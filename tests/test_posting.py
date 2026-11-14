from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ledgercore.accounting import posting
from ledgercore.models.entities import (
    AccrualRecord,
    AuditEvent,
    IdempotencyRequest,
    LedgerEntry,
    LedgerJournal,
    Loan,
    Repayment,
    RepaymentAllocation,
    RepaymentSchedule,
    User,
)

pytestmark = pytest.mark.integration
OFFICER = {"X-Demo-User": "demo-officer"}
MANAGER = {"X-Demo-User": "demo-manager"}
AUDITOR = {"X-Demo-User": "demo-auditor"}


def make_loan(client, *, principal=10000, first="2026-01-31", periods=2, disburse=True):
    suffix = uuid4().hex
    b = client.post(
        "/borrowers",
        json={"external_reference": "B-" + suffix, "full_name": "Posting Test"},
    )
    assert b.status_code == 201, b.text
    result = client.post(
        "/loans",
        json={
            "external_reference": "L-" + suffix,
            "borrower_id": b.json()["id"],
            "product_id": "00000000-0000-0000-0000-000000000002",
            "principal_paise": principal,
            "tenure_periods": periods,
            "first_due_date": first,
        },
    )
    assert result.status_code == 201, result.text
    loan_id = result.json()["id"]
    if disburse:
        result = client.post(
            f"/loans/{loan_id}/disburse",
            json={"business_date": "2026-01-01"},
            headers=MANAGER,
        )
        assert result.status_code == 201, result.text
    return loan_id


def payment(amount=100, event=None, day="2026-01-31"):
    return {
        "amount_paise": amount,
        "source": "test",
        "external_event_id": event or uuid4().hex,
        "occurred_at": day + "T10:00:00Z",
        "business_date": day,
    }


def repay(client, loan_id, body, key=None, headers=None):
    return client.post(
        f"/loans/{loan_id}/repayments",
        json=body,
        headers={**OFFICER, "Idempotency-Key": key or uuid4().hex, **(headers or {})},
    )


def balances(client, loan_id):
    response = client.get(f"/loans/{loan_id}/balance")
    assert response.status_code == 200, response.text
    result = response.json()
    return tuple(
        result[k + "_receivable_paise"] for k in ["principal", "interest", "penalty"]
    )


def assert_journals_balance(client, loan_id):
    response = client.get(f"/loans/{loan_id}/ledger", headers=AUDITOR)
    assert response.status_code == 200, response.text
    rows = response.json()
    for journal in rows:
        assert len(journal["entries"]) >= 2
        assert (
            sum(
                e["amount_paise"] if e["direction"] == "debit" else -e["amount_paise"]
                for e in journal["entries"]
            )
            == 0
        )
    return rows


def counts(db):
    return {
        model.__name__: db.scalar(select(func.count()).select_from(model))
        for model in [
            Repayment,
            RepaymentAllocation,
            LedgerJournal,
            LedgerEntry,
            IdempotencyRequest,
            AuditEvent,
            AccrualRecord,
        ]
    }


def test_disbursement_once_and_balanced(client):
    loan_id = make_loan(client, disburse=False)
    assert balances(client, loan_id) == (0, 0, 0)
    assert repay(client, loan_id, payment()).status_code == 409
    assert (
        client.post(
            f"/loans/{loan_id}/disburse",
            json={"business_date": "2026-01-01"},
            headers=MANAGER,
        ).status_code
        == 201
    )
    assert balances(client, loan_id) == (10000, 0, 0)
    assert client.get(f"/loans/{loan_id}").json()["status"] == "disbursed"
    assert (
        client.post(
            f"/loans/{loan_id}/disburse",
            json={"business_date": "2026-01-01"},
            headers=MANAGER,
        ).status_code
        == 409
    )
    rows = assert_journals_balance(client, loan_id)
    assert len(rows) == 1
    assert {
        (e["account"], e["direction"], e["amount_paise"]) for e in rows[0]["entries"]
    } == {("LOAN_PRINCIPAL_RECEIVABLE", "debit", 10000), ("CASH", "credit", 10000)}


