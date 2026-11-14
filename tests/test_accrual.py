from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from test_posting import (
    MANAGER,
    assert_journals_balance,
    balances,
    counts,
    make_loan,
    payment,
    repay,
)

from ledgercore.accounting import posting
from ledgercore.jobs import accrual
from ledgercore.models.entities import (
    AccrualRecord,
    LedgerJournal,
    User,
)

pytestmark = pytest.mark.integration


def actor(db):
    result = db.scalar(select(User.id).where(User.external_subject == "demo-manager"))
    db.rollback()
    return result


def run_one(db, loan_id, day, *, catch_up=False):
    actor_id = actor(db)
    with db.begin():
        return accrual.accrue_loan(
            db,
            UUID(loan_id),
            date.fromisoformat(day),
            actor_id,
            "test-accrual",
            catch_up=catch_up,
        )


def test_due_date_boundary_noncompounding_and_repeat(client, db):
    loan_id = make_loan(client)
    assert run_one(db, loan_id, "2026-01-31")["charged_days"] == 0
    assert balances(client, loan_id) == (10000, 100, 0)
    assert (
        run_one(db, loan_id, "2026-02-01")["penalty_paise"] == 2
    )  # 4975 * .0005 = 2.4875 -> 2
    before = counts(db)
    db.rollback()
    assert run_one(db, loan_id, "2026-02-01")["evaluated_days"] == 0
    assert counts(db) == before
    db.rollback()
    assert run_one(db, loan_id, "2026-02-02")["penalty_paise"] == 2
    assert balances(client, loan_id) == (10000, 100, 4)
    rows = assert_journals_balance(client, loan_id)
    assert sum(j["kind"] == "scheduled_interest" for j in rows) == 1
    assert sum(j["kind"] == "penalty" for j in rows) == 2


def test_half_up_daily_rounding(client, db):
    loan_id = make_loan(client, principal=2010)
    rows = client.get(f"/loans/{loan_id}/schedule").json()
    assert rows[0]["principal_due_paise"] == 1000
    # Half a paisa rounds UP; neither interest nor existing penalties enter the basis.
    assert run_one(db, loan_id, "2026-02-01")["penalty_paise"] == 1
    assert run_one(db, loan_id, "2026-02-02")["penalty_paise"] == 1
    assert balances(client, loan_id)[2] == 2


def test_partial_principal_reduces_only_next_day_and_zero_identity(client, db):
    loan_id = make_loan(client)
    assert run_one(db, loan_id, "2026-02-01")["penalty_paise"] == 2
    response = repay(client, loan_id, payment(4102, day="2026-02-01"))
    assert response.status_code == 201, response.text
    assert [
        (a["component"], a["amount_paise"]) for a in response.json()["allocations"]
    ] == [("penalty", 2), ("interest", 100), ("principal", 4000)]
    assert run_one(db, loan_id, "2026-02-01")["evaluated_days"] == 0
    assert (
        run_one(db, loan_id, "2026-02-02")["penalty_paise"] == 0
    )  # 975 * .0005 = .4875
    record = db.scalar(
        select(AccrualRecord).where(
            AccrualRecord.kind == "overdue_penalty",
            AccrualRecord.period_start == date(2026, 2, 2),
        )
    )
    assert (
        record.basis_paise == 975
        and record.amount_paise == 0
        and record.journal_id is None
    )
    db.rollback()
    assert run_one(db, loan_id, "2026-02-02")["evaluated_days"] == 0
    assert balances(client, loan_id) == (6000, 0, 0)


def test_catch_up_uses_historical_processing_dates(client, db):
    loan_id = make_loan(client)
    # Delayed economic timestamp does not retrospectively reduce the opening basis.
    body = payment(4100, day="2026-02-02") | {"occurred_at": "2026-01-15T10:00:00Z"}
    assert repay(client, loan_id, body).status_code == 201
    assert run_one(db, loan_id, "2026-02-03", catch_up=True)["penalty_paise"] == 4
    rows = db.scalars(
        select(AccrualRecord)
        .where(AccrualRecord.kind == "overdue_penalty")
        .order_by(AccrualRecord.period_start)
    ).all()
    assert [(r.period_start, r.basis_paise, r.amount_paise) for r in rows] == [
        (date(2026, 2, 1), 4975, 2),
        (date(2026, 2, 2), 4975, 2),
        (date(2026, 2, 3), 975, 0),
    ]
    db.rollback()
    assert balances(client, loan_id) == (6000, 0, 4)
    assert run_one(db, loan_id, "2026-02-03", catch_up=True)["evaluated_days"] == 0


