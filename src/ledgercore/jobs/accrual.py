"""Dated daily opening-principal accrual. No always-running scheduler is required."""

import argparse
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, localcontext
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import aliased

from ledgercore.accounting import posting
from ledgercore.db.session import session_factory
from ledgercore.models.entities import (
    AccrualRecord,
    LedgerJournal,
    Loan,
    Repayment,
    RepaymentAllocation,
    RepaymentSchedule,
    User,
)
from ledgercore.services.money import round_paise

DAILY_RATE = Decimal("0.0005")


def daily_charge(basis_paise: int) -> int:
    if type(basis_paise) is not int or not 0 <= basis_paise <= 100000000000:
        raise ValueError("Invalid penalty basis")
    with localcontext() as ctx:
        ctx.prec = 50
        return round_paise(Decimal(basis_paise) * DAILY_RATE)


def historical_principal_movements(session, loan_id):
    """Processing-day deltas, including forward-dated reversals, never economic backdating."""
    reversal = aliased(LedgerJournal)
    rows = session.execute(
        select(
            RepaymentAllocation.schedule_id,
            RepaymentAllocation.amount_paise,
            Repayment.business_date,
            reversal.business_date,
        )
        .join(Repayment, Repayment.id == RepaymentAllocation.repayment_id)
        .join(LedgerJournal, LedgerJournal.repayment_id == Repayment.id)
        .outerjoin(
            reversal,
            (reversal.reversal_of_id == LedgerJournal.id)
            & (reversal.status == "posted"),
        )
        .where(
            RepaymentAllocation.loan_id == loan_id,
            RepaymentAllocation.component == "principal",
            LedgerJournal.status == "posted",
        )
    ).all()
    return rows


def accrue_loan(
    session,
    loan_id: UUID,
    business_date: date,
    actor_id: UUID,
    correlation_id: str,
    *,
    catch_up=False,
    max_days=3660,
):
    """Caller owns one transaction for the entire loan; daily basis uses activity before D."""
    if type(business_date) is not date or not date(1900, 1, 1) <= business_date <= date(
        2100, 12, 31
    ):
        raise posting.FinancialError(
            422, "Business date must be an explicit supported UTC date"
        )
    loan = posting.lock_loan(session, loan_id)
    posting.require_disbursed(loan)
    posting.check_date(session, loan_id, business_date)
    disbursed = session.scalar(
        select(func.min(LedgerJournal.business_date)).where(
            LedgerJournal.loan_id == loan_id,
            LedgerJournal.kind == "disbursement",
            LedgerJournal.status == "posted",
        )
    )
    if disbursed is None:
        raise posting.FinancialError(409, "Missing posted disbursement")
    schedules = session.scalars(
        select(RepaymentSchedule)
        .where(RepaymentSchedule.loan_id == loan_id)
        .order_by(RepaymentSchedule.instalment_number)
    ).all()
    allocated = posting.active_principal_allocations(session, loan_id)
    capacities = [
        row.principal_due_paise - int(allocated.get(row.id, 0)) for row in schedules
    ]
    if (
        any(value < 0 for value in capacities)
        or sum(capacities)
        != posting.balance(session, loan_id)["principal_receivable_paise"]
    ):
        raise posting.FinancialError(
            409, "Principal allocations require reconciliation before accrual"
        )
    earliest = max(
        min(r.due_date for r in schedules) + timedelta(days=1),
        disbursed + timedelta(days=1),
    )
    if catch_up and (business_date - earliest).days + 1 > max_days:
        raise posting.FinancialError(
            422, "Catch-up horizon exceeds max-days; choose an explicit larger bound"
        )
    interest = posting.recognize_scheduled_interest(
        session, loan_id, business_date, actor_id, correlation_id
    )
    existing = set(
        session.execute(
            select(AccrualRecord.schedule_id, AccrualRecord.period_start).where(
                AccrualRecord.loan_id == loan_id,
                AccrualRecord.kind == "overdue_penalty",
            )
        ).all()
    )
    movements = historical_principal_movements(session, loan_id)
    created = charged = total = 0
    for row in schedules:
        start = (
            max(row.due_date + timedelta(days=1), disbursed + timedelta(days=1))
            if catch_up
            else business_date
        )
        if not catch_up and business_date < max(
            row.due_date + timedelta(days=1), disbursed + timedelta(days=1)
        ):
            continue
        day = start
        while day <= business_date:
            if (row.id, day) not in existing:
                paid = sum(
                    amount
                    for schedule_id, amount, received, reversed_day in movements
                    if schedule_id == row.id
                    and received < day
                    and (reversed_day is None or reversed_day >= day)
                )
                basis = row.principal_due_paise - paid
                if basis < 0:
                    raise posting.FinancialError(
                        409, "Historical principal requires reconciliation"
                    )
                amount = daily_charge(basis)
                journal = None
                if amount:
                    journal = posting.post_journal(
                        session,
                        loan_id,
                        "penalty",
                        f"daily-penalty:{row.id}:{day}",
                        business_date,
                        [
                            ("PENALTY_RECEIVABLE", "debit", amount, row.id, None),
                            ("PENALTY_INCOME", "credit", amount, row.id, None),
                        ],
                        description=f"Daily overdue principal penalty for {day}",
                        effective_at=datetime.combine(day, time(), UTC),
                    )
                    charged += 1
                session.add(
                    AccrualRecord(
                        loan_id=loan_id,
                        schedule_id=row.id,
                        kind="overdue_penalty",
                        period_start=day,
                        period_end=day + timedelta(days=1),
                        basis_paise=basis,
                        daily_rate=DAILY_RATE,
                        amount_paise=amount,
                        journal_id=journal.id if journal else None,
                    )
                )
                created += 1
                total += amount
            day += timedelta(days=1)
    if created or interest:
        posting.audit(
            session,
            actor_id,
            correlation_id,
            "accrual.completed",
            "loan",
            loan_id,
            business_date=business_date.isoformat(),
            evaluated_days=created,
            charged_days=charged,
            penalty_paise=total,
            scheduled_interest_journals=interest,
            catch_up=catch_up,
        )
    session.flush()
    return {
        "loan_id": str(loan_id),
        "evaluated_days": created,
        "charged_days": charged,
        "penalty_paise": total,
        "interest_journals": len(interest),
    }


