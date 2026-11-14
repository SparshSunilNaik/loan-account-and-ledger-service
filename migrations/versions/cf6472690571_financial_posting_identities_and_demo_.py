"""financial posting identities and demo accounts"""

import sqlalchemy as sa
from alembic import op

revision = "cf6472690571"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ledger_entries", sa.Column("schedule_id", sa.Uuid(), nullable=True))
    op.add_column(
        "ledger_entries", sa.Column("receivable_origin_id", sa.Uuid(), nullable=True)
    )
    op.create_index(
        op.f("ix_ledger_entries_receivable_origin_id"),
        "ledger_entries",
        ["receivable_origin_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ledger_entries_schedule_id"),
        "ledger_entries",
        ["schedule_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_entry_schedule",
        "ledger_entries",
        "repayment_schedules",
        ["schedule_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_entry_origin",
        "ledger_entries",
        "ledger_entries",
        ["receivable_origin_id"],
        ["id"],
    )
    op.add_column(
        "ledger_journals",
        sa.Column(
            "business_date",
            sa.Date(),
            server_default=sa.text("CURRENT_DATE"),
            nullable=False,
        ),
    )
    op.add_column(
        "repayments",
        sa.Column(
            "business_date",
            sa.Date(),
            server_default=sa.text("CURRENT_DATE"),
            nullable=False,
        ),
    )
    op.add_column(
        "repayments", sa.Column("request_hash", sa.String(length=64), nullable=True)
    )
    # Table DDL holds exclusive locks throughout this transactional migration.
    # Backfill UTC business dates without treating metadata migration as a journal edit.
    op.execute("ALTER TABLE ledger_journals DISABLE TRIGGER immutable_posted_journal")
    op.execute(
        "UPDATE ledger_journals SET business_date = (effective_at AT TIME ZONE 'UTC')::date"
    )
    op.execute("ALTER TABLE ledger_journals ENABLE TRIGGER immutable_posted_journal")
    op.execute(
        "UPDATE repayments SET business_date = (received_at AT TIME ZONE 'UTC')::date"
    )

    op.drop_constraint("journal_kind", "ledger_journals", type_="check")
    op.create_check_constraint(
        "journal_kind",
        "ledger_journals",
        "kind IN ('disbursement','repayment','scheduled_interest','overdue_interest','penalty','reversal')",
    )
    for number, (code, account_type) in enumerate(
        [
            ("CASH", "asset"),
            ("LOAN_PRINCIPAL_RECEIVABLE", "asset"),
            ("INTEREST_RECEIVABLE", "asset"),
            ("INTEREST_INCOME", "income"),
            ("PENALTY_RECEIVABLE", "asset"),
            ("PENALTY_INCOME", "income"),
        ],
        start=1,
    ):
        op.execute(
            sa.text(
                "INSERT INTO ledger_accounts (id, code, name, account_type) VALUES (CAST(:id AS uuid), :code, :name, :account_type) ON CONFLICT (code) DO NOTHING"
            ).bindparams(
                id=f"10000000-0000-0000-0000-{number:012d}",
                code=code,
                name=code.replace("_", " ").title(),
                account_type=account_type,
            )
        )
    for number, (subject, role) in enumerate(
        [
            ("demo-officer", "loan_officer"),
            ("demo-manager", "manager"),
            ("demo-auditor", "auditor"),
        ],
        start=1,
    ):
        op.execute(
            sa.text(
                "INSERT INTO users (id, external_subject, role) VALUES (CAST(:id AS uuid), :subject, :role) ON CONFLICT (external_subject) DO NOTHING"
            ).bindparams(
                id=f"20000000-0000-0000-0000-{number:012d}", subject=subject, role=role
            )
        )


def downgrade():
    # Seed identities/accounts remain on downgrade: financial history may reference them.
    op.drop_constraint("journal_kind", "ledger_journals", type_="check")
    op.create_check_constraint(
        "journal_kind",
        "ledger_journals",
        "kind IN ('disbursement','repayment','scheduled_interest','overdue_interest','reversal')",
    )
    op.drop_column("repayments", "request_hash")
    op.drop_column("repayments", "business_date")
    op.drop_column("ledger_journals", "business_date")
    op.drop_constraint("fk_entry_origin", "ledger_entries", type_="foreignkey")
    op.drop_constraint("fk_entry_schedule", "ledger_entries", type_="foreignkey")
    op.drop_index(op.f("ix_ledger_entries_schedule_id"), table_name="ledger_entries")
    op.drop_index(
        op.f("ix_ledger_entries_receivable_origin_id"), table_name="ledger_entries"
    )
    op.drop_column("ledger_entries", "receivable_origin_id")
    op.drop_column("ledger_entries", "schedule_id")
