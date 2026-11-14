"""Parallel HTTP requests; real independent PostgreSQL transactions and row locks."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from test_posting import (
    assert_journals_balance,
    balances,
    make_loan,
    payment,
    repay,
)

from ledgercore.models.entities import (
    IdempotencyRequest,
    LedgerJournal,
    Loan,
    Repayment,
    RepaymentAllocation,
    RepaymentSchedule,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "workers,amount,successes,day",
    [
        (2, 6000, 1, "2026-01-15"),
        (20, 1000, 10, "2026-01-15"),
        (20, 1000, 10, "2026-01-31"),
    ],
)
def test_overlapping_principal_serializes(
    parallel_env, workers, amount, successes, day
):
    client, engine = parallel_env
    loan_id = make_loan(client)
    start = Barrier(workers)

    def submit(index):
        start.wait(timeout=10)
        return repay(
            client,
            loan_id,
            payment(amount, event=f"parallel-{index}", day=day),
            f"key-{index}",
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        responses = list(pool.map(submit, range(workers)))
    statuses = [r.status_code for r in responses]
    assert statuses.count(201) == successes, [
        (r.status_code, r.text) for r in responses
    ]
    assert statuses.count(400) == workers - successes
    interest = 100 if day == "2026-01-31" else 0
    assert balances(client, loan_id) == (10000 + interest - successes * amount, 0, 0)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Repayment)) == successes
        assert (
            session.scalar(select(func.sum(RepaymentAllocation.amount_paise)))
            == successes * amount
        )
        for row in session.scalars(select(RepaymentSchedule)):
            allocated = session.scalar(
                select(
                    func.coalesce(func.sum(RepaymentAllocation.amount_paise), 0)
                ).where(
                    RepaymentAllocation.schedule_id == row.id,
                    RepaymentAllocation.component == "principal",
                )
            )
            assert 0 <= allocated <= row.principal_due_paise
    rows = assert_journals_balance(client, loan_id)
    assert len(rows) == successes + 1 + bool(interest)
    assert sum(j["kind"] == "scheduled_interest" for j in rows) == bool(interest)


@pytest.mark.parametrize("same_key", [True, False])
def test_twenty_duplicate_deliveries_post_once(parallel_env, same_key):
    client, engine = parallel_env
    loan_id = make_loan(client)
    body = payment(1000, event="one-source-event", day="2026-01-15")
    start = Barrier(20)

    def submit(index):
        start.wait(timeout=10)
        return repay(
            client, loan_id, body, "same-key" if same_key else f"alias-{index}"
        )

    with ThreadPoolExecutor(max_workers=20) as pool:
        responses = list(pool.map(submit, range(20)))
    assert all(r.status_code == 201 for r in responses), [
        (r.status_code, r.text) for r in responses
    ]
    assert all(r.json() == responses[0].json() for r in responses)
    assert balances(client, loan_id) == (9000, 0, 0)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Repayment)) == 1
        assert session.scalar(select(func.count()).select_from(IdempotencyRequest)) == (
            1 if same_key else 20
        )
    assert len(assert_journals_balance(client, loan_id)) == 2


@pytest.mark.parametrize("collision", ["source_event", "idempotency_key"])
def test_cross_loan_uniqueness_race_is_sanitized(parallel_env, collision):
    client, engine = parallel_env
    loans = [make_loan(client), make_loan(client)]
    start = Barrier(2)

    def submit(index):
        body = payment(
            1000,
            event="shared-event" if collision == "source_event" else f"event-{index}",
            day="2026-01-15",
        )
        start.wait(timeout=10)
        return repay(
            client,
            loans[index],
            body,
            "shared-key" if collision == "idempotency_key" else f"key-{index}",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, range(2)))
    assert sorted(r.status_code for r in responses) == [201, 409], [
        (r.status_code, r.text) for r in responses
    ]
    assert all(
        "sqlalchemy" not in r.text.lower() and "INSERT INTO" not in r.text
        for r in responses
    )
    assert sum(balances(client, loan_id)[0] for loan_id in loans) == 19000
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Repayment)) == 1


def test_request_waits_for_real_postgresql_loan_lock(parallel_env):
    client, engine = parallel_env
    loan_id = make_loan(client)
    with Session(engine) as blocker, blocker.begin():
        blocker.scalar(select(Loan).where(Loan.id == UUID(loan_id)).with_for_update())
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                repay, client, loan_id, payment(1000, day="2026-01-15")
            )
            try:
                deadline = time.monotonic() + 5
                observed = False
                while time.monotonic() < deadline:
                    with engine.connect() as observer:
                        observed = observer.scalar(
                            text(
                                "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE application_name = 'ledgercore_parallel' AND wait_event_type = 'Lock')"
                            )
                        )
                    if observed:
                        break
                    time.sleep(0.01)
                assert observed, "No PostgreSQL lock wait observed"
                assert not future.done()
            finally:
                # Release BEFORE waiting for the thread, including assertion failures.
                blocker.commit()
            assert future.result(timeout=10).status_code == 201
    assert balances(client, loan_id) == (9000, 0, 0)
    assert_journals_balance(client, loan_id)


def test_upgrade_preserves_phase_one_origination(parallel_env):
    from datetime import date

    from ledgercore.models.entities import Borrower
    from ledgercore.schemas.api import LoanCreate
    from ledgercore.services.origination import originate

    client, engine = parallel_env
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "0002")
    with Session(engine) as session, session.begin():
        borrower = Borrower(
            external_reference="PHASE-ONE", full_name="Existing Borrower"
        )
        session.add(borrower)
        session.flush()
        loan = originate(
            session,
            LoanCreate(
                external_reference="EXISTING-LOAN",
                borrower_id=borrower.id,
                product_id=UUID("00000000-0000-0000-0000-000000000002"),
                principal_paise=10000,
                tenure_periods=2,
                first_due_date=date(2026, 1, 31),
            ),
        )
        session.flush()
        loan_id = str(loan.id)
        before = [
            (r.id, r.principal_due_paise, r.interest_due_paise)
            for r in session.scalars(
                select(RepaymentSchedule).order_by(RepaymentSchedule.instalment_number)
            )
        ]
    command.upgrade(cfg, "head")
    command.check(cfg)
    with Session(engine) as session:
        after = [
            (r.id, r.principal_due_paise, r.interest_due_paise)
            for r in session.scalars(
                select(RepaymentSchedule).order_by(RepaymentSchedule.instalment_number)
            )
        ]
        assert before == after
    assert client.get(f"/loans/{loan_id}").json()["status"] == "originated"
    assert balances(client, loan_id) == (0, 0, 0)


def test_simultaneous_disbursements_post_once(parallel_env):
    from test_posting import MANAGER

    client, engine = parallel_env
    loan_id = make_loan(client, disburse=False)
    start = Barrier(2)

    def submit(_):
        start.wait(timeout=10)
        return client.post(
            f"/loans/{loan_id}/disburse",
            json={"business_date": "2026-01-01"},
            headers=MANAGER,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, range(2)))
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert balances(client, loan_id) == (10000, 0, 0)
    assert len(assert_journals_balance(client, loan_id)) == 1


def test_simultaneous_reversals_restore_once(parallel_env):
    from test_posting import MANAGER

    client, engine = parallel_env
    loan_id = make_loan(client)
    original = repay(client, loan_id, payment(1000, day="2026-01-15")).json()
    start = Barrier(2)

    def submit(_):
        start.wait(timeout=10)
        return client.post(
            f"/loans/{loan_id}/journals/{original['journal_id']}/reverse",
            json={"business_date": "2026-01-15", "reason": "Concurrent retry"},
            headers=MANAGER,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    assert balances(client, loan_id) == (10000, 0, 0)
    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(LedgerJournal)
                .where(LedgerJournal.kind == "reversal")
            )
            == 1
        )
    assert len(assert_journals_balance(client, loan_id)) == 3
