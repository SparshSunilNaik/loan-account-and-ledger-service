from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ledgercore.db.session import get_session
from ledgercore.models.entities import (
    AuditEvent,
    Borrower,
    Loan,
    LoanProduct,
    RepaymentSchedule,
)
from ledgercore.schemas.api import (
    BorrowerCreate,
    BorrowerRead,
    LoanCreate,
    LoanRead,
    ProductRead,
    ScheduleRead,
)
from ledgercore.security.demo import Officer, Reader
from ledgercore.services.origination import OriginationError, originate

router = APIRouter()
DB = Annotated[Session, Depends(get_session)]


def require(session, model, record_id):
    record = session.get(model, record_id)
    if record is None:
        raise HTTPException(404, f"{model.__name__} not found")
    return record


def conflict(exc: IntegrityError):
    # Never disclose SQL, parameters, or driver diagnostics to clients.
    if getattr(exc.orig, "sqlstate", None) == "23505":
        return HTTPException(409, "External reference already exists")
    return HTTPException(409, "Request conflicts with database constraints")


@router.post("/borrowers", response_model=BorrowerRead, status_code=201)
def create_borrower(
    body: BorrowerCreate, actor: Officer, session: DB, request: Request
):
    try:
        with session.begin():
            borrower = Borrower(**body.model_dump())
            session.add(borrower)
            session.flush()
            session.add(
                AuditEvent(
                    action="borrower.created",
                    entity_type="borrower",
                    entity_id=borrower.id,
                    actor_user_id=actor.id,
                    correlation_id=request.state.correlation_id,
                    details={
                        "before": None,
                        "after": {"external_reference": borrower.external_reference},
                    },
                )
            )
    except IntegrityError as exc:
        raise conflict(exc) from exc
    return borrower


@router.get("/borrowers/{borrower_id}", response_model=BorrowerRead)
def get_borrower(borrower_id: UUID, actor: Reader, session: DB):
    return require(session, Borrower, borrower_id)


@router.get("/loan-products", response_model=list[ProductRead])
def products(actor: Reader, session: DB):
    return session.scalars(select(LoanProduct).order_by(LoanProduct.code)).all()


@router.post("/loans", response_model=LoanRead, status_code=201)
def create_loan(body: LoanCreate, actor: Officer, session: DB, request: Request):
    try:
        with session.begin():
            loan = originate(session, body, actor.id, request.state.correlation_id)
    except OriginationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except IntegrityError as exc:
        raise conflict(exc) from exc
    return loan


@router.get("/loans/{loan_id}", response_model=LoanRead)
def get_loan(loan_id: UUID, actor: Reader, session: DB):
    return require(session, Loan, loan_id)


@router.get("/loans/{loan_id}/schedule", response_model=list[ScheduleRead])
def schedule(loan_id: UUID, actor: Reader, session: DB):
    require(session, Loan, loan_id)
    return session.scalars(
        select(RepaymentSchedule)
        .where(RepaymentSchedule.loan_id == loan_id)
        .order_by(RepaymentSchedule.instalment_number)
    ).all()


@router.get("/health")
def health(session: DB):
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database unavailable") from exc
    return {"status": "ok", "database": "ok"}
