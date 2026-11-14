from datetime import date
from decimal import Decimal, localcontext

import pytest

from ledgercore.services.money import MAX_MONEY_PAISE, round_paise, rupees_to_paise
from ledgercore.services.schedules import generate_schedule


def calc(
    p=100_000, rate="0.12", n=3, method="flat", freq="monthly", first=date(2026, 1, 31)
):
    return generate_schedule(p, Decimal(rate), n, method, freq, first)


def test_flat_monthly_independent_example():
    # INR 1,000 * 12% * 3/12 = INR 30; 100000 / 3 has remainder 1.
    rows = calc()
    assert [(r.principal_due_paise, r.interest_due_paise) for r in rows] == [
        (33333, 1000),
        (33333, 1000),
        (33334, 1000),
    ]
    assert [r.due_date for r in rows] == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]


def test_flat_weekly_independent_example():
    # 52000 * .26 * 4/52 = 1040 paise, 260 each week.
    rows = calc(52000, "0.26", 4, freq="weekly")
    assert [(r.principal_due_paise, r.interest_due_paise) for r in rows] == [
        (13000, 260)
    ] * 4
    assert [r.due_date for r in rows] == [
        date(2026, 1, 31),
        date(2026, 2, 7),
        date(2026, 2, 14),
        date(2026, 2, 21),
    ]


def test_reducing_two_periods_independent_example():
    # P=10000 paise, r=.01, n=2 -> EMI=5075.124378... -> 5075.
    # First interest=100, principal=4975; second balance=5025, interest=50.
    rows = calc(10000, "0.12", 2, "reducing")
    assert [(r.principal_due_paise, r.interest_due_paise) for r in rows] == [
        (4975, 100),
        (5025, 50),
    ]


def test_reducing_year_example():
    # Independently tabulated amortization: INR 12000, 12%, 12 months.
    rows = calc(1_200_000, "0.12", 12, "reducing")
    assert (rows[0].principal_due_paise, rows[0].interest_due_paise) == (94619, 12000)
    assert rows[0].principal_due_paise + rows[0].interest_due_paise == 106619
    assert sum(r.interest_due_paise for r in rows) == 79423
    assert (rows[-1].principal_due_paise, rows[-1].interest_due_paise) == (105558, 1056)


def test_reducing_weekly():
    # Annual .52 / 52 = .01, same two-period example as monthly .12 / 12.
    rows = calc(10000, "0.52", 2, "reducing", "weekly")
    assert [(r.principal_due_paise, r.interest_due_paise) for r in rows] == [
        (4975, 100),
        (5025, 50),
    ]


@pytest.mark.parametrize(
    "method,expected", [("flat", [33, 33, 34]), ("reducing", [33, 33, 34])]
)
def test_zero_interest(method, expected):
    rows = calc(100, "0", 3, method)
    assert [r.principal_due_paise for r in rows] == expected
    assert sum(r.interest_due_paise for r in rows) == 0


def test_flat_interest_remainder():
    rows = calc(100, "0.12", 3)
    assert [r.interest_due_paise for r in rows] == [1, 1, 1]
    rows = calc(101, "0.20", 3)
    assert [r.interest_due_paise for r in rows] == [1, 1, 3]  # rounded total 5


@pytest.mark.parametrize("p", [1, 2, 101, 100003, MAX_MONEY_PAISE])
@pytest.mark.parametrize("n", [1, 3, 52, 600])
@pytest.mark.parametrize("rate", ["0", "0.12", "1"])
@pytest.mark.parametrize("method", ["flat", "reducing"])
@pytest.mark.parametrize("freq", ["weekly", "monthly"])
def test_invariants(p, n, rate, method, freq):
    rows = calc(p, rate, n, method, freq)
    assert len(rows) == n
    assert sum(row.principal_due_paise for row in rows) == p
    assert all(
        row.principal_due_paise >= 0 and row.interest_due_paise >= 0 for row in rows
    )
    assert [r.instalment_number for r in rows] == list(range(1, n + 1))
    assert all(a.due_date < b.due_date for a, b in zip(rows, rows[1:], strict=False))


@pytest.mark.parametrize(
    "args",
    [
        (True, Decimal("0.12"), 3, "flat", "weekly"),
        (0, Decimal("0.12"), 3, "flat", "weekly"),
        (100, 0.12, 3, "flat", "weekly"),
        (100, Decimal("NaN"), 3, "flat", "weekly"),
        (100, Decimal("Infinity"), 3, "flat", "weekly"),
        (100, Decimal("-0.1"), 3, "flat", "weekly"),
        (100, Decimal("1.01"), 3, "flat", "weekly"),
        (100, Decimal("0"), 0, "flat", "weekly"),
        (100, Decimal("0"), 601, "flat", "weekly"),
        (100, Decimal("0"), True, "flat", "weekly"),
        (100, Decimal("0"), 3, "other", "weekly"),
        (100, Decimal("0"), 3, "flat", "daily"),
    ],
)
def test_invalid_domain_inputs(args):
    with pytest.raises(ValueError):
        generate_schedule(*args, date(2026, 1, 1))


def test_half_up_and_precision_independence():
    assert rupees_to_paise(Decimal("1.005")) == 101
    assert round_paise(Decimal("2.5")) == 3
    expected = calc(method="reducing")
    with localcontext() as ctx:
        ctx.prec = 6
        assert calc(method="reducing") == expected


@pytest.mark.parametrize(
    "value",
    [
        Decimal("-1"),
        Decimal("-0.1"),
        Decimal("NaN"),
        Decimal("Infinity"),
        1.0,
        Decimal(2**63),
    ],
)
def test_invalid_money(value):
    with pytest.raises(ValueError):
        round_paise(value)


def test_leap_month_anchor():
    rows = calc(first=date(2028, 1, 31))
    assert [r.due_date for r in rows] == [
        date(2028, 1, 31),
        date(2028, 2, 29),
        date(2028, 3, 31),
    ]
