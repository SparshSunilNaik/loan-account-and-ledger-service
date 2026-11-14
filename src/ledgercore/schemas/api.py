import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from ledgercore.services.money import MAX_MONEY_PAISE, MAX_TENURE

Reference = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    ),
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BorrowerCreate(Input):
    external_reference: Reference
    full_name: Annotated[
        str,
        StringConstraints(
            strict=True, strip_whitespace=True, min_length=1, max_length=200
        ),
    ]
    phone: (
        Annotated[str, StringConstraints(strict=True, pattern=r"^\+?[0-9]{7,15}$")]
        | None
    ) = None


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BorrowerRead(Output):
    id: UUID
    external_reference: str
    full_name: str
    phone: str | None
    created_at: datetime


class LoanCreate(Input):
    external_reference: Reference
    borrower_id: UUID
    product_id: UUID
    principal_paise: int = Field(strict=True, ge=1, le=MAX_MONEY_PAISE)
    tenure_periods: int = Field(strict=True, ge=1, le=MAX_TENURE)
    first_due_date: date

    @field_validator("first_due_date", mode="before")
    @classmethod
    def date_input(cls, value):
        if type(value) is date:
            return value
        if not isinstance(value, str) or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value
        ):
            raise ValueError("Use an ISO date in YYYY-MM-DD format")
        return value

    @field_validator("first_due_date")
    @classmethod
    def supported_date(cls, value: date) -> date:
        if not date(1900, 1, 1) <= value <= date(2100, 12, 31):
            raise ValueError("First due date must be between 1900 and 2100")
        return value


class ProductRead(Output):
    id: UUID
    code: str
    name: str
    annual_rate: Decimal
    interest_method: Literal["flat", "reducing"]
    frequency: Literal["weekly", "monthly"]
    currency: Literal["INR"]
    active: bool


class LoanRead(Output):
    id: UUID
    external_reference: str
    borrower_id: UUID
    product_id: UUID
    principal_paise: int
    tenure_periods: int
    first_due_date: date
    annual_rate: Decimal
    interest_method: str
    frequency: str
    currency: Literal["INR"]
    schedule_version: str
    status: str
    created_at: datetime


class ScheduleRead(Output):
    id: UUID
    loan_id: UUID
    instalment_number: int
    due_date: date
    principal_due_paise: int
    interest_due_paise: int
