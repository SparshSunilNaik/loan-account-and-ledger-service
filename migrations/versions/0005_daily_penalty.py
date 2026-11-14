"""Daily overdue penalty identities including zero-charge evaluation history."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "accrual_records", "journal_id", existing_type=sa.Uuid(), nullable=True
    )
    op.add_column(
        "accrual_records", sa.Column("basis_paise", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "accrual_records", sa.Column("daily_rate", sa.Numeric(12, 10), nullable=True)
    )
    op.drop_constraint("accrual_kind", "accrual_records", type_="check")
    op.create_check_constraint(
        "accrual_kind",
        "accrual_records",
        "kind IN ('scheduled_interest','overdue_interest','overdue_penalty')",
    )
    op.create_check_constraint(
        "daily_penalty_policy",
        "accrual_records",
        "kind <> 'overdue_penalty' OR (period_end = period_start + 1 AND basis_paise IS NOT NULL AND basis_paise BETWEEN 0 AND 100000000000 AND daily_rate = 0.0005 AND daily_rate IS NOT NULL AND ((amount_paise = 0 AND journal_id IS NULL) OR (amount_paise > 0 AND journal_id IS NOT NULL)))",
    )
    op.create_check_constraint(
        "nonpenalty_journal",
        "accrual_records",
        "kind = 'overdue_penalty' OR journal_id IS NOT NULL",
    )
    op.execute("""
    CREATE TRIGGER immutable_accrual BEFORE UPDATE OR DELETE ON accrual_records
    FOR EACH ROW EXECUTE FUNCTION immutable_history();
    CREATE FUNCTION validate_daily_penalty() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.kind = 'overdue_penalty' THEN
            IF NOT EXISTS (SELECT 1 FROM repayment_schedules WHERE id = NEW.schedule_id
                AND loan_id = NEW.loan_id AND due_date < NEW.period_start) THEN
                RAISE EXCEPTION 'Penalty requires overdue schedule' USING ERRCODE = '23514';
            END IF;
            IF NEW.amount_paise <> floor(NEW.basis_paise::numeric * 0.0005 + 0.5) THEN
                RAISE EXCEPTION 'Invalid daily penalty rounding' USING ERRCODE = '23514';
            END IF;
            IF NEW.journal_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM ledger_journals j WHERE j.id = NEW.journal_id
                AND j.loan_id = NEW.loan_id AND j.kind = 'penalty' AND j.status = 'posted'
                AND j.business_date >= NEW.period_start
            ) THEN
                RAISE EXCEPTION 'Invalid penalty journal' USING ERRCODE = '23514';
            END IF;
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER daily_penalty_integrity BEFORE INSERT ON accrual_records
    FOR EACH ROW EXECUTE FUNCTION validate_daily_penalty();
    """)


def downgrade():
    # Null-journal evaluations cannot be represented in the old schema; fail rather than erase history.
    op.execute(
        "DROP TRIGGER daily_penalty_integrity ON accrual_records; DROP FUNCTION validate_daily_penalty(); DROP TRIGGER immutable_accrual ON accrual_records;"
    )
    op.drop_constraint("nonpenalty_journal", "accrual_records", type_="check")
    op.drop_constraint("daily_penalty_policy", "accrual_records", type_="check")
    op.drop_constraint("accrual_kind", "accrual_records", type_="check")
    op.create_check_constraint(
        "accrual_kind",
        "accrual_records",
        "kind IN ('scheduled_interest','overdue_interest')",
    )
    op.drop_column("accrual_records", "daily_rate")
    op.drop_column("accrual_records", "basis_paise")
    op.alter_column(
        "accrual_records", "journal_id", existing_type=sa.Uuid(), nullable=False
    )
