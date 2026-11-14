"""Relational records. No cached outstanding balances are stored."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Record:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Borrower(Record, Base):
    __tablename__ = "borrowers"
    external_reference: Mapped[str] = mapped_column(String(100), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(20))


class Terms:
    annual_rate: Mapped[Decimal] = mapped_column(Numeric(12, 10))
    interest_method: Mapped[str] = mapped_column(String(20))
    frequency: Mapped[str] = mapped_column(String(10))
    currency: Mapped[str] = mapped_column(String(3), server_default="INR")


def term_checks(prefix):
    return (
        CheckConstraint("annual_rate >= 0 AND annual_rate <= 1", name=f"{prefix}_rate"),
        CheckConstraint(
            "interest_method IN ('flat','reducing')", name=f"{prefix}_method"
        ),
        CheckConstraint(
            "frequency IN ('weekly','monthly')", name=f"{prefix}_frequency"
        ),
        CheckConstraint("currency = 'INR'", name=f"{prefix}_currency"),
    )


class LoanProduct(Record, Terms, Base):
    __tablename__ = "loan_products"
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(server_default=text("true"))
    __table_args__ = term_checks("product")


class Loan(Record, Terms, Base):
    __tablename__ = "loans"
    external_reference: Mapped[str] = mapped_column(String(100), unique=True)
    borrower_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("borrowers.id"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loan_products.id"), index=True
    )
    principal_paise: Mapped[int] = mapped_column(BigInteger)
    tenure_periods: Mapped[int] = mapped_column(Integer)
    first_due_date: Mapped[date]
    schedule_version: Mapped[str] = mapped_column(String(30), server_default="v1")
    status: Mapped[str] = mapped_column(String(20), server_default="originated")
    __table_args__ = (
        *term_checks("loan"),
        CheckConstraint(
            "principal_paise BETWEEN 1 AND 100000000000", name="loan_principal"
        ),
        CheckConstraint("tenure_periods BETWEEN 1 AND 600", name="loan_tenure"),
        CheckConstraint(
            "status IN ('originated','disbursed','closed')", name="loan_status"
        ),
    )


class RepaymentSchedule(Record, Base):
    __tablename__ = "repayment_schedules"
    loan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("loans.id"), index=True)
    instalment_number: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date]
    principal_due_paise: Mapped[int] = mapped_column(BigInteger)
    interest_due_paise: Mapped[int] = mapped_column(BigInteger)
    __table_args__ = (
        UniqueConstraint("loan_id", "instalment_number", name="uq_schedule_instalment"),
        UniqueConstraint("id", "loan_id", name="uq_schedule_loan"),
        CheckConstraint("instalment_number > 0", name="schedule_number"),
        CheckConstraint(
            "principal_due_paise BETWEEN 0 AND 100000000000 AND interest_due_paise BETWEEN 0 AND 100000000000",
            name="schedule_amounts",
        ),
        Index("ix_schedule_due", "loan_id", "due_date"),
    )


class User(Record, Base):
    __tablename__ = "users"
    external_subject: Mapped[str] = mapped_column(String(200), unique=True)
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(server_default=text("true"))
    __table_args__ = (
        CheckConstraint(
            "role IN ('loan_officer','manager','auditor')", name="user_role"
        ),
    )


class IdempotencyRequest(Record, Base):
    __tablename__ = "idempotency_requests"
    scope: Mapped[str] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    response_status: Mapped[int | None]
    response_body: Mapped[dict | None] = mapped_column(JSONB)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
        CheckConstraint("status IN ('pending','completed')", name="idempotency_status"),
    )


class Repayment(Record, Base):
    __tablename__ = "repayments"
    loan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("loans.id"), index=True)
    source: Mapped[str] = mapped_column(String(100))
    external_event_id: Mapped[str] = mapped_column(String(200))
    idempotency_request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("idempotency_requests.id"), unique=True
    )
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (
        UniqueConstraint(
            "source", "external_event_id", name="uq_repayment_source_event"
        ),
        UniqueConstraint("id", "loan_id", name="uq_repayment_loan"),
        CheckConstraint(
            "amount_paise BETWEEN 1 AND 100000000000", name="repayment_amount"
        ),
        Index("ix_repayment_occurred", "loan_id", "occurred_at"),
    )


class RepaymentAllocation(Record, Base):
    __tablename__ = "repayment_allocations"
    loan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("loans.id"), index=True)
    repayment_id: Mapped[uuid.UUID] = mapped_column(index=True)
    schedule_id: Mapped[uuid.UUID] = mapped_column(index=True)
    component: Mapped[str] = mapped_column(String(20))
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    __table_args__ = (
        ForeignKeyConstraint(
            ["repayment_id", "loan_id"], ["repayments.id", "repayments.loan_id"]
        ),
        ForeignKeyConstraint(
            ["schedule_id", "loan_id"],
            ["repayment_schedules.id", "repayment_schedules.loan_id"],
        ),
        UniqueConstraint(
            "repayment_id", "schedule_id", "component", name="uq_allocation_component"
        ),
        CheckConstraint(
            "component IN ('penalty','interest','principal')",
            name="allocation_component",
        ),
        CheckConstraint(
            "amount_paise BETWEEN 1 AND 100000000000", name="allocation_amount"
        ),
    )


class LedgerAccount(Record, Base):
    __tablename__ = "ledger_accounts"
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    account_type: Mapped[str] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3), server_default="INR")
    __table_args__ = (
        CheckConstraint("currency = 'INR'", name="account_currency"),
        CheckConstraint(
            "account_type IN ('asset','liability','equity','income','expense')",
            name="account_type",
        ),
    )


class LedgerJournal(Record, Base):
    __tablename__ = "ledger_journals"
    loan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("loans.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10), server_default="draft")
    event_key: Mapped[str] = mapped_column(String(200), unique=True)
    repayment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("repayments.id"), unique=True
    )
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ledger_journals.id"), unique=True
    )
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str] = mapped_column(String(500))
    __table_args__ = (
        CheckConstraint(
            "kind IN ('disbursement','repayment','scheduled_interest','overdue_interest','reversal')",
            name="journal_kind",
        ),
        CheckConstraint("status IN ('draft','posted')", name="journal_status"),
        CheckConstraint(
            "(status = 'posted') = (posted_at IS NOT NULL)", name="journal_posted_at"
        ),
        CheckConstraint(
            "(kind = 'reversal') = (reversal_of_id IS NOT NULL)",
            name="journal_reversal",
        ),
        CheckConstraint(
            "reversal_of_id IS NULL OR reversal_of_id <> id",
            name="journal_no_self_reversal",
        ),
        Index(
            "uq_single_disbursement",
            "loan_id",
            unique=True,
            postgresql_where=text("kind = 'disbursement'"),
        ),
    )


class LedgerEntry(Record, Base):
    __tablename__ = "ledger_entries"
    journal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_journals.id"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_accounts.id"), index=True
    )
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    direction: Mapped[str] = mapped_column(String(6))
    __table_args__ = (
        CheckConstraint("amount_paise BETWEEN 1 AND 100000000000", name="entry_amount"),
        CheckConstraint("direction IN ('debit','credit')", name="entry_direction"),
    )


class AccrualRecord(Record, Base):
    __tablename__ = "accrual_records"
    loan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("loans.id"), index=True)
    schedule_id: Mapped[uuid.UUID] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(20))
    period_start: Mapped[date]
    period_end: Mapped[date]
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    journal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_journals.id"), unique=True
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["schedule_id", "loan_id"],
            ["repayment_schedules.id", "repayment_schedules.loan_id"],
        ),
        UniqueConstraint(
            "loan_id",
            "schedule_id",
            "kind",
            "period_start",
            "period_end",
            name="uq_accrual_period",
        ),
        Index(
            "uq_scheduled_recognition",
            "schedule_id",
            unique=True,
            postgresql_where=text("kind = 'scheduled_interest'"),
        ),
        CheckConstraint(
            "kind IN ('scheduled_interest','overdue_interest')", name="accrual_kind"
        ),
        CheckConstraint("period_end > period_start", name="accrual_period"),
        CheckConstraint(
            "amount_paise BETWEEN 0 AND 100000000000", name="accrual_amount"
        ),
    )


class AuditEvent(Record, Base):
    __tablename__ = "audit_events"
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), index=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(200), index=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
