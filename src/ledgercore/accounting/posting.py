"""Atomic posting operations. Callers own transactions; every mutation locks its loan."""

import hashlib
import json
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, aliased

from ledgercore.models.entities import (
    AccrualRecord,
    AuditEvent,
    IdempotencyRequest,
    LedgerAccount,
    LedgerEntry,
    LedgerJournal,
    Loan,
    Repayment,
    RepaymentAllocation,
    RepaymentSchedule,
)
from ledgercore.services.money import MAX_MONEY_PAISE

RECEIVABLES = {
    "principal": "LOAN_PRINCIPAL_RECEIVABLE",
    "interest": "INTEREST_RECEIVABLE",
    "penalty": "PENALTY_RECEIVABLE",
}


class FinancialError(Exception):
    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail
        super().__init__(detail)


def audit(session, actor_id, correlation_id, action, entity_type, entity_id, **details):
    session.add(
        AuditEvent(
            actor_user_id=actor_id,
            correlation_id=correlation_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
    )


def lock_loan(session: Session, loan_id: UUID) -> Loan:
    if not session.in_transaction():
        raise RuntimeError("Posting requires a caller-owned transaction")
    loan = session.scalar(
        select(Loan)
        .where(Loan.id == loan_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if loan is None:
        raise FinancialError(404, "Loan not found")
    return loan


def check_date(session, loan_id, business_date):
    if type(business_date) is not date:
        raise FinancialError(422, "An explicit business date is required")
    last = session.scalar(
        select(func.max(LedgerJournal.business_date)).where(
            LedgerJournal.loan_id == loan_id, LedgerJournal.status == "posted"
        )
    )
    evaluated = session.scalar(
        select(func.max(AccrualRecord.period_start)).where(
            AccrualRecord.loan_id == loan_id, AccrualRecord.kind == "overdue_penalty"
        )
    )
    last = max([d for d in (last, evaluated) if d is not None], default=None)
    if last is not None and business_date < last:
        raise FinancialError(
            409, "Business date cannot precede an already posted operation"
        )


def require_disbursed(loan):
    if loan.status != "disbursed":
        raise FinancialError(409, "Loan must be disbursed before posting")


def post_journal(
    session,
    loan_id,
    kind,
    event_key,
    business_date,
    lines,
    *,
    repayment_id=None,
    reversal_of_id=None,
    description="",
    effective_at=None,
):
    """Internal primitive: caller has authorized and locked the loan.

    Lines are (account code, direction, amount, schedule UUID, receivable origin UUID).
    Draft entries are flushed before the balanced posted transition.
    """
    if (
        len(lines) < 2
        or sum(
            amount if direction == "debit" else -amount
            for _, direction, amount, _, _ in lines
        )
        != 0
    ):
        raise FinancialError(409, "Journal must be balanced")
    accounts = {a.code: a.id for a in session.scalars(select(LedgerAccount))}
    if any(
        code not in accounts
        or direction not in ("debit", "credit")
        or type(amount) is not int
        or not 1 <= amount <= MAX_MONEY_PAISE
        for code, direction, amount, _, _ in lines
    ):
        raise FinancialError(409, "Invalid journal entries")
    journal = LedgerJournal(
        loan_id=loan_id,
        kind=kind,
        event_key=event_key,
        business_date=business_date,
        effective_at=effective_at or datetime.combine(business_date, time(), UTC),
        description=description,
        repayment_id=repayment_id,
        reversal_of_id=reversal_of_id,
    )
    session.add(journal)
    session.flush()
    session.add_all(
        [
            LedgerEntry(
                journal_id=journal.id,
                account_id=accounts[code],
                direction=direction,
                amount_paise=amount,
                schedule_id=schedule_id,
                receivable_origin_id=origin_id,
            )
            for code, direction, amount, schedule_id, origin_id in lines
        ]
    )
    session.flush()
    journal.status, journal.posted_at = "posted", datetime.now(UTC)
    session.flush()
    return journal


def balance(session, loan_id):
    signed = case(
        (LedgerEntry.direction == "debit", LedgerEntry.amount_paise),
        else_=-LedgerEntry.amount_paise,
    )
    totals = dict(
        session.execute(
            select(LedgerAccount.code, func.sum(signed))
            .join(LedgerEntry, LedgerEntry.account_id == LedgerAccount.id)
            .join(LedgerJournal, LedgerJournal.id == LedgerEntry.journal_id)
            .where(LedgerJournal.loan_id == loan_id, LedgerJournal.status == "posted")
            .group_by(LedgerAccount.code)
        ).all()
    )
    result = {
        f"{component}_receivable_paise": int(totals.get(code, 0))
        for component, code in RECEIVABLES.items()
    }
    result["total_posted_receivables_paise"] = sum(result.values())
    return result


def disburse(session, loan_id, business_date, actor_id, correlation_id):
    loan = lock_loan(session, loan_id)
    if loan.status != "originated" or session.scalar(
        select(LedgerJournal.id).where(
            LedgerJournal.loan_id == loan_id, LedgerJournal.kind == "disbursement"
        )
    ):
        raise FinancialError(409, "Loan has already been disbursed")
    check_date(session, loan_id, business_date)
    journal = post_journal(
        session,
        loan_id,
        "disbursement",
        f"disbursement:{loan_id}",
        business_date,
        [
            ("LOAN_PRINCIPAL_RECEIVABLE", "debit", loan.principal_paise, None, None),
            ("CASH", "credit", loan.principal_paise, None, None),
        ],
        description="Loan disbursement",
    )
    loan.status = "disbursed"
    audit(
        session,
        actor_id,
        correlation_id,
        "loan.disbursed",
        "loan",
        loan_id,
        before={"status": "originated"},
        after={"status": "disbursed"},
        journal_id=str(journal.id),
        business_date=business_date.isoformat(),
    )
    return {
        "loan_id": str(loan_id),
        "journal_id": str(journal.id),
        "status": "disbursed",
    }


def recognize_scheduled_interest(
    session, loan_id, business_date, actor_id, correlation_id
):
    """Independently callable, idempotent service. No scheduler, no overdue charges."""
    loan = lock_loan(session, loan_id)
    require_disbursed(loan)
    check_date(session, loan_id, business_date)
    recorded = select(AccrualRecord.schedule_id).where(
        AccrualRecord.loan_id == loan_id, AccrualRecord.kind == "scheduled_interest"
    )
    rows = session.scalars(
        select(RepaymentSchedule)
        .where(
            RepaymentSchedule.loan_id == loan_id,
            RepaymentSchedule.due_date <= business_date,
            RepaymentSchedule.interest_due_paise > 0,
            RepaymentSchedule.id.not_in(recorded),
        )
        .order_by(RepaymentSchedule.due_date, RepaymentSchedule.instalment_number)
    ).all()
    journals = []
    for row in rows:
        journal = post_journal(
            session,
            loan_id,
            "scheduled_interest",
            f"scheduled-interest:{row.id}",
            business_date,
            [
                ("INTEREST_RECEIVABLE", "debit", row.interest_due_paise, row.id, None),
                ("INTEREST_INCOME", "credit", row.interest_due_paise, row.id, None),
            ],
            description="Contractual interest recognition",
            effective_at=datetime.combine(row.due_date, time(), UTC),
        )
        session.add(
            AccrualRecord(
                loan_id=loan_id,
                schedule_id=row.id,
                kind="scheduled_interest",
                period_start=row.due_date,
                period_end=row.due_date + timedelta(days=1),
                amount_paise=row.interest_due_paise,
                journal_id=journal.id,
            )
        )
        audit(
            session,
            actor_id,
            correlation_id,
            "interest.recognized",
            "loan",
            loan_id,
            before={"recognized_paise": 0},
            after={"recognized_paise": row.interest_due_paise},
            schedule_id=str(row.id),
            journal_id=str(journal.id),
            business_date=business_date.isoformat(),
        )
        journals.append(str(journal.id))
    session.flush()
    return journals


def canonical_hash(loan_id, request):
    payload = {"loan_id": str(loan_id), **request.model_dump(mode="json")}
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def complete_idempotency(session, record, response):
    record.status, record.response_status, record.response_body = (
        "completed",
        201,
        response,
    )
    record.completed_at = datetime.now(UTC)
    session.flush()
    return response


def recognized_lots(session, loan_id, component):
    """Outstanding per original recognized debit, calculated from posted entries."""
    signed = case(
        (LedgerEntry.direction == "debit", LedgerEntry.amount_paise),
        else_=-LedgerEntry.amount_paise,
    )
    origin = func.coalesce(LedgerEntry.receivable_origin_id, LedgerEntry.id)
    totals = dict(
        session.execute(
            select(origin, func.sum(signed))
            .join(LedgerJournal, LedgerJournal.id == LedgerEntry.journal_id)
            .join(LedgerAccount, LedgerAccount.id == LedgerEntry.account_id)
            .where(
                LedgerJournal.loan_id == loan_id,
                LedgerJournal.status == "posted",
                LedgerAccount.code == RECEIVABLES[component],
            )
            .group_by(origin)
        ).all()
    )
    if any(amount < 0 for amount in totals.values()):
        raise FinancialError(409, "Receivable history requires reconciliation")
    ids = [entry_id for entry_id, amount in totals.items() if amount > 0]
    rows = session.execute(
        select(LedgerEntry, LedgerJournal.effective_at)
        .join(LedgerJournal, LedgerJournal.id == LedgerEntry.journal_id)
        .outerjoin(RepaymentSchedule, RepaymentSchedule.id == LedgerEntry.schedule_id)
        .where(LedgerEntry.id.in_(ids))
        .order_by(
            LedgerJournal.effective_at,
            RepaymentSchedule.due_date,
            RepaymentSchedule.instalment_number,
            LedgerJournal.created_at,
            LedgerEntry.id,
        )
    ).all()
    lots = []
    for entry, _ in rows:
        if (
            entry.direction != "debit"
            or entry.schedule_id is None
            or entry.receivable_origin_id is not None
        ):
            raise FinancialError(409, "Receivable history requires reconciliation")
        lots.append((entry.schedule_id, entry.id, int(totals[entry.id])))
    return lots


def active_principal_allocations(session, loan_id):
    reversal = aliased(LedgerJournal)
    reversed_journal = (
        select(reversal.id)
        .where(reversal.reversal_of_id == LedgerJournal.id, reversal.status == "posted")
        .exists()
    )
    return dict(
        session.execute(
            select(
                RepaymentAllocation.schedule_id,
                func.sum(RepaymentAllocation.amount_paise),
            )
            .join(
                LedgerJournal,
                LedgerJournal.repayment_id == RepaymentAllocation.repayment_id,
            )
            .where(
                RepaymentAllocation.loan_id == loan_id,
                RepaymentAllocation.component == "principal",
                LedgerJournal.status == "posted",
                ~reversed_journal,
            )
            .group_by(RepaymentAllocation.schedule_id)
        ).all()
    )


def receive_repayment(session, loan_id, request, key, actor_id, correlation_id):
    loan = lock_loan(session, loan_id)
    digest = canonical_hash(loan_id, request)
    scope = f"{actor_id}:repayment"
    idem = session.scalar(
        select(IdempotencyRequest).where(
            IdempotencyRequest.scope == scope, IdempotencyRequest.key == key
        )
    )
    if idem:
        if idem.request_hash != digest:
            raise FinancialError(
                409, "Idempotency key was used with a different request"
            )
        if idem.status != "completed" or idem.response_body is None:
            raise FinancialError(409, "Request is not completed; retry later")
        return idem.response_body
    original = session.scalar(
        select(Repayment).where(
            Repayment.source == request.source,
            Repayment.external_event_id == request.external_event_id,
        )
    )
    idem = IdempotencyRequest(
        scope=scope, key=key, request_hash=digest, status="pending"
    )
    if original:
        if original.request_hash != digest or original.idempotency_request_id is None:
            raise FinancialError(409, "Source event was used with a different request")
        first = session.get(IdempotencyRequest, original.idempotency_request_id)
        if first is None or first.response_body is None:
            raise FinancialError(409, "Source event requires reconciliation")
        session.add(idem)
        return complete_idempotency(session, idem, first.response_body)
    require_disbursed(loan)
    check_date(session, loan_id, request.business_date)
    if (
        type(request.amount_paise) is not int
        or not 1 <= request.amount_paise <= MAX_MONEY_PAISE
    ):
        raise FinancialError(422, "Repayment amount is outside supported bounds")
    recognize_scheduled_interest(
        session, loan_id, request.business_date, actor_id, correlation_id
    )
    before = balance(session, loan_id)
    if request.amount_paise > before["total_posted_receivables_paise"]:
        raise FinancialError(
            400, "Repayment exceeds collectible outstanding receivables"
        )
    if min(before.values()) < 0:
        raise FinancialError(409, "Receivable history requires reconciliation")
    remaining = request.amount_paise
    credits = []
    allocations = defaultdict(int)
    for component in ("penalty", "interest"):
        for schedule_id, origin_id, outstanding in recognized_lots(
            session, loan_id, component
        ):
            amount = min(remaining, outstanding)
            if amount:
                credits.append(
                    (RECEIVABLES[component], "credit", amount, schedule_id, origin_id)
                )
                allocations[(schedule_id, component)] += amount
                remaining -= amount
    settled = active_principal_allocations(session, loan_id)
    schedules = session.scalars(
        select(RepaymentSchedule)
        .where(RepaymentSchedule.loan_id == loan_id)
        .order_by(RepaymentSchedule.due_date, RepaymentSchedule.instalment_number)
    ).all()
    capacity = {
        row.id: row.principal_due_paise - int(settled.get(row.id, 0))
        for row in schedules
    }
    if (
        any(v < 0 for v in capacity.values())
        or sum(capacity.values()) != before["principal_receivable_paise"]
    ):
        raise FinancialError(409, "Principal allocations require reconciliation")
    # Due rows precede future rows because schedules are sorted by contractual due date.
    for row in schedules:
        amount = min(remaining, capacity[row.id])
        if amount:
            credits.append(
                ("LOAN_PRINCIPAL_RECEIVABLE", "credit", amount, row.id, None)
            )
            allocations[(row.id, "principal")] += amount
            remaining -= amount
    if remaining:
        raise FinancialError(409, "Receivable allocations require reconciliation")
    session.add(idem)
    session.flush()
    receipt = Repayment(
        loan_id=loan_id,
        source=request.source,
        external_event_id=request.external_event_id,
        business_date=request.business_date,
        request_hash=digest,
        amount_paise=request.amount_paise,
        occurred_at=request.occurred_at,
        idempotency_request_id=idem.id,
    )
    session.add(receipt)
    session.flush()
    session.add_all(
        [
            RepaymentAllocation(
                loan_id=loan_id,
                repayment_id=receipt.id,
                schedule_id=schedule_id,
                component=component,
                amount_paise=amount,
            )
            for (schedule_id, component), amount in allocations.items()
        ]
    )
    journal = post_journal(
        session,
        loan_id,
        "repayment",
        f"repayment:{receipt.id}",
        request.business_date,
        [("CASH", "debit", request.amount_paise, None, None), *credits],
        repayment_id=receipt.id,
        description="Repayment receipt",
        effective_at=request.occurred_at,
    )
    after = balance(session, loan_id)
    response = {
        "id": str(receipt.id),
        "loan_id": str(loan_id),
        "journal_id": str(journal.id),
        "amount_paise": receipt.amount_paise,
        "source": receipt.source,
        "external_event_id": receipt.external_event_id,
        "occurred_at": receipt.occurred_at.isoformat(),
        "received_at": receipt.received_at.isoformat(),
        "business_date": receipt.business_date.isoformat(),
        "status": "posted",
        "allocations": [
            {"schedule_id": str(s), "component": c, "amount_paise": a}
            for (s, c), a in allocations.items()
        ],
    }
    audit(
        session,
        actor_id,
        correlation_id,
        "repayment.posted",
        "repayment",
        receipt.id,
        before=before,
        after=after,
        journal_id=str(journal.id),
        loan_id=str(loan_id),
        business_date=request.business_date.isoformat(),
    )
    return complete_idempotency(session, idem, response)


def reverse_repayment(session, loan_id, journal_id, request, actor_id, correlation_id):
    loan = lock_loan(session, loan_id)
    require_disbursed(loan)
    original = session.get(LedgerJournal, journal_id)
    if original is None or original.loan_id != loan_id:
        raise FinancialError(404, "Journal not found for loan")
    if (
        original.status != "posted"
        or original.kind != "repayment"
        or original.repayment_id is None
    ):
        raise FinancialError(409, "Only posted repayment journals support reversal")
    existing = session.scalar(
        select(LedgerJournal).where(
            LedgerJournal.reversal_of_id == journal_id, LedgerJournal.status == "posted"
        )
    )
    if existing:
        return {
            "journal_id": str(existing.id),
            "reversal_of_id": str(journal_id),
            "repayment_id": str(original.repayment_id),
            "status": "posted",
        }
    check_date(session, loan_id, request.business_date)
    before = balance(session, loan_id)
    lines = session.execute(
        select(LedgerEntry, LedgerAccount.code)
        .join(LedgerAccount, LedgerAccount.id == LedgerEntry.account_id)
        .where(LedgerEntry.journal_id == journal_id)
        .order_by(LedgerEntry.id)
    ).all()
    reversed_journal = post_journal(
        session,
        loan_id,
        "reversal",
        f"reversal:{journal_id}",
        request.business_date,
        [
            (
                code,
                "credit" if entry.direction == "debit" else "debit",
                entry.amount_paise,
                entry.schedule_id,
                entry.receivable_origin_id,
            )
            for entry, code in lines
        ],
        reversal_of_id=journal_id,
        description=request.reason,
    )
    audit(
        session,
        actor_id,
        correlation_id,
        "repayment.reversed",
        "repayment",
        original.repayment_id,
        before=before,
        after=balance(session, loan_id),
        journal_id=str(reversed_journal.id),
        reversal_of_id=str(journal_id),
        reason=request.reason,
        business_date=request.business_date.isoformat(),
    )
    session.flush()
    return {
        "journal_id": str(reversed_journal.id),
        "reversal_of_id": str(journal_id),
        "repayment_id": str(original.repayment_id),
        "status": "posted",
    }
