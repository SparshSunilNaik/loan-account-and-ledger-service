"""Exercise database protections directly, without future posting services."""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ledgercore.models.entities import (
    AccrualRecord,
    AuditEvent,
    Borrower,
    IdempotencyRequest,
    LedgerAccount,
    LedgerEntry,
    LedgerJournal,
    Loan,
    Repayment,
    RepaymentAllocation,
    RepaymentSchedule,
)
from ledgercore.schemas.api import LoanCreate
from ledgercore.services.origination import originate

pytestmark = pytest.mark.integration


@pytest.fixture
def loan(db):
    b = Borrower(external_reference="DB-B", full_name="Test")
    db.add(b)
    db.flush()
    result = originate(
        db,
        LoanCreate(
            external_reference="DB-L",
            borrower_id=b.id,
            product_id=UUID("00000000-0000-0000-0000-000000000002"),
            principal_paise=10000,
            tenure_periods=2,
            first_due_date=date(2026, 1, 31),
        ),
    )
    db.flush()
    return result


def journal(db, loan, key="J-1", kind="disbursement", **kwargs):
    result = LedgerJournal(
        loan_id=loan.id,
        kind=kind,
        event_key=key,
        effective_at=datetime.now(UTC),
        description="Schema test",
        **kwargs,
    )
    db.add(result)
    db.flush()
    return result


def balanced(db, loan):
    j = journal(db, loan)
    accounts = [
        LedgerAccount(code="CASH", name="Cash", account_type="asset"),
        LedgerAccount(
            code="PRINCIPAL", name="Principal receivable", account_type="asset"
        ),
    ]
    db.add_all(accounts)
    db.flush()
    entries = [
        LedgerEntry(journal_id=j.id, account_id=a.id, amount_paise=10000, direction=d)
        for a, d in zip(accounts, ["debit", "credit"], strict=True)
    ]
    db.add_all(entries)
    db.flush()
    return j, entries


@pytest.mark.parametrize(
    "mutation",
    [
        "journal_update",
        "journal_delete",
        "entry_update",
        "entry_delete",
        "entry_insert",
        "entry_move",
    ],
)
def test_posted_immutability(db, loan, mutation):
    j, entries = balanced(db, loan)
    other = journal(db, loan, "other", "repayment")
    j.status, j.posted_at = "posted", datetime.now(UTC)
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        if mutation == "journal_update":
            j.description = "Silently changed"
        elif mutation == "journal_delete":
            db.delete(j)
        elif mutation == "entry_update":
            entries[0].amount_paise = 9999
        elif mutation == "entry_delete":
            db.delete(entries[0])
        elif mutation == "entry_move":
            entries[0].journal_id = other.id
        else:
            db.add(
                LedgerEntry(
                    journal_id=j.id,
                    account_id=entries[0].account_id,
                    amount_paise=1,
                    direction="credit",
                )
            )
        db.flush()


@pytest.mark.parametrize("empty", [False, True])
def test_unbalanced_posting_rejected(db, loan, empty):
    j, entries = balanced(db, loan)
    if empty:
        for entry in entries:
            db.delete(entry)
    else:
        entries[0].amount_paise = 9999
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        j.status, j.posted_at = "posted", datetime.now(UTC)
        db.flush()


def test_single_disbursement_and_unique_event(db, loan):
    journal(db, loan)
    with pytest.raises(IntegrityError), db.begin_nested():
        journal(db, loan, "J-2")
    with pytest.raises(IntegrityError), db.begin_nested():
        journal(db, loan, "J-1", "repayment")


def test_reversal_reference_only_once(db, loan):
    j, _ = balanced(db, loan)
    j.status, j.posted_at = "posted", datetime.now(UTC)
    db.flush()
    journal(db, loan, "R-1", "reversal", reversal_of_id=j.id)
    with pytest.raises(IntegrityError), db.begin_nested():
        journal(db, loan, "R-2", "reversal", reversal_of_id=j.id)