def run_job(factory, business_date, *, catch_up=False, loan_ids=None, max_days=3660):
    """Each loan commits independently; failed loans roll back and remain resumable."""
    with factory() as session:
        actor = session.scalar(
            select(User).where(
                User.external_subject == "demo-manager",
                User.active.is_(True),
                User.role == "manager",
            )
        )
        if actor is None:
            raise ValueError("An active demo-manager job identity is required")
        actor_id = actor.id
        ids = (
            loan_ids
            if loan_ids is not None
            else list(
                session.scalars(
                    select(Loan.id).where(Loan.status == "disbursed").order_by(Loan.id)
                )
            )
        )
    results, failures = [], []
    for loan_id in ids:
        for attempt in range(3):
            try:
                with factory() as session, session.begin():
                    result = accrue_loan(
                        session,
                        loan_id,
                        business_date,
                        actor_id,
                        f"accrual:{business_date}:{loan_id}",
                        catch_up=catch_up,
                        max_days=max_days,
                    )
                results.append(result)
                break
            except DBAPIError as exc:
                if (
                    getattr(exc.orig, "sqlstate", None) in ("40001", "40P01", "23505")
                    and attempt < 2
                ):
                    continue
                failures.append(
                    {"loan_id": str(loan_id), "reason": "database_conflict"}
                )
                break
            except Exception as exc:
                failures.append(
                    {
                        "loan_id": str(loan_id),
                        "reason": exc.detail
                        if isinstance(exc, posting.FinancialError)
                        else "accrual_failed",
                    }
                )
                break
    return {
        "business_date": business_date.isoformat(),
        "results": results,
        "failures": failures,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-date", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--catch-up",
        action="store_true",
        help="Fill every missing eligible day using historical opening principal",
    )
    parser.add_argument("--max-days", type=int, default=3660)
    parser.add_argument("--loan-id", type=UUID, action="append")
    args = parser.parse_args()
    if args.max_days < 1:
        parser.error("max-days must be positive")
    result = run_job(
        session_factory(),
        args.business_date,
        catch_up=args.catch_up,
        loan_ids=args.loan_id,
        max_days=args.max_days,
    )
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(1 if result["failures"] else 0)


if __name__ == "__main__":
    main()