def test_zero_days_prevent_backdated_reversal(client, db):
    loan_id = make_loan(client, principal=1)
    receipt = repay(client, loan_id, payment(1, day="2026-01-15")).json()
    result = run_one(db, loan_id, "2026-02-10", catch_up=True)
    assert result["evaluated_days"] == 10 and result["charged_days"] == 0
    assert (
        client.post(
            f"/loans/{loan_id}/journals/{receipt['journal_id']}/reverse",
            headers=MANAGER,
            json={"business_date": "2026-02-05", "reason": "Backdate"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/loans/{loan_id}/journals/{receipt['journal_id']}/reverse",
            headers=MANAGER,
            json={"business_date": "2026-02-10", "reason": "Current reversal"},
        ).status_code
        == 200
    )
    assert run_one(db, loan_id, "2026-02-11", catch_up=True)["evaluated_days"] == 1


def test_reversal_restores_future_daily_basis_without_rewriting_past(client, db):
    loan_id = make_loan(client)
    receipt = repay(client, loan_id, payment(4100, day="2026-02-01")).json()
    assert (
        client.post(
            f"/loans/{loan_id}/journals/{receipt['journal_id']}/reverse",
            headers=MANAGER,
            json={"business_date": "2026-02-03", "reason": "Restore principal"},
        ).status_code
        == 200
    )
    assert run_one(db, loan_id, "2026-02-04", catch_up=True)["penalty_paise"] == 4
    rows = db.scalars(
        select(AccrualRecord)
        .where(AccrualRecord.kind == "overdue_penalty")
        .order_by(AccrualRecord.period_start)
    ).all()
    assert [(r.basis_paise, r.amount_paise) for r in rows] == [
        (4975, 2),
        (975, 0),
        (975, 0),
        (4975, 2),
    ]


def test_loan_failure_rolls_back_whole_catch_up(client, db, monkeypatch):
    loan_id = make_loan(client)
    before = counts(db)
    db.rollback()
    real = posting.post_journal
    seen = 0

    def fail(*args, **kwargs):
        nonlocal seen
        result = real(*args, **kwargs)
        if args[2] == "penalty":
            seen += 1
            if seen == 2:
                raise RuntimeError("Injected daily failure")
        return result

    monkeypatch.setattr(posting, "post_journal", fail)
    with pytest.raises(RuntimeError, match="Injected daily failure"):
        run_one(db, loan_id, "2026-02-03", catch_up=True)
    assert counts(db) == before
    db.rollback()
    assert balances(client, loan_id) == (10000, 0, 0)
    monkeypatch.setattr(posting, "post_journal", real)
    assert run_one(db, loan_id, "2026-02-03", catch_up=True)["penalty_paise"] == 6


def test_job_partial_failure_resume_and_max_horizon(client, db, monkeypatch):
    ids = [UUID(make_loan(client)), UUID(make_loan(client))]
    factory = sessionmaker(
        db.bind, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    real = accrual.accrue_loan

    def fail_second(*args, **kwargs):
        result = real(*args, **kwargs)
        if args[1] == ids[1]:
            raise RuntimeError("Second loan fails")
        return result

    monkeypatch.setattr(accrual, "accrue_loan", fail_second)
    first = accrual.run_job(factory, date(2026, 2, 2), catch_up=True, loan_ids=ids)
    assert len(first["results"]) == 1 and len(first["failures"]) == 1
    assert balances(client, str(ids[0])) == (10000, 100, 4)
    assert balances(client, str(ids[1])) == (10000, 0, 0)
    monkeypatch.setattr(accrual, "accrue_loan", real)
    second = accrual.run_job(factory, date(2026, 2, 2), catch_up=True, loan_ids=ids)
    assert not second["failures"]
    assert [r["evaluated_days"] for r in second["results"]] == [0, 2]
    fail = accrual.run_job(
        factory, date(2026, 2, 5), catch_up=True, loan_ids=[ids[0]], max_days=1
    )
    assert len(fail["failures"]) == 1
    assert balances(client, str(ids[0])) == (10000, 100, 4)


def test_daily_period_constraints_and_immutability(client, db):
    loan_id = make_loan(client, principal=1)
    run_one(db, loan_id, "2026-02-01")
    record = db.scalar(
        select(AccrualRecord).where(AccrualRecord.kind == "overdue_penalty")
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            AccrualRecord(
                loan_id=record.loan_id,
                schedule_id=record.schedule_id,
                kind=record.kind,
                period_start=record.period_start,
                period_end=record.period_end + timedelta(days=1),
                basis_paise=0,
                amount_paise=0,
                daily_rate=accrual.DAILY_RATE,
            )
        )
        db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.delete(record)
        db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            AccrualRecord(
                loan_id=record.loan_id,
                schedule_id=record.schedule_id,
                kind=record.kind,
                period_start=record.period_start,
                period_end=record.period_end,
                basis_paise=0,
                amount_paise=0,
                daily_rate=accrual.DAILY_RATE,
            )
        )
        db.flush()


def test_concurrent_repayment_and_two_accruals(parallel_env):
    client, engine = parallel_env
    loan_id = make_loan(client)
    with Session(engine) as session:
        actor_id = session.scalar(
            select(User.id).where(User.external_subject == "demo-manager")
        )
    start = Barrier(3)

    def run_accrual():
        start.wait(timeout=10)
        with Session(engine) as session, session.begin():
            return accrual.accrue_loan(
                session,
                UUID(loan_id),
                date(2026, 2, 2),
                actor_id,
                "parallel-accrual",
                catch_up=True,
            )

    def run_payment():
        start.wait(timeout=10)
        return repay(client, loan_id, payment(1000, day="2026-02-02"))

    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(run_accrual), pool.submit(run_accrual)]
        receipt = pool.submit(run_payment)
        results = [j.result(timeout=15) for j in jobs]
        assert receipt.result(timeout=15).status_code == 201
    assert sum(r["penalty_paise"] for r in results) == 4
    assert balances(client, loan_id) in [(9100, 0, 4), (9104, 0, 0)]
    assert_journals_balance(client, loan_id)
    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(AccrualRecord)
                .where(AccrualRecord.kind == "overdue_penalty")
            )
            == 2
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(LedgerJournal)
                .where(LedgerJournal.kind == "scheduled_interest")
            )
            == 1
        )


