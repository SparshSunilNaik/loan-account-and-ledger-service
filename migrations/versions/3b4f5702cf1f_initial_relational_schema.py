"""initial relational schema"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "3b4f5702cf1f"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "borrowers",
        sa.Column("external_reference", sa.String(length=100), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_reference"),
    )
    op.create_table(
        "idempotency_requests",
        sa.Column("scope", sa.String(length=200), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column(
            "response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending','completed')", name="idempotency_status"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
    )
    op.create_table(
        "ledger_accounts",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column(
            "currency", sa.String(length=3), server_default="INR", nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "account_type IN ('asset','liability','equity','income','expense')",
            name="account_type",
        ),
        sa.CheckConstraint("currency = 'INR'", name="account_currency"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "loan_products",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("annual_rate", sa.Numeric(precision=12, scale=10), nullable=False),
        sa.Column("interest_method", sa.String(length=20), nullable=False),
        sa.Column("frequency", sa.String(length=10), nullable=False),
        sa.Column(
            "currency", sa.String(length=3), server_default="INR", nullable=False
        ),
        sa.CheckConstraint("currency = 'INR'", name="product_currency"),
        sa.CheckConstraint(
            "frequency IN ('weekly','monthly')", name="product_frequency"
        ),
        sa.CheckConstraint(
            "interest_method IN ('flat','reducing')", name="product_method"
        ),
        sa.CheckConstraint(
            "annual_rate >= 0 AND annual_rate <= 1", name="product_rate"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "users",
        sa.Column("external_subject", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('loan_officer','manager','auditor')", name="user_role"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_subject"),
    )
    op.create_table(
        "audit_events",
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("correlation_id", sa.String(length=200), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_events_action"), "audit_events", ["action"], unique=False
    )
    op.create_index(
        op.f("ix_audit_events_actor_user_id"),
        "audit_events",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_events_correlation_id"),
        "audit_events",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_events_entity_id"), "audit_events", ["entity_id"], unique=False
    )
    op.create_table(
        "loans",
        sa.Column("external_reference", sa.String(length=100), nullable=False),
        sa.Column("borrower_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("principal_paise", sa.BigInteger(), nullable=False),
        sa.Column("tenure_periods", sa.Integer(), nullable=False),
        sa.Column("first_due_date", sa.Date(), nullable=False),
        sa.Column(
            "schedule_version",
            sa.String(length=30),
            server_default="v1",
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=20), server_default="originated", nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("annual_rate", sa.Numeric(precision=12, scale=10), nullable=False),
        sa.Column("interest_method", sa.String(length=20), nullable=False),
        sa.Column("frequency", sa.String(length=10), nullable=False),
        sa.Column(
            "currency", sa.String(length=3), server_default="INR", nullable=False
        ),
        sa.CheckConstraint("currency = 'INR'", name="loan_currency"),
        sa.CheckConstraint("frequency IN ('weekly','monthly')", name="loan_frequency"),
        sa.CheckConstraint(
            "interest_method IN ('flat','reducing')", name="loan_method"
        ),
        sa.CheckConstraint(
            "status IN ('originated','disbursed','closed')", name="loan_status"
        ),
        sa.CheckConstraint("annual_rate >= 0 AND annual_rate <= 1", name="loan_rate"),
        sa.CheckConstraint(
            "principal_paise BETWEEN 1 AND 100000000000", name="loan_principal"
        ),
        sa.CheckConstraint("tenure_periods BETWEEN 1 AND 600", name="loan_tenure"),
        sa.ForeignKeyConstraint(
            ["borrower_id"],
            ["borrowers.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["loan_products.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_reference"),
    )
    op.create_index(
        op.f("ix_loans_borrower_id"), "loans", ["borrower_id"], unique=False
    )
    op.create_index(op.f("ix_loans_product_id"), "loans", ["product_id"], unique=False)
    op.create_table(
        "repayment_schedules",
        sa.Column("loan_id", sa.Uuid(), nullable=False),
        sa.Column("instalment_number", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("principal_due_paise", sa.BigInteger(), nullable=False),
        sa.Column("interest_due_paise", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("instalment_number > 0", name="schedule_number"),
        sa.CheckConstraint(
            "principal_due_paise BETWEEN 0 AND 100000000000 AND interest_due_paise BETWEEN 0 AND 100000000000",
            name="schedule_amounts",
        ),
        sa.ForeignKeyConstraint(
            ["loan_id"],
            ["loans.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "loan_id", name="uq_schedule_loan"),
        sa.UniqueConstraint(
            "loan_id", "instalment_number", name="uq_schedule_instalment"
        ),
    )
    op.create_index(
        op.f("ix_repayment_schedules_loan_id"),
        "repayment_schedules",
        ["loan_id"],
        unique=False,
    )
    op.create_index(
        "ix_schedule_due", "repayment_schedules", ["loan_id", "due_date"], unique=False
    )
    op.create_table(
        "repayments",
        sa.Column("loan_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("external_event_id", sa.String(length=200), nullable=False),
        sa.Column("idempotency_request_id", sa.Uuid(), nullable=True),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount_paise BETWEEN 1 AND 100000000000", name="repayment_amount"
        ),
        sa.ForeignKeyConstraint(
            ["idempotency_request_id"],
            ["idempotency_requests.id"],
        ),
        sa.ForeignKeyConstraint(
            ["loan_id"],
            ["loans.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "loan_id", name="uq_repayment_loan"),
        sa.UniqueConstraint("idempotency_request_id"),
        sa.UniqueConstraint(
            "source", "external_event_id", name="uq_repayment_source_event"
        ),
    )
    op.create_index(
        "ix_repayment_occurred", "repayments", ["loan_id", "occurred_at"], unique=False
    )
    op.create_index(
        op.f("ix_repayments_loan_id"), "repayments", ["loan_id"], unique=False
    )
    op.create_table(
        "ledger_journals",
        sa.Column("loan_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=10), server_default="draft", nullable=False
        ),
        sa.Column("event_key", sa.String(length=200), nullable=False),
        sa.Column("repayment_id", sa.Uuid(), nullable=True),
        sa.Column("reversal_of_id", sa.Uuid(), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(kind = 'reversal') = (reversal_of_id IS NOT NULL)",
            name="journal_reversal",
        ),
        sa.CheckConstraint(
            "(status = 'posted') = (posted_at IS NOT NULL)", name="journal_posted_at"
        ),
        sa.CheckConstraint(
            "kind IN ('disbursement','repayment','scheduled_interest','overdue_interest','reversal')",
            name="journal_kind",
        ),
        sa.CheckConstraint("status IN ('draft','posted')", name="journal_status"),
        sa.CheckConstraint(
            "reversal_of_id IS NULL OR reversal_of_id <> id",
            name="journal_no_self_reversal",
        ),
        sa.ForeignKeyConstraint(
            ["loan_id"],
            ["loans.id"],
        ),
        sa.ForeignKeyConstraint(
            ["repayment_id"],
            ["repayments.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reversal_of_id"],
            ["ledger_journals.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key"),
        sa.UniqueConstraint("repayment_id"),
        sa.UniqueConstraint("reversal_of_id"),
    )
    op.create_index(
        op.f("ix_ledger_journals_loan_id"), "ledger_journals", ["loan_id"], unique=False
    )
    op.create_index(
        "uq_single_disbursement",
        "ledger_journals",
        ["loan_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'disbursement'"),
    )
    op.create_table(
        "repayment_allocations",
        sa.Column("loan_id", sa.Uuid(), nullable=False),
        sa.Column("repayment_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("component", sa.String(length=20), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "component IN ('penalty','interest','principal')",
            name="allocation_component",
        ),
        sa.CheckConstraint(
            "amount_paise BETWEEN 1 AND 100000000000", name="allocation_amount"
        ),
        sa.ForeignKeyConstraint(
            ["loan_id"],
            ["loans.id"],
        ),
        sa.ForeignKeyConstraint(
            ["repayment_id", "loan_id"],
            ["repayments.id", "repayments.loan_id"],
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id", "loan_id"],
            ["repayment_schedules.id", "repayment_schedules.loan_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repayment_id", "schedule_id", "component", name="uq_allocation_component"
        ),
    )
    op.create_index(
        op.f("ix_repayment_allocations_loan_id"),
        "repayment_allocations",
        ["loan_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repayment_allocations_repayment_id"),
        "repayment_allocations",
        ["repayment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repayment_allocations_schedule_id"),
        "repayment_allocations",
        ["schedule_id"],
        unique=False,
    )
    op.create_table(
        "accrual_records",
        sa.Column("loan_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("journal_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('scheduled_interest','overdue_interest')", name="accrual_kind"
        ),
        sa.CheckConstraint(
            "amount_paise BETWEEN 0 AND 100000000000", name="accrual_amount"
        ),
        sa.CheckConstraint("period_end > period_start", name="accrual_period"),
        sa.ForeignKeyConstraint(
            ["journal_id"],
            ["ledger_journals.id"],
        ),
        sa.ForeignKeyConstraint(
            ["loan_id"],
            ["loans.id"],
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id", "loan_id"],
            ["repayment_schedules.id", "repayment_schedules.loan_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("journal_id"),
        sa.UniqueConstraint(
            "loan_id",
            "schedule_id",
            "kind",
            "period_start",
            "period_end",
            name="uq_accrual_period",
        ),
    )
    op.create_index(
        op.f("ix_accrual_records_loan_id"), "accrual_records", ["loan_id"], unique=False
    )
    op.create_index(
        op.f("ix_accrual_records_schedule_id"),
        "accrual_records",
        ["schedule_id"],
        unique=False,
    )
    op.create_index(
        "uq_scheduled_recognition",
        "accrual_records",
        ["schedule_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'scheduled_interest'"),
    )
    op.create_table(
        "ledger_entries",
        sa.Column("journal_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("direction", sa.String(length=6), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("direction IN ('debit','credit')", name="entry_direction"),
        sa.CheckConstraint(
            "amount_paise BETWEEN 1 AND 100000000000", name="entry_amount"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["ledger_accounts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["journal_id"],
            ["ledger_journals.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ledger_entries_account_id"),
        "ledger_entries",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ledger_entries_journal_id"),
        "ledger_entries",
        ["journal_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_ledger_entries_journal_id"), table_name="ledger_entries")
    op.drop_index(op.f("ix_ledger_entries_account_id"), table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index(
        "uq_scheduled_recognition",
        table_name="accrual_records",
        postgresql_where=sa.text("kind = 'scheduled_interest'"),
    )
    op.drop_index(op.f("ix_accrual_records_schedule_id"), table_name="accrual_records")
    op.drop_index(op.f("ix_accrual_records_loan_id"), table_name="accrual_records")
    op.drop_table("accrual_records")
    op.drop_index(
        op.f("ix_repayment_allocations_schedule_id"), table_name="repayment_allocations"
    )
    op.drop_index(
        op.f("ix_repayment_allocations_repayment_id"),
        table_name="repayment_allocations",
    )
    op.drop_index(
        op.f("ix_repayment_allocations_loan_id"), table_name="repayment_allocations"
    )
    op.drop_table("repayment_allocations")
    op.drop_index(
        "uq_single_disbursement",
        table_name="ledger_journals",
        postgresql_where=sa.text("kind = 'disbursement'"),
    )
    op.drop_index(op.f("ix_ledger_journals_loan_id"), table_name="ledger_journals")
    op.drop_table("ledger_journals")
    op.drop_index(op.f("ix_repayments_loan_id"), table_name="repayments")
    op.drop_index("ix_repayment_occurred", table_name="repayments")
    op.drop_table("repayments")
    op.drop_index("ix_schedule_due", table_name="repayment_schedules")
    op.drop_index(
        op.f("ix_repayment_schedules_loan_id"), table_name="repayment_schedules"
    )
    op.drop_table("repayment_schedules")
    op.drop_index(op.f("ix_loans_product_id"), table_name="loans")
    op.drop_index(op.f("ix_loans_borrower_id"), table_name="loans")
    op.drop_table("loans")
    op.drop_index(op.f("ix_audit_events_entity_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_correlation_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_actor_user_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_action"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("users")
    op.drop_table("loan_products")
    op.drop_table("ledger_accounts")
    op.drop_table("idempotency_requests")
    op.drop_table("borrowers")
