"""Protect financial history and validate receivable and reversal linkage."""

from alembic import op

revision = "0004"
down_revision = "cf6472690571"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE OR REPLACE FUNCTION guard_posted_entry() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE journal_row record;
    BEGIN
        -- Entry changes and posting a journal serialize on the journal row too.
        FOR journal_row IN SELECT id, status FROM ledger_journals
            WHERE id IN (CASE WHEN TG_OP <> 'INSERT' THEN OLD.journal_id END,
                         CASE WHEN TG_OP <> 'DELETE' THEN NEW.journal_id END)
            ORDER BY id FOR UPDATE
        LOOP
            IF journal_row.status = 'posted' THEN
                RAISE EXCEPTION 'Posted entries are immutable' USING ERRCODE = '23514';
            END IF;
        END LOOP;
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END $$;

    CREATE FUNCTION validate_entry_links() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE entry_loan uuid;
    BEGIN
        SELECT loan_id INTO entry_loan FROM ledger_journals WHERE id = NEW.journal_id;
        IF NEW.schedule_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM repayment_schedules WHERE id = NEW.schedule_id AND loan_id = entry_loan
        ) THEN
            RAISE EXCEPTION 'Schedule and journal must belong to same loan' USING ERRCODE = '23514';
        END IF;
        IF NEW.receivable_origin_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM ledger_entries e JOIN ledger_journals j ON j.id = e.journal_id
            WHERE e.id = NEW.receivable_origin_id AND e.direction = 'debit'
              AND e.receivable_origin_id IS NULL AND e.account_id = NEW.account_id
              AND e.schedule_id IS NOT NULL AND e.schedule_id = NEW.schedule_id
              AND j.loan_id = entry_loan AND j.status = 'posted'
        ) THEN
            RAISE EXCEPTION 'Invalid recognized receivable origin' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER entry_linkage BEFORE INSERT OR UPDATE ON ledger_entries
    FOR EACH ROW EXECUTE FUNCTION validate_entry_links();

    CREATE FUNCTION validate_reversal() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.status = 'posted' AND NEW.kind = 'reversal' THEN
            IF NOT EXISTS (
                SELECT 1 FROM ledger_journals WHERE id = NEW.reversal_of_id
                AND kind = 'repayment' AND status = 'posted' AND loan_id = NEW.loan_id
                AND repayment_id IS NOT NULL
            ) THEN
                RAISE EXCEPTION 'Only same-loan posted repayment reversals are supported' USING ERRCODE = '23514';
            END IF;
            IF EXISTS (
                (SELECT account_id, amount_paise, schedule_id, receivable_origin_id, direction
                 FROM ledger_entries WHERE journal_id = NEW.reversal_of_id)
                EXCEPT ALL
                (SELECT account_id, amount_paise, schedule_id, receivable_origin_id,
                 CASE direction WHEN 'credit' THEN 'debit' ELSE 'credit' END
                 FROM ledger_entries WHERE journal_id = NEW.id)
            ) OR EXISTS (
                (SELECT account_id, amount_paise, schedule_id, receivable_origin_id,
                 CASE direction WHEN 'credit' THEN 'debit' ELSE 'credit' END
                 FROM ledger_entries WHERE journal_id = NEW.id)
                EXCEPT ALL
                (SELECT account_id, amount_paise, schedule_id, receivable_origin_id, direction
                 FROM ledger_entries WHERE journal_id = NEW.reversal_of_id)
            ) THEN
                RAISE EXCEPTION 'Reversal must contain exact opposite entries' USING ERRCODE = '23514';
            END IF;
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER reversal_integrity BEFORE INSERT OR UPDATE ON ledger_journals
    FOR EACH ROW EXECUTE FUNCTION validate_reversal();

    CREATE FUNCTION immutable_history() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'Financial history is immutable' USING ERRCODE = '23514';
    END $$;
    CREATE TRIGGER immutable_schedule BEFORE UPDATE OR DELETE ON repayment_schedules
    FOR EACH ROW EXECUTE FUNCTION immutable_history();
    CREATE TRIGGER immutable_receipt BEFORE UPDATE OR DELETE ON repayments
    FOR EACH ROW EXECUTE FUNCTION immutable_history();
    CREATE TRIGGER immutable_allocation BEFORE UPDATE OR DELETE ON repayment_allocations
    FOR EACH ROW EXECUTE FUNCTION immutable_history();
    CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION immutable_history();

    CREATE TRIGGER immutable_accounts BEFORE UPDATE OR DELETE ON ledger_accounts
    FOR EACH ROW EXECUTE FUNCTION immutable_history();

    CREATE FUNCTION guard_completed_request() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF OLD.status = 'completed' THEN
            RAISE EXCEPTION 'Completed idempotency results are immutable' USING ERRCODE = '23514';
        END IF;
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER immutable_completed_request BEFORE UPDATE OR DELETE ON idempotency_requests
    FOR EACH ROW EXECUTE FUNCTION guard_completed_request();

    CREATE FUNCTION immutable_loan_terms() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF (NEW.principal_paise, NEW.annual_rate, NEW.tenure_periods, NEW.frequency,
            NEW.interest_method, NEW.currency, NEW.first_due_date, NEW.schedule_version,
            NEW.borrower_id, NEW.product_id, NEW.external_reference)
            IS DISTINCT FROM
           (OLD.principal_paise, OLD.annual_rate, OLD.tenure_periods, OLD.frequency,
            OLD.interest_method, OLD.currency, OLD.first_due_date, OLD.schedule_version,
            OLD.borrower_id, OLD.product_id, OLD.external_reference) THEN
            RAISE EXCEPTION 'Originated loan terms are immutable' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER immutable_loan_terms BEFORE UPDATE ON loans
    FOR EACH ROW EXECUTE FUNCTION immutable_loan_terms();
    """)


def downgrade():
    op.execute("""
    DROP TRIGGER immutable_loan_terms ON loans;
    DROP FUNCTION immutable_loan_terms();
    DROP TRIGGER immutable_receipt ON repayments;
    DROP TRIGGER immutable_allocation ON repayment_allocations;
    DROP TRIGGER immutable_schedule ON repayment_schedules;
    DROP TRIGGER immutable_audit ON audit_events;
    DROP TRIGGER immutable_accounts ON ledger_accounts;
    DROP TRIGGER immutable_completed_request ON idempotency_requests;
    DROP FUNCTION guard_completed_request();
    DROP FUNCTION immutable_history();
    DROP TRIGGER reversal_integrity ON ledger_journals;
    DROP FUNCTION validate_reversal();
    DROP TRIGGER entry_linkage ON ledger_entries;
    DROP FUNCTION validate_entry_links();
    CREATE OR REPLACE FUNCTION guard_posted_entry() RETURNS trigger LANGUAGE plpgsql AS $$
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
    """)