def test_missing_receivable_schedule_fails_closed(client, db):
    loan_id = make_loan(client)
    with db.begin():
        posting.lock_loan(db, UUID(loan_id))
        posting.post_journal(
            db,
            UUID(loan_id),
            "penalty",
            "malformed-legacy-lot",
            date(2026, 1, 2),
            [
                ("PENALTY_RECEIVABLE", "debit", 10, None, None),
                ("PENALTY_INCOME", "credit", 10, None, None),
            ],
        )
    before = counts(db)
    db.rollback()
    response = repay(client, loan_id, payment(100, day="2026-01-15"))
    assert response.status_code == 409
    assert "reconciliation" in response.json()["detail"]
    assert counts(db) == before


def test_accrual_rejects_unreconciled_principal_before_posting(client, db):
    loan_id = make_loan(client)
    with db.begin():
        posting.lock_loan(db, UUID(loan_id))
        # Simulate inconsistent historical SQL outside supported posting operations.
        posting.post_journal(
            db,
            UUID(loan_id),
            "penalty",
            "malformed-principal-history",
            date(2026, 1, 2),
            [
                ("CASH", "debit", 1, None, None),
                ("LOAN_PRINCIPAL_RECEIVABLE", "credit", 1, None, None),
            ],
        )
    before = counts(db)
    db.rollback()
    with pytest.raises(posting.FinancialError, match="reconciliation before accrual"):
        run_one(db, loan_id, "2026-02-01", catch_up=True)
    assert counts(db) == before