def test_partial_repayment_interest_before_principal(client):
    loan_id = make_loan(client)
    response = repay(client, loan_id, payment(60))
    assert response.status_code == 201, response.text
    assert [
        (a["component"], a["amount_paise"]) for a in response.json()["allocations"]
    ] == [("interest", 60)]
    assert balances(client, loan_id) == (10000, 40, 0)
    response = repay(client, loan_id, payment(100))
    assert [
        (a["component"], a["amount_paise"]) for a in response.json()["allocations"]
    ] == [("interest", 40), ("principal", 60)]
    assert balances(client, loan_id) == (9940, 0, 0)
    rows = assert_journals_balance(client, loan_id)
    assert [j["kind"] for j in rows].count("scheduled_interest") == 1
    repayment = next(j for j in rows if j["id"] == response.json()["journal_id"])
    assert {
        (e["account"], e["direction"], e["amount_paise"]) for e in repayment["entries"]
    } == {
        ("CASH", "debit", 100),
        ("INTEREST_RECEIVABLE", "credit", 40),
        ("LOAN_PRINCIPAL_RECEIVABLE", "credit", 60),
    }


def test_independent_recognition_idempotence_and_due_boundary(client, db):
    loan_id = make_loan(client)
    actor = db.scalar(select(User.id).where(User.external_subject == "demo-manager"))
    db.rollback()
    with db.begin():
        assert (
            posting.recognize_scheduled_interest(
                db, UUID(loan_id), date(2026, 1, 30), actor, "before-due"
            )
            == []
        )
    assert balances(client, loan_id) == (10000, 0, 0)
    with db.begin():
        journals = posting.recognize_scheduled_interest(
            db, UUID(loan_id), date(2026, 1, 31), actor, "due"
        )
        assert len(journals) == 1
        assert (
            posting.recognize_scheduled_interest(
                db, UUID(loan_id), date(2026, 1, 31), actor, "repeat"
            )
            == []
        )
    assert balances(client, loan_id) == (10000, 100, 0)
    assert repay(client, loan_id, payment(100)).status_code == 201
    assert balances(client, loan_id) == (10000, 0, 0)
    with db.begin():
        assert (
            len(
                posting.recognize_scheduled_interest(
                    db, UUID(loan_id), date(2026, 2, 28), actor, "next"
                )
            )
            == 1
        )
    assert balances(client, loan_id) == (10000, 50, 0)
    assert_journals_balance(client, loan_id)


def test_prepayment_keeps_schedule_and_future_interest(client):
    loan_id = make_loan(client)
    original = client.get(f"/loans/{loan_id}/schedule").json()
    first = repay(client, loan_id, payment(8000, day="2026-01-15"))
    assert first.status_code == 201, first.text
    assert [
        (a["schedule_id"], a["amount_paise"]) for a in first.json()["allocations"]
    ] == [(original[0]["id"], 4975), (original[1]["id"], 3025)]
    assert balances(client, loan_id) == (2000, 0, 0)
    second = repay(client, loan_id, payment(1000))
    assert second.status_code == 201, second.text
    assert [
        (a["component"], a["amount_paise"]) for a in second.json()["allocations"]
    ] == [("interest", 100), ("principal", 900)]
    assert balances(client, loan_id) == (1100, 0, 0)
    # February recognizes the ORIGINAL remaining contractual interest, with no rebate.
    third = repay(client, loan_id, payment(1150, day="2026-02-28"))
    assert third.status_code == 201, third.text
    assert balances(client, loan_id) == (0, 0, 0)
    assert client.get(f"/loans/{loan_id}/schedule").json() == original
    receipts = client.get(f"/loans/{loan_id}/repayments").json()
    for row in original:
        total = sum(
            a["amount_paise"]
            for r in receipts
            for a in r["allocations"]
            if a["component"] == "principal" and a["schedule_id"] == row["id"]
        )
        assert total == row["principal_due_paise"]
    assert_journals_balance(client, loan_id)


