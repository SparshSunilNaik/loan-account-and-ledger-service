"""Seed configurable products; protect posted journal history."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "3b4f5702cf1f"
branch_labels = None
depends_on = None


def upgrade():
    products = sa.table(
        "loan_products",
        sa.column("id", sa.Uuid),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("annual_rate", sa.Numeric),
        sa.column("interest_method", sa.String),
        sa.column("frequency", sa.String),
    )
    from decimal import Decimal
    from uuid import UUID

    op.bulk_insert(
        products,
        [
            dict(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                code="WEEKLY_GROUP",
                name="Weekly Group Loan",
                annual_rate=Decimal("0.24"),
                interest_method="flat",
                frequency="weekly",
            ),
            dict(
                id=UUID("00000000-0000-0000-0000-000000000002"),
                code="PERSONAL_EMI",
                name="Personal EMI Loan",
                annual_rate=Decimal("0.12"),
                interest_method="reducing",
                frequency="monthly",
            ),
            dict(
                id=UUID("00000000-0000-0000-0000-000000000003"),
                code="SMALL_BUSINESS",
                name="Small Business Loan",
                annual_rate=Decimal("0.18"),
                interest_method="flat",
                frequency="monthly",
            ),
        ],
    )
    op.execute("""
        CREATE FUNCTION guard_posted_journal() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.status = 'posted' THEN
                RAISE EXCEPTION 'Posted journals are immutable' USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER immutable_posted_journal BEFORE UPDATE OR DELETE ON ledger_journals
        FOR EACH ROW EXECUTE FUNCTION guard_posted_journal();

        CREATE FUNCTION guard_posted_entry() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP IN ('UPDATE','DELETE') THEN
                IF EXISTS (SELECT 1 FROM ledger_journals WHERE id = OLD.journal_id AND status = 'posted') THEN
                    RAISE EXCEPTION 'Posted entries are immutable' USING ERRCODE = '23514';
                END IF;
            END IF;
            IF TG_OP IN ('INSERT','UPDATE') THEN
                IF EXISTS (SELECT 1 FROM ledger_journals WHERE id = NEW.journal_id AND status = 'posted') THEN
                    RAISE EXCEPTION 'Cannot add entries to posted journal' USING ERRCODE = '23514';
                END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER immutable_posted_entry BEFORE INSERT OR UPDATE OR DELETE ON ledger_entries
        FOR EACH ROW EXECUTE FUNCTION guard_posted_entry();

        CREATE FUNCTION validate_posted_journal() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE entry_count bigint; net numeric;
        BEGIN
            IF NEW.status = 'posted' THEN
                SELECT count(*), coalesce(sum(CASE direction WHEN 'debit' THEN amount_paise ELSE -amount_paise END), 0)
                INTO entry_count, net FROM ledger_entries WHERE journal_id = NEW.id;
                IF entry_count < 2 OR net <> 0 THEN
                    RAISE EXCEPTION 'Posted journal must have balanced entries' USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER balanced_posted_journal BEFORE INSERT OR UPDATE ON ledger_journals
        FOR EACH ROW EXECUTE FUNCTION validate_posted_journal();
    """)


def downgrade():
    op.execute(
        "DROP TRIGGER balanced_posted_journal ON ledger_journals; DROP FUNCTION validate_posted_journal();"
    )
    op.execute(
        "DROP TRIGGER immutable_posted_entry ON ledger_entries; DROP FUNCTION guard_posted_entry();"
    )
    op.execute(
        "DROP TRIGGER immutable_posted_journal ON ledger_journals; DROP FUNCTION guard_posted_journal();"
    )
    op.execute(
        "DELETE FROM loan_products WHERE id IN ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000003')"
    )