def test_repayment_deduplication_and_amount(db, loan):
    def add(amount=100, event="E-1"):
        db.add(
            Repayment(
                loan_id=loan.id,
                source="synthetic",
                external_event_id=event,
                amount_paise=amount,
                occurred_at=datetime.now(UTC),
            )
        )
        db.flush()

    add()
    with pytest.raises(IntegrityError), db.begin_nested():
        add()
    for amount in [0, -1, 100000000001]:
        with pytest.raises(IntegrityError), db.begin_nested():
            add(amount, str(amount))


def test_idempotency_scope_uniqueness(db):
    def add(scope):
        db.add(
            IdempotencyRequest(
                scope=scope, key="same-key", request_hash="a" * 64, status="pending"
            )
        )
        db.flush()

    add("principal-A:repayment")
    add("principal-B:repayment")
    with pytest.raises(IntegrityError), db.begin_nested():
        add("principal-A:repayment")


def test_accrual_period_uniqueness(db, loan):
    schedule = db.scalar(
        select(RepaymentSchedule)
        .where(RepaymentSchedule.loan_id == loan.id)
        .order_by(RepaymentSchedule.instalment_number)
    )

    def add(key, kind, start, end):
        j = journal(db, loan, key, kind)
        db.add(
            AccrualRecord(
                loan_id=loan.id,
                schedule_id=schedule.id,
                kind=kind,
                period_start=start,
                period_end=end,
                amount_paise=100,
                journal_id=j.id,
            )
        )
        db.flush()

    add("A1", "scheduled_interest", date(2026, 1, 1), date(2026, 2, 1))
    with pytest.raises(IntegrityError), db.begin_nested():
        add("A2", "scheduled_interest", date(2026, 2, 1), date(2026, 3, 1))
    add("A3", "overdue_interest", date(2026, 2, 1), date(2026, 2, 2))
    with pytest.raises(IntegrityError), db.begin_nested():
        add("A4", "overdue_interest", date(2026, 2, 1), date(2026, 2, 2))


def test_allocation_cannot_cross_loans(db, loan):
    schedule = db.scalar(
        select(RepaymentSchedule).where(RepaymentSchedule.loan_id == loan.id)
    )
    other = Loan(
        external_reference="OTHER",
        borrower_id=loan.borrower_id,
        product_id=loan.product_id,
        principal_paise=1000,
        tenure_periods=1,
        first_due_date=date(2026, 1, 1),
        annual_rate=0,
        frequency="monthly",
        interest_method="flat",
    )
    db.add(other)
    db.flush()
    repayment = Repayment(
        loan_id=other.id,
        source="test",
        external_event_id="R",
        amount_paise=100,
        occurred_at=datetime.now(UTC),
    )
    db.add(repayment)
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            RepaymentAllocation(
                loan_id=loan.id,
                repayment_id=repayment.id,
                schedule_id=schedule.id,
                component="principal",
                amount_paise=100,
            )
        )
        db.flush()


def test_origination_is_atomic_on_schedule_failure(db, loan):
    before = {
        m: db.scalar(select(func.count()).select_from(m))
        for m in [Loan, RepaymentSchedule, AuditEvent]
    }
    with pytest.raises(IntegrityError), db.begin_nested():
        result = originate(
            db,
            LoanCreate(
                external_reference="ROLLBACK",
                borrower_id=loan.borrower_id,
                product_id=loan.product_id,
                principal_paise=1000,
                tenure_periods=2,
                first_due_date=date(2026, 1, 1),
            ),
        )
        db.flush()
        db.add(
            RepaymentSchedule(
                loan_id=result.id,
                instalment_number=1,
                due_date=date(2026, 1, 1),
                principal_due_paise=1,
                interest_due_paise=0,
            )
        )
        db.flush()
    assert {m: db.scalar(select(func.count()).select_from(m)) for m in before} == before


def test_foreign_keys_and_nonnegative_schedule(db, loan):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            RepaymentSchedule(
                loan_id=uuid4(),
                instalment_number=1,
                due_date=date(2026, 1, 1),
                principal_due_paise=1,
                interest_due_paise=0,
            )
        )
        db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            RepaymentSchedule(
                loan_id=loan.id,
                instalment_number=3,
                due_date=date(2026, 1, 1),
                principal_due_paise=-1,
                interest_due_paise=0,
            )
        )
        db.flush()