def test_full_early_principal_payment_does_not_cancel_interest(client):
    loan_id = make_loan(client)
    assert repay(client, loan_id, payment(10000, day="2026-01-15")).status_code == 201
    assert balances(client, loan_id) == (0, 0, 0)
    assert repay(client, loan_id, payment(1, day="2026-01-16")).status_code == 400
    assert repay(client, loan_id, payment(100)).status_code == 201
    assert repay(client, loan_id, payment(50, day="2026-02-28")).status_code == 201
    assert balances(client, loan_id) == (0, 0, 0)


def test_overpayment_atomic_including_auto_recognition(client, db):
    loan_id = make_loan(client)
    before = counts(db)
    db.rollback()
    assert repay(client, loan_id, payment(10101)).status_code == 400
    assert balances(client, loan_id) == (10000, 0, 0)
    assert counts(db) == before


@pytest.mark.parametrize("value", [0, -1, True, 1.2, "100", 100000000001])
def test_repayment_invalid_amounts(client, value):
    loan_id = make_loan(client)
    assert repay(client, loan_id, payment(value)).status_code == 422


def test_retry_hash_and_source_identity(client, db):
    loan_id = make_loan(client)
    body = payment(1000, event="E-RETRY")
    first = repay(client, loan_id, body, "KEY-1")
    assert first.status_code == 201, first.text
    # Treat the first committed response as lost; retry returns identical body/status.
    assert repay(client, loan_id, body, "KEY-1").json() == first.json()
    assert (
        repay(
            client,
            loan_id,
            body | {"occurred_at": "2026-01-31T15:30:00+05:30"},
            "KEY-1",
        ).json()
        == first.json()
    )
    assert (
        repay(client, loan_id, body | {"amount_paise": 1001}, "KEY-1").status_code
        == 409
    )
    assert repay(client, loan_id, body, "KEY-2").json() == first.json()
    assert repay(client, loan_id, body, "KEY-2").json() == first.json()
    assert (
        repay(client, loan_id, body | {"amount_paise": 1001}, "KEY-3").status_code
        == 409
    )
    assert balances(client, loan_id) == (9100, 0, 0)
    assert db.scalar(select(func.count()).select_from(Repayment)) == 1
    assert db.scalar(select(func.count()).select_from(IdempotencyRequest)) == 2
    assert (
        db.scalar(
            select(func.count())
            .select_from(LedgerJournal)
            .where(LedgerJournal.kind == "repayment")
        )
        == 1
    )


def test_idempotency_required_and_strict_dates(client):
    loan_id = make_loan(client)
    body = payment()
    assert client.post(f"/loans/{loan_id}/repayments", json=body).status_code == 422
    for patch in [
        {"business_date": 0},
        {"occurred_at": 0},
        {"occurred_at": "2026-01-31T10:00:00"},
        {"business_date": "2026-01-30"},
    ]:
        assert repay(client, loan_id, body | patch).status_code == 422
    assert repay(client, loan_id, body, " ").status_code == 422


def test_processing_dates_monotonic_but_old_retries_work(client):
    loan_id = make_loan(client)
    body = payment(100)
    first = repay(client, loan_id, body, "OLD")
    assert first.status_code == 201
    assert repay(client, loan_id, payment(100, day="2026-02-28")).status_code == 201
    assert repay(client, loan_id, body, "OLD").json() == first.json()
    assert repay(client, loan_id, payment(100)).status_code == 409
    # Economic arrivals may be out of order at the CURRENT processing date.
    assert (
        repay(
            client,
            loan_id,
            payment(100, day="2026-02-28") | {"occurred_at": "2026-01-10T10:00:00Z"},
        ).status_code
        == 201
    )


@pytest.mark.parametrize("role", [OFFICER, AUDITOR])
def test_manager_only_disbursement(client, role):
    loan_id = make_loan(client, disburse=False)
    assert (
        client.post(
            f"/loans/{loan_id}/disburse",
            json={"business_date": "2026-01-01"},
            headers=role,
        ).status_code
        == 403
    )
    assert balances(client, loan_id) == (0, 0, 0)


