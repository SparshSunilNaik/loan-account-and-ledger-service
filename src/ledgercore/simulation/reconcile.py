"""Independent database reconciliation; never calls the production balance calculator."""

from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select

from ledgercore.models.entities import (
    AccrualRecord,
    Borrower,
    LedgerAccount,
    LedgerEntry,
    LedgerJournal,
    Loan,
    LoanProduct,
    Repayment,
    RepaymentAllocation,
    RepaymentSchedule,
)

CODES = {
    "LOAN_PRINCIPAL_RECEIVABLE": "principal",
    "INTEREST_RECEIVABLE": "interest",
    "PENALTY_RECEIVABLE": "penalty",
}


def reconcile(session, loan_map, manifest):
    loans = {loan.id: loan for loan in session.scalars(select(Loan))}
    schedules = {row.id: row for row in session.scalars(select(RepaymentSchedule))}
    journals = {
        row.id: row
        for row in session.scalars(
            select(LedgerJournal).where(LedgerJournal.status == "posted")
        )
    }
    entries = session.execute(
        select(LedgerEntry, LedgerAccount.code).join(
            LedgerAccount, LedgerAccount.id == LedgerEntry.account_id
        )
    ).all()
    receipts = {row.id: row for row in session.scalars(select(Repayment))}
    allocations = session.scalars(select(RepaymentAllocation)).all()
    accruals = session.scalars(select(AccrualRecord)).all()
    journal_entries, receipt_allocations = defaultdict(list), defaultdict(list)
    ledger, allocated, recognized = defaultdict(int), defaultdict(int), defaultdict(int)
    total_debit = total_credit = 0
    errors = []
    for entry, code in entries:
        if entry.journal_id not in journals:
            errors.append({"type": "draft_or_orphan_entry", "entry_id": str(entry.id)})
            continue
        journal_entries[entry.journal_id].append((entry, code))
        if entry.direction == "debit":
            total_debit += entry.amount_paise
        else:
            total_credit += entry.amount_paise
        if code in CODES:
            ledger[(journals[entry.journal_id].loan_id, CODES[code])] += (
                entry.amount_paise
                if entry.direction == "debit"
                else -entry.amount_paise
            )
    unbalanced = 0
    for journal in journals.values():
        lines = journal_entries[journal.id]
        net = sum(
            entry.amount_paise if entry.direction == "debit" else -entry.amount_paise
            for entry, _ in lines
        )
        if len(lines) < 2 or net != 0:
            unbalanced += 1
    reversed_journals = {
        j.reversal_of_id: j for j in journals.values() if j.kind == "reversal"
    }
    repayment_journals = {
        j.repayment_id: j for j in journals.values() if j.kind == "repayment"
    }
    for allocation in allocations:
        receipt_allocations[allocation.repayment_id].append(allocation)
        j = repayment_journals.get(allocation.repayment_id)
        if j and j.id not in reversed_journals:
            allocated[(allocation.loan_id, allocation.component)] += (
                allocation.amount_paise
            )
    for receipt in receipts.values():
        rows = receipt_allocations[receipt.id]
        j = repayment_journals.get(receipt.id)
        if j is None:
            errors.append(
                {"type": "receipt_missing_journal", "receipt_id": str(receipt.id)}
            )
            continue
        expected, observed = defaultdict(int), defaultdict(int)
        for row in rows:
            expected[(row.schedule_id, row.component)] += row.amount_paise
        cash_debit = 0
        for entry, code in journal_entries[j.id]:
            if code == "CASH" and entry.direction == "debit":
                cash_debit += entry.amount_paise
            elif code in CODES and entry.direction == "credit":
                observed[(entry.schedule_id, CODES[code])] += entry.amount_paise
            else:
                errors.append(
                    {"type": "incorrect_repayment_entry", "receipt_id": str(receipt.id)}
                )
        if (
            dict(expected) != dict(observed)
            or sum(expected.values()) != receipt.amount_paise
            or cash_debit != receipt.amount_paise
        ):
            errors.append(
                {"type": "repayment_effect_mismatch", "receipt_id": str(receipt.id)}
            )
    penalty_days = set()
    penalty_basis_errors = 0
    zero_days = penalty_records = 0
    for record in accruals:
        if record.kind == "scheduled_interest":
            recognized[(record.loan_id, "interest")] += record.amount_paise
            schedule = schedules[record.schedule_id]
            journal = journals.get(record.journal_id)
            if (
                record.amount_paise != schedule.interest_due_paise
                or not journal
                or schedule.due_date > journal.business_date
            ):
                errors.append(
                    {
                        "type": "scheduled_recognition_mismatch",
                        "schedule_id": str(schedule.id),
                    }
                )
        if record.kind != "overdue_penalty":
            continue
        penalty_records += 1
        recognized[(record.loan_id, "penalty")] += record.amount_paise
        identity = (record.schedule_id, record.period_start)
        if (
            identity in penalty_days
            or record.period_end != record.period_start + timedelta(days=1)
        ):
            errors.append({"type": "overlapping_penalty_period"})
        penalty_days.add(identity)
        schedule = schedules[record.schedule_id]
        prior_paid = 0
        for allocation in allocations:
            if (
                allocation.schedule_id != record.schedule_id
                or allocation.component != "principal"
            ):
                continue
            receipt = receipts[allocation.repayment_id]
            j = repayment_journals[receipt.id]
            reverse = reversed_journals.get(j.id)
            if receipt.business_date < record.period_start and (
                reverse is None or reverse.business_date >= record.period_start
            ):
                prior_paid += allocation.amount_paise
        basis = schedule.principal_due_paise - prior_paid
        # Exact independent integer arithmetic: 0.05% = 1/2000; positive half-up.
        expected_charge = (basis + 1000) // 2000
        if (
            basis != record.basis_paise
            or expected_charge != record.amount_paise
            or schedule.due_date >= record.period_start
        ):
            penalty_basis_errors += 1
        if record.amount_paise == 0:
            zero_days += 1
            if record.journal_id is not None:
                errors.append({"type": "zero_charge_has_journal"})
        else:
            lines = journal_entries[record.journal_id]
            expected_lines = {
                (
                    "PENALTY_RECEIVABLE",
                    "debit",
                    record.amount_paise,
                    record.schedule_id,
                ),
                ("PENALTY_INCOME", "credit", record.amount_paise, record.schedule_id),
            }
            if {
                (code, entry.direction, entry.amount_paise, entry.schedule_id)
                for entry, code in lines
            } != expected_lines:
                errors.append({"type": "penalty_journal_mismatch"})
    per_loan, principal_differences, interest_differences, penalty_differences = (
        [],
        [],
        [],
        [],
    )
    for logical_id, actual_id in sorted(loan_map.items()):
        loan = loans[actual_id]
        expected = manifest["expected_final"][logical_id]
        observed = {
            component: ledger[(actual_id, component)]
            for component in ("principal", "interest", "penalty")
        }
        operational = {
            "principal": loan.principal_paise - allocated[(actual_id, "principal")],
            "interest": recognized[(actual_id, "interest")]
            - allocated[(actual_id, "interest")],
            "penalty": recognized[(actual_id, "penalty")]
            - allocated[(actual_id, "penalty")],
        }
        for component, differences in [
            ("principal", principal_differences),
            ("interest", interest_differences),
            ("penalty", penalty_differences),
        ]:
            if (
                observed[component] != operational[component]
                or observed[component] != expected[component + "_paise"]
            ):
                differences.append(
                    {
                        "loan_id": logical_id,
                        "ledger": observed[component],
                        "operational": operational[component],
                        "reference": expected[component + "_paise"],
                    }
                )
            if allocated[(actual_id, component)] != expected["collected"].get(
                component, 0
            ):
                errors.append(
                    {
                        "type": "reference_collection_mismatch",
                        "loan_id": logical_id,
                        "component": component,
                    }
                )
        if (
            recognized[(actual_id, "interest")] != expected["recognized_interest_paise"]
            or recognized[(actual_id, "penalty")]
            != expected["recognized_penalty_paise"]
        ):
            errors.append(
                {"type": "reference_recognition_mismatch", "loan_id": logical_id}
            )
        rows = sorted(
            (row for row in schedules.values() if row.loan_id == actual_id),
            key=lambda row: row.instalment_number,
        )
        if sum(row.principal_due_paise for row in rows) != loan.principal_paise:
            errors.append(
                {"type": "scheduled_principal_mismatch", "loan_id": logical_id}
            )
        for row in rows:
            paid = sum(
                a.amount_paise
                for a in allocations
                if a.schedule_id == row.id
                and a.component == "principal"
                and repayment_journals[a.repayment_id].id not in reversed_journals
            )
            if (
                paid < 0
                or paid > row.principal_due_paise
                or row.principal_due_paise - paid
                != expected["principal_by_instalment"][row.instalment_number - 1]
            ):
                errors.append(
                    {
                        "type": "instalment_principal_mismatch",
                        "loan_id": logical_id,
                        "number": row.instalment_number,
                    }
                )
        per_loan.append(
            {"loan_id": logical_id, "ledger": observed, "operational": operational}
        )
    counts = {
        "borrowers": len(session.scalars(select(Borrower)).all()),
        "loans": len(loans),
        "products": len(session.scalars(select(LoanProduct)).all()),
        "accepted_receipts": len(receipts),
    }
    if (
        len(journals) != manifest["expected_journals"]
        or penalty_records != manifest["expected_penalty_evaluations"]
        or zero_days != manifest["expected_zero_charge_days"]
    ):
        errors.append({"type": "reference_record_count_mismatch"})
    passed = (
        not errors
        and not any(
            (
                unbalanced,
                penalty_basis_errors,
                principal_differences,
                interest_differences,
                penalty_differences,
            )
        )
        and total_debit == total_credit
    )
    return {
        "passed": passed,
        "database_counts": counts,
        "posted_journals": len(journals),
        "total_debit_paise": total_debit,
        "total_credit_paise": total_credit,
        "unbalanced_journal_count": unbalanced,
        "principal_differences": principal_differences,
        "interest_differences": interest_differences,
        "penalty_differences": penalty_differences,
        "penalty_basis_errors": penalty_basis_errors,
        "penalty_evaluations": penalty_records,
        "zero_charge_days": zero_days,
        "errors": errors,
        "per_loan": per_loan,
    }
