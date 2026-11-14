"""Future posting boundary. No posting implementation exists in Phase 1."""

from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session


class PostingService(Protocol):
    """Future implementations use the caller's atomic transaction and loan lock.

    They must validate authorization, idempotency, receivables and balanced entries.
    No method may commit independently or mutate a posted journal.
    """

    def disburse(self, session: Session, loan_id: UUID, event_key: str) -> UUID: ...

    def receive_repayment(
        self,
        session: Session,
        loan_id: UUID,
        amount_paise: int,
        occurred_at: datetime,
        source: str,
        event_id: str,
    ) -> UUID: ...

    def reverse(self, session: Session, journal_id: UUID, event_key: str) -> UUID: ...

    def recognize_interest(
        self,
        session: Session,
        loan_id: UUID,
        schedule_id: UUID,
        period_start: date,
        period_end: date,
        kind: str,
    ) -> UUID: ...
