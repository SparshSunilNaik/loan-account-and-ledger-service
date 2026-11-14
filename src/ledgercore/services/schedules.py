from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, localcontext
from typing import Literal

from ledgercore.services.money import MAX_MONEY_PAISE, MAX_TENURE, round_paise


@dataclass(frozen=True)
class Instalment:
    instalment_number: int
    due_date: date
    principal_due_paise: int
    interest_due_paise: int


def due_date(first: date, offset: int, frequency: str) -> date:
    if frequency == "weekly":
        return first + timedelta(weeks=offset)
    month = first.year * 12 + first.month - 1 + offset
    year, month0 = divmod(month, 12)
    return date(year, month0 + 1, min(first.day, monthrange(year, month0 + 1)[1]))


def generate_schedule(
    principal_paise: int,
    annual_rate: Decimal,
    tenure_periods: int,
    interest_method: Literal["flat", "reducing"],
    frequency: Literal["weekly", "monthly"],
    first_due_date: date,
) -> list[Instalment]:
    if type(principal_paise) is not int or not 1 <= principal_paise <= MAX_MONEY_PAISE:
        raise ValueError("Invalid principal")
    if type(tenure_periods) is not int or not 1 <= tenure_periods <= MAX_TENURE:
        raise ValueError("Invalid tenure")
    if (
        not isinstance(annual_rate, Decimal)
        or not annual_rate.is_finite()
        or not 0 <= annual_rate <= 1
    ):
        raise ValueError("Annual rate must be a Decimal fraction between 0 and 1")
    if interest_method not in ("flat", "reducing") or frequency not in (
        "weekly",
        "monthly",
    ):
        raise ValueError("Unsupported method or frequency")
    with localcontext() as ctx:
        ctx.prec = 50
        p, n = Decimal(principal_paise), tenure_periods
        r = annual_rate / (52 if frequency == "weekly" else 12)
        rows = []
        balance = principal_paise
        if interest_method == "flat":
            total_interest = round_paise(p * r * n)
            # Floor regular components; all remainder belongs to the final row.
            regular_principal = principal_paise // n
            regular_interest = total_interest // n
        else:
            emi = p / n if not r else p * r * (1 + r) ** n / ((1 + r) ** n - 1)
            payment = round_paise(emi)
        for i in range(n):
            final = i == n - 1
            if interest_method == "flat":
                principal = balance if final else regular_principal
                interest = (
                    total_interest - regular_interest * i if final else regular_interest
                )
            else:
                interest = round_paise(Decimal(balance) * r)
                principal = (
                    balance if final else min(balance, max(0, payment - interest))
                )
            balance -= principal
            rows.append(
                Instalment(
                    i + 1, due_date(first_due_date, i, frequency), principal, interest
                )
            )
        return rows
