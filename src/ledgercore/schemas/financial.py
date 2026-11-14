from datetime import UTC, date, datetime
from typing import Annotated

from pydantic import (
    AwareDatetime,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from ledgercore.schemas.api import Input, LoanCreate, Reference
from ledgercore.services.money import MAX_MONEY_PAISE


class ProcessingDate(Input):
    business_date: date
    _date_input = field_validator("business_date", mode="before")(
        LoanCreate.date_input.__func__
    )
    _date_range = field_validator("business_date")(LoanCreate.supported_date.__func__)


class RepaymentCreate(ProcessingDate):
    amount_paise: int = Field(strict=True, ge=1, le=MAX_MONEY_PAISE)
    source: Reference
    external_event_id: Annotated[
        str,
        StringConstraints(
            strict=True, min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.:-]+$"
        ),
    ]
    occurred_at: AwareDatetime

    @field_validator("occurred_at", mode="before")
    @classmethod
    def timestamp_input(cls, value):
        if not isinstance(value, (str, datetime)):
            raise ValueError("Use an ISO timestamp with timezone")
        return value

    @field_validator("occurred_at")
    @classmethod
    def utc_timestamp(cls, value):
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def occurred_not_after_processing(self):
        if self.occurred_at.date() > self.business_date:
            raise ValueError(
                "Occurrence UTC date cannot follow the processing business date"
            )
        return self


class ReversalCreate(ProcessingDate):
    reason: Annotated[
        str,
        StringConstraints(
            strict=True, strip_whitespace=True, min_length=1, max_length=500
        ),
    ]
