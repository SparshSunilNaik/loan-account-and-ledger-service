from dataclasses import asdict

from sqlalchemy.orm import Session

from ledgercore.models.entities import (
    AuditEvent,
    Borrower,
    Loan,
    LoanProduct,
    RepaymentSchedule,
)
from ledgercore.schemas.api import LoanCreate
from ledgercore.services.schedules import generate_schedule


class OriginationError(ValueError):
    pass


def originate(session: Session, request: LoanCreate) -> Loan:
    """Caller owns the transaction; the loan and full schedule are one unit."""
    if session.get(Borrower, request.borrower_id) is None:
        raise OriginationError("Borrower not found")
    product = session.get(LoanProduct, request.product_id)
    if product is None:
        raise OriginationError("Loan product not found")
    if not product.active:
        raise OriginationError("Loan product is inactive")
    rows = generate_schedule(
        request.principal_paise,
        product.annual_rate,
        request.tenure_periods,
        product.interest_method,
        product.frequency,
        request.first_due_date,
    )
    loan = Loan(
        **request.model_dump(),
        annual_rate=product.annual_rate,
        interest_method=product.interest_method,
        frequency=product.frequency,
        currency=product.currency,
        schedule_version="v1",
    )
    session.add(loan)
    session.flush()
    session.add_all([RepaymentSchedule(loan_id=loan.id, **asdict(row)) for row in rows])
    session.add(
        AuditEvent(
            action="loan.originated",
            entity_type="loan",
            entity_id=loan.id,
            details={"schedule_version": "v1"},
        )
    )
    return loan