def test_auditor_read_only_and_denied_audit(client, db):
    loan_id = make_loan(client)
    assert client.get(f"/loans/{loan_id}", headers=AUDITOR).status_code == 200
    assert (
        client.get(f"/loans/{loan_id}/repayments", headers=AUDITOR).status_code == 200
    )
    assert client.get(f"/loans/{loan_id}/balance", headers=AUDITOR).status_code == 200
    assert (
        client.post(
            "/borrowers",
            json={"external_reference": "DENIED", "full_name": "Auditor"},
            headers=AUDITOR,
        ).status_code
        == 403
    )
    assert client.post("/loans", json={}, headers=AUDITOR).status_code == 403
    assert repay(client, loan_id, payment(), headers=AUDITOR).status_code == 403
    assert client.get("/audit-events", headers=OFFICER).status_code == 403
    response = client.get("/audit-events", headers=AUDITOR)
    assert response.status_code == 200
    denied = [r for r in response.json() if r["action"] == "authorization.denied"]
    auditor_id = str(
        db.scalar(select(User.id).where(User.external_subject == "demo-auditor"))
    )
    assert any(r["actor_user_id"] == auditor_id for r in denied)
    assert all(
        r["correlation_id"] and "amount_paise" not in r["details"] for r in denied
    )


def test_unknown_inactive_identity_and_no_role_header(client, db, monkeypatch):
    assert (
        client.get(
            "/loan-products",
            headers={"X-Demo-User": "unknown", "X-Demo-Role": "manager"},
        ).status_code
        == 403
    )
    with db.begin():
        user = db.scalar(select(User).where(User.external_subject == "demo-auditor"))
        user.active = False
    assert client.get("/loan-products", headers=AUDITOR).status_code == 403
    monkeypatch.setenv("DEMO_AUTH_ENABLED", "false")
    assert client.get("/loan-products").status_code == 503


def test_audit_actor_correlation_and_state(client, db):
    loan_id = make_loan(client)
    response = repay(
        client, loan_id, payment(101), headers={"X-Correlation-ID": "request-101"}
    )
    assert response.status_code == 201
    assert response.headers["X-Correlation-ID"] == "request-101"
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "repayment.posted"))
    assert event.actor_user_id == db.scalar(
        select(User.id).where(User.external_subject == "demo-officer")
    )
    assert event.details["journal_id"] == response.json()["journal_id"]
    assert event.details["before"]["principal_receivable_paise"] == 10000
    assert event.details["after"]["principal_receivable_paise"] == 9999
    assert event.created_at.utcoffset().total_seconds() == 0
    assert (
        client.get("/health", headers={"X-Correlation-ID": "bad value"}).status_code
        == 400
    )


def test_reversal_exact_restores_operational_allocations_and_idempotency(client, db):
    loan_id = make_loan(client)
    body = payment(6000)
    original = repay(client, loan_id, body, "ORIGINAL").json()
    assert balances(client, loan_id) == (4100, 0, 0)
    path = f"/loans/{loan_id}/journals/{original['journal_id']}/reverse"
    reverse_body = {
        "business_date": "2026-01-31",
        "reason": "Duplicate bank settlement",
    }
    assert client.post(path, json=reverse_body, headers=OFFICER).status_code == 403
    assert client.post(path, json=reverse_body, headers=AUDITOR).status_code == 403
    response = client.post(path, json=reverse_body, headers=MANAGER)
    assert response.status_code == 200, response.text
    assert balances(client, loan_id) == (10000, 100, 0)
    assert (
        client.post(path, json=reverse_body, headers=MANAGER).json() == response.json()
    )
    rows = assert_journals_balance(client, loan_id)
    by_id = {j["id"]: j for j in rows}

    def normalized(j, flip=False):
        return sorted(
            (
                e["account"],
                ("credit" if e["direction"] == "debit" else "debit")
                if flip
                else e["direction"],
                e["amount_paise"],
                str(e["schedule_id"]),
                str(e["receivable_origin_id"]),
            )
            for e in j["entries"]
        )

    assert normalized(by_id[original["journal_id"]], True) == normalized(
        by_id[response.json()["journal_id"]]
    )
    assert client.get(f"/loans/{loan_id}/repayments").json()[0]["status"] == "reversed"
    # Historical retry remains the original accepted response; it must never re-post.
    assert repay(client, loan_id, body, "ORIGINAL").json() == original
    assert repay(client, loan_id, body, "ALIAS").json() == original
    assert balances(client, loan_id) == (10000, 100, 0)
    # Full principal capacity is available again; no schedule edit is needed.
    assert repay(client, loan_id, payment(10100)).status_code == 201
    assert balances(client, loan_id) == (0, 0, 0)
    assert (
        client.post(
            f"/loans/{loan_id}/journals/{response.json()['journal_id']}/reverse",
            json=reverse_body,
            headers=MANAGER,
        ).status_code
        == 409
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(LedgerJournal)
            .where(LedgerJournal.kind == "reversal")
        )
        == 1
    )


