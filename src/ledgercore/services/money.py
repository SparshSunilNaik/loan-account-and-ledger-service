from decimal import ROUND_HALF_UP, Decimal, localcontext

MAX_MONEY_PAISE = 100_000_000_000  # INR 100 crore
MAX_TENURE = 600
MAX_STORED_PAISE = 2**63 - 1


def round_paise(value: Decimal) -> int:
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or not 0 <= value <= MAX_STORED_PAISE
    ):
        raise ValueError("Amount must be a finite Decimal")
    with localcontext() as ctx:
        ctx.prec = 50
        rounded = int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if not 0 <= rounded <= MAX_STORED_PAISE:
        raise ValueError("Amount outside supported bounds")
    return rounded


def rupees_to_paise(value: Decimal) -> int:
    if (
        not isinstance(value, Decimal)
        or not value.is_finite()
        or not 0 <= value <= Decimal(MAX_MONEY_PAISE) / 100
    ):
        raise ValueError("Rupees must be a finite nonnegative Decimal")
    with localcontext() as ctx:
        ctx.prec = 50
        return round_paise(value * 100)
