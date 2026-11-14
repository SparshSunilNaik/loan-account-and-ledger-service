from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import aliased

from ledgercore.accounting import posting
from ledgercore.api.routes import DB, require
from ledgercore.models.entities import (
    AuditEvent,
    LedgerAccount,
    LedgerEntry,
    LedgerJournal,
    Loan,
    Repayment,
    RepaymentAllocation,
)
from ledgercore.schemas.financial import ProcessingDate, RepaymentCreate, ReversalCreate
from ledgercore.security.demo import Manager, Officer, Reader, Reviewer

router = APIRouter()


def transact(session, operation):
    """Retry uniqueness/deadlock races after rolling back the whole operation.

    A winning source event/key becomes visible at READ COMMITTED on the next attempt.
    Services never commit. Unexpected failures escape and the context rolls back.
    """
    for attempt in range(3):
        try:
            with session.begin():
                result = operation()
            return result
        except posting.FinancialError as exc:
            raise HTTPException(exc.status, exc.detail) from exc
        except DBAPIError as exc:
            code = getattr(exc.orig, "sqlstate", None)
            if code in ("23505", "40001", "40P01") and attempt < 2:
                continue
            if code in ("23505", "23514", "23503", "40001", "40P01", "55P03"):
                raise HTTPException(
                    409, "Financial transaction conflict; retry the request"
                ) from exc
            raise


@router.post("/loans/{loan_id}/disburse", status_code=201)
def disburse(
    loan_id: UUID, body: ProcessingDate, actor: Manager, session: DB, request: Request
):
    return transact(
        session,
        lambda: posting.disburse(
            session, loan_id, body.business_date, actor.id, request.state.correlation_id
        ),
    )


@router.post("/loans/{loan_id}/repayments", status_code=201)
def repay(
    loan_id: UUID,
    body: RepaymentCreate,
    actor: Officer,
    session: DB,
    request: Request,
    key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=200,
            pattern=r"^[A-Za-z0-9_.:-]+$",
        ),
    ],
):
    return transact(
        session,
        lambda: posting.receive_repayment(
            session, loan_id, body, key, actor.id, request.state.correlation_id
        ),
    )


@router.get("/loans/{loan_id}/repayments")
def repayments(loan_id: UUID, actor: Reader, session: DB):
    require(session, Loan, loan_id)
    reversal = aliased(LedgerJournal)
    rows = session.execute(
        select(Repayment, LedgerJournal.id, reversal.id)
        .join(LedgerJournal, LedgerJournal.repayment_id == Repayment.id)
        .outerjoin(
            reversal,
            (reversal.reversal_of_id == LedgerJournal.id)
            & (reversal.status == "posted"),
        )
        .where(Repayment.loan_id == loan_id, LedgerJournal.status == "posted")
        .order_by(Repayment.received_at, Repayment.id)
    ).all()
    allocations = session.scalars(
        select(RepaymentAllocation)
        .where(RepaymentAllocation.loan_id == loan_id)
        .order_by(RepaymentAllocation.schedule_id, RepaymentAllocation.component)
    ).all()
    return [
        {
            "id": receipt.id,
            "journal_id": journal_id,
            "loan_id": loan_id,
            "amount_paise": receipt.amount_paise,
            "source": receipt.source,
            "external_event_id": receipt.external_event_id,
            "occurred_at": receipt.occurred_at,
            "received_at": receipt.received_at,
            "business_date": receipt.business_date,
            "status": "reversed" if reversal_id else "posted",
            "reversal_journal_id": reversal_id,
            "allocations": [
                {
                    "schedule_id": a.schedule_id,
                    "component": a.component,
                    "amount_paise": a.amount_paise,
                }
                for a in allocations
                if a.repayment_id == receipt.id
            ],
        }
        for receipt, journal_id, reversal_id in rows
    ]


@router.get("/loans/{loan_id}/balance")
def balance(loan_id: UUID, actor: Reader, session: DB):
    require(session, Loan, loan_id)
    return {"loan_id": loan_id, "currency": "INR", **posting.balance(session, loan_id)}


@router.get("/loans/{loan_id}/ledger")
def ledger(loan_id: UUID, actor: Reader, session: DB):
    require(session, Loan, loan_id)
    rows = session.execute(
        select(LedgerJournal, LedgerEntry, LedgerAccount.code)
        .join(LedgerEntry, LedgerEntry.journal_id == LedgerJournal.id)
        .join(LedgerAccount, LedgerAccount.id == LedgerEntry.account_id)
        .where(LedgerJournal.loan_id == loan_id, LedgerJournal.status == "posted")
        .order_by(LedgerJournal.created_at, LedgerJournal.id, LedgerEntry.id)
    ).all()
    journals = {}
    for j, entry, code in rows:
        if j.id not in journals:
            journals[j.id] = {
                "id": j.id,
                "kind": j.kind,
                "status": j.status,
                "business_date": j.business_date,
                "effective_at": j.effective_at,
                "posted_at": j.posted_at,
                "repayment_id": j.repayment_id,
                "reversal_of_id": j.reversal_of_id,
                "description": j.description,
                "entries": [],
            }
        journals[j.id]["entries"].append(
            {
                "id": entry.id,
                "account": code,
                "direction": entry.direction,
                "amount_paise": entry.amount_paise,
                "schedule_id": entry.schedule_id,
                "receivable_origin_id": entry.receivable_origin_id,
            }
        )
    return list(journals.values())


@router.get("/audit-events")
def audit_events(
    actor: Reviewer,
    session: DB,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return session.scalars(
        select(AuditEvent)
        .order_by(AuditEvent.created_at, AuditEvent.id)
        .limit(limit)
        .offset(offset)
    ).all()


@router.post("/loans/{loan_id}/journals/{journal_id}/reverse")
def reverse(
    loan_id: UUID,
    journal_id: UUID,
    body: ReversalCreate,
    actor: Manager,
    session: DB,
    request: Request,
):
    return transact(
        session,
        lambda: posting.reverse_repayment(
            session, loan_id, journal_id, body, actor.id, request.state.correlation_id
        ),
    )