def test_unsupported_reversal_types_and_cross_loan(client):
    loan_id = make_loan(client)
    other_id = make_loan(client)
    disbursement = assert_journals_balance(client, loan_id)[0]
    body = {"business_date": "2026-01-31", "reason": "Test"}
    assert (
        client.post(
            f"/loans/{loan_id}/journals/{disbursement['id']}/reverse",
            json=body,
            headers=MANAGER,
        ).status_code
        == 409
    )
    repayment = repay(client, loan_id, payment()).json()
    assert (
        client.post(
            f"/loans/{other_id}/journals/{repayment['journal_id']}/reverse",
            json=body,
            headers=MANAGER,
        ).status_code
        == 404
    )
    interest = next(
        j
        for j in assert_journals_balance(client, loan_id)
        if j["kind"] == "scheduled_interest"
    )
    assert (
        client.post(
            f"/loans/{loan_id}/journals/{interest['id']}/reverse",
            json=body,
            headers=MANAGER,
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "failure_at", ["after_journal", "after_idempotency", "after_audit"]
)
def test_repayment_injected_failure_rolls_back_all(client, db, monkeypatch, failure_at):
    loan_id = make_loan(client)
    before = counts(db)
    db.rollback()
    function = {
        "after_journal": "post_journal",
        "after_idempotency": "complete_idempotency",
        "after_audit": "audit",
    }[failure_at]
    real = getattr(posting, function)

    def fail(*args, **kwargs):
        result = real(*args, **kwargs)
        # Let auto-recognition finish; fail at the later repayment journal/audit.
        if function == "post_journal" and args[2] != "repayment":
            return result
        if function == "audit" and args[3] != "repayment.posted":
            return result
        raise RuntimeError("Injected failure")

    monkeypatch.setattr(posting, function, fail)
    with pytest.raises(RuntimeError, match="Injected failure"):
        repay(client, loan_id, payment(1000))
    assert counts(db) == before
    db.rollback()
    assert balances(client, loan_id) == (10000, 0, 0)


def test_reversal_failure_rolls_back(client, db, monkeypatch):
    loan_id = make_loan(client)
    receipt = repay(client, loan_id, payment(1000)).json()
    before = counts(db)
    db.rollback()
    real = posting.audit

    def fail(*args, **kwargs):
        real(*args, **kwargs)
        if args[3] == "repayment.reversed":
            raise RuntimeError("Injected reversal failure")

    monkeypatch.setattr(posting, "audit", fail)
    with pytest.raises(RuntimeError, match="Injected reversal failure"):
        client.post(
            f"/loans/{loan_id}/journals/{receipt['journal_id']}/reverse",
            json={"business_date": "2026-01-31", "reason": "Failure test"},
            headers=MANAGER,
        )
    assert counts(db) == before
    db.rollback()
    assert balances(client, loan_id) == (9100, 0, 0)


def test_zero_interest_has_no_empty_journal(client, db):
    loan_id = make_loan(client, principal=1)
    response = repay(client, loan_id, payment(1, day="2026-02-28"))
    assert response.status_code == 201, response.text
    assert db.scalar(select(func.count()).select_from(AccrualRecord)) == 0
    assert balances(client, loan_id) == (0, 0, 0)
    assert_journals_balance(client, loan_id)


def test_penalty_lots_before_interest_then_principal(client, db):
    loan_id = make_loan(client)
    schedules = client.get(f"/loans/{loan_id}/schedule").json()
    # Seed existing recognized penalty receivables through the internal journal primitive.
    # There is intentionally no penalty generation service or endpoint.
    with db.begin():
        posting.lock_loan(db, UUID(loan_id))
        for schedule, amount, day in [
            (schedules[1], 30, date(2026, 1, 10)),
            (schedules[0], 20, date(2026, 1, 11)),
        ]:
            posting.post_journal(
                db,
                UUID(loan_id),
                "penalty",
                uuid4().hex,
                day,
                [
                    ("PENALTY_RECEIVABLE", "debit", amount, UUID(schedule["id"]), None),
                    ("PENALTY_INCOME", "credit", amount, UUID(schedule["id"]), None),
                ],
                description="Test recognized penalty",
            )
    result = repay(client, loan_id, payment(160))
    assert result.status_code == 201, result.text
    assert [
        (a["schedule_id"], a["component"], a["amount_paise"])
        for a in result.json()["allocations"]
    ] == [
        (schedules[1]["id"], "penalty", 30),
        (schedules[0]["id"], "penalty", 20),
        (schedules[0]["id"], "interest", 100),
        (schedules[0]["id"], "principal", 10),
    ]
    assert balances(client, loan_id) == (9990, 0, 0)
    assert_journals_balance(client, loan_id)


def test_schedule_loan_and_audit_history_immutable(client, db):
    loan_id = make_loan(client)
    schedule = db.scalar(
        select(RepaymentSchedule).where(RepaymentSchedule.loan_id == UUID(loan_id))
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        schedule.principal_due_paise = 1
        db.flush()
    loan = db.get(Loan, UUID(loan_id))
    with pytest.raises(IntegrityError), db.begin_nested():
        loan.principal_paise = 1
        db.flush()
    audit = db.scalar(select(AuditEvent))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.delete(audit)
        db.flush()


def test_disbursement_failure_rolls_back_status_journal_and_audit(
    client, db, monkeypatch
):
    loan_id = make_loan(client, disburse=False)
    before = counts(db)
    db.rollback()
    real = posting.audit

    def fail(*args, **kwargs):
        real(*args, **kwargs)
        if args[3] == "loan.disbursed":
            raise RuntimeError("Injected disbursement failure")

    monkeypatch.setattr(posting, "audit", fail)
    with pytest.raises(RuntimeError, match="Injected disbursement failure"):
        client.post(
            f"/loans/{loan_id}/disburse",
            json={"business_date": "2026-01-01"},
            headers=MANAGER,
        )
    assert counts(db) == before
    db.rollback()
    assert client.get(f"/loans/{loan_id}").json()["status"] == "originated"
    assert balances(client, loan_id) == (0, 0, 0)


def test_balanced_but_inexact_reversal_rejected_by_database(client, db):
    loan_id = make_loan(client)
    original = repay(client, loan_id, payment(1000)).json()
    with pytest.raises(IntegrityError), db.begin_nested():
        posting.lock_loan(db, UUID(loan_id))
        # Balanced is necessary but insufficient: this is NOT the exact opposite receipt.
        posting.post_journal(
            db,
            UUID(loan_id),
            "reversal",
            "wrong-reversal",
            date(2026, 1, 31),
            [
                ("CASH", "credit", 1, None, None),
                ("LOAN_PRINCIPAL_RECEIVABLE", "debit", 1, None, None),
            ],
            reversal_of_id=UUID(original["journal_id"]),
            description="Invalid",
        )
    db.rollback()
    assert balances(client, loan_id) == (9100, 0, 0)


def test_receivable_cannot_reference_other_loan(client, db):
    loan_id, other = make_loan(client), make_loan(client)
    schedule_id = UUID(client.get(f"/loans/{other}/schedule").json()[0]["id"])
    with pytest.raises(IntegrityError), db.begin_nested():
        posting.lock_loan(db, UUID(loan_id))
        posting.post_journal(
            db,
            UUID(loan_id),
            "penalty",
            "cross-loan",
            date(2026, 1, 10),
            [
                ("PENALTY_RECEIVABLE", "debit", 10, schedule_id, None),
                ("PENALTY_INCOME", "credit", 10, schedule_id, None),
            ],
        )


def test_missing_demo_header_is_denied_and_audited(client, db):
    original = client.headers.pop("X-Demo-User")
    try:
        assert client.get("/loan-products").status_code == 403
    finally:
        client.headers["X-Demo-User"] = original
    event = db.scalar(
        select(AuditEvent).where(AuditEvent.action == "authorization.denied")
    )
    assert event.actor_user_id is None
    assert event.details["reason"] == "missing_or_inactive_identity"


def test_penalty_and_interest_reversal_restore_recognized_lots(client, db):
    loan_id = make_loan(client)
    schedule_id = UUID(client.get(f"/loans/{loan_id}/schedule").json()[0]["id"])
    with db.begin():
        posting.lock_loan(db, UUID(loan_id))
        posting.post_journal(
            db,
            UUID(loan_id),
            "penalty",
            "recognized-penalty",
            date(2026, 1, 10),
            [
                ("PENALTY_RECEIVABLE", "debit", 50, schedule_id, None),
                ("PENALTY_INCOME", "credit", 50, schedule_id, None),
            ],
        )
    original = repay(client, loan_id, payment(200)).json()
    assert balances(client, loan_id) == (9950, 0, 0)
    response = client.post(
        f"/loans/{loan_id}/journals/{original['journal_id']}/reverse",
        json={"business_date": "2026-01-31", "reason": "Restore all components"},
        headers=MANAGER,
    )
    assert response.status_code == 200, response.text
    assert balances(client, loan_id) == (10000, 100, 50)
    repeated = repay(client, loan_id, payment(200))
    assert repeated.status_code == 201, repeated.text
    assert [
        (a["component"], a["amount_paise"]) for a in repeated.json()["allocations"]
    ] == [("penalty", 50), ("interest", 100), ("principal", 50)]
    assert_journals_balance(client, loan_id)


def test_reversal_of_earlier_payment_preserves_later_allocations(client):
    loan_id = make_loan(client)
    first = repay(client, loan_id, payment(6000)).json()
    assert repay(client, loan_id, payment(3000)).status_code == 201
    assert balances(client, loan_id) == (1100, 0, 0)
    response = client.post(
        f"/loans/{loan_id}/journals/{first['journal_id']}/reverse",
        json={"business_date": "2026-02-01", "reason": "Earlier settlement reversed"},
        headers=MANAGER,
    )
    assert response.status_code == 200, response.text
    assert balances(client, loan_id) == (7000, 100, 0)
    assert repay(client, loan_id, payment(7100, day="2026-02-01")).status_code == 201
    assert balances(client, loan_id) == (0, 0, 0)
    original = client.get(f"/loans/{loan_id}/schedule").json()
    active = [
        r
        for r in client.get(f"/loans/{loan_id}/repayments").json()
        if r["status"] == "posted"
    ]
    for row in original:
        assert (
            sum(
                a["amount_paise"]
                for r in active
                for a in r["allocations"]
                if a["schedule_id"] == row["id"] and a["component"] == "principal"
            )
            == row["principal_due_paise"]
        )
    assert_journals_balance(client, loan_id)


def test_receipt_allocation_chart_and_completed_response_are_immutable(client, db):
    from ledgercore.models.entities import LedgerAccount

    loan_id = make_loan(client)
    receipt = repay(client, loan_id, payment(1000)).json()
    models = [
        (db.get(Repayment, UUID(receipt["id"])), "amount_paise", 1),
        (db.scalar(select(RepaymentAllocation)), "amount_paise", 1),
        (
            db.scalar(select(LedgerAccount).where(LedgerAccount.code == "CASH")),
            "code",
            "HIDDEN-CASH",
        ),
        (db.scalar(select(IdempotencyRequest)), "response_body", {"fake": True}),
    ]
    for record, field, value in models:
        with pytest.raises(IntegrityError), db.begin_nested():
            setattr(record, field, value)
            db.flush()
