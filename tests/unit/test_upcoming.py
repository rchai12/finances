from datetime import date

import pytest

from finances.domain.recurring import (
    INCOME_CADENCES,
    Charge,
    Recurring,
    find_recurring,
    find_recurring_income,
    monthly_cost,
    next_charge,
)
from finances.domain.upcoming import BILL, INCOME, Upcoming, expected

AS_OF = date(2026, 5, 25)


def charges(merchant: str, cents: int, *days: date) -> list[Charge]:
    return [Charge(merchant, day, cents) for day in days]


def series(
    merchant: str, cadence: str, amount: int, last: date, next_day: date, active: bool = True
) -> Recurring:
    return Recurring(
        merchant=merchant,
        cadence=cadence,
        amount_cents=amount,
        monthly_cents=0,
        count=3,
        first_day=date(2026, 1, 1),
        last_day=last,
        next_day=next_day,
        active=active,
    )


def test_income_has_a_two_week_band() -> None:
    assert INCOME_CADENCES == ("week", "two_weeks", "month", "quarter", "year")
    assert next_charge(date(2026, 5, 15), "two_weeks") == date(2026, 5, 29)
    assert monthly_cost(300000, "two_weeks") == 650000
    assert monthly_cost(100001, "two_weeks") == 216669


def test_a_paycheck_every_two_weeks() -> None:
    found = find_recurring_income(
        charges(
            "PAYCHECK EXAMPLE CORP",
            300000,
            date(2026, 4, 3),
            date(2026, 4, 17),
            date(2026, 5, 1),
            date(2026, 5, 15),
        ),
        AS_OF,
    )
    assert found == [
        Recurring(
            merchant="PAYCHECK EXAMPLE CORP",
            cadence="two_weeks",
            amount_cents=300000,
            monthly_cents=650000,
            count=4,
            first_day=date(2026, 4, 3),
            last_day=date(2026, 5, 15),
            next_day=date(2026, 5, 29),
            active=True,
        )
    ]


def test_pay_on_the_15th_and_the_last_day_counts_as_every_two_weeks() -> None:
    days = (date(2026, 1, 15), date(2026, 1, 31), date(2026, 2, 15), date(2026, 2, 28))
    found = find_recurring_income(charges("PAYCHECK", 250000, *days), date(2026, 3, 1))
    assert [(item.cadence, item.count, item.next_day) for item in found] == [
        ("two_weeks", 4, date(2026, 3, 14))
    ]


def test_income_ignores_money_out_and_charges_ignore_the_new_band() -> None:
    days = (date(2026, 4, 3), date(2026, 4, 17), date(2026, 5, 1), date(2026, 5, 15))
    assert find_recurring_income(charges("ACME CLEANING", -9000, *days), AS_OF) == []
    assert find_recurring(charges("ACME CLEANING", -9000, *days), AS_OF) == []


def test_expected_bills_and_income_in_a_window() -> None:
    bills = [
        series("QUUX STREAMING", "month", 1599, date(2026, 5, 5), date(2026, 6, 5)),
        series("BAZ BOX", "week", 1200, date(2026, 5, 22), date(2026, 5, 29)),
        series("QUUX CLOUD", "year", 9900, date(2025, 6, 10), date(2026, 6, 10)),
        series("OLD GYM", "month", 2500, date(2026, 1, 1), date(2026, 2, 1), active=False),
        series("LATE BILL", "month", 4000, date(2026, 4, 20), date(2026, 5, 20)),
    ]
    income = [
        series("PAYCHECK EXAMPLE CORP", "two_weeks", 300000, date(2026, 5, 15), date(2026, 5, 29))
    ]
    assert expected(bills, income, AS_OF, 30) == [
        Upcoming(date(2026, 5, 29), INCOME, "PAYCHECK EXAMPLE CORP", "two_weeks", 300000),
        Upcoming(date(2026, 5, 29), BILL, "BAZ BOX", "week", -1200),
        Upcoming(date(2026, 6, 5), BILL, "BAZ BOX", "week", -1200),
        Upcoming(date(2026, 6, 5), BILL, "QUUX STREAMING", "month", -1599),
        Upcoming(date(2026, 6, 10), BILL, "QUUX CLOUD", "year", -9900),
        Upcoming(date(2026, 6, 12), INCOME, "PAYCHECK EXAMPLE CORP", "two_weeks", 300000),
        Upcoming(date(2026, 6, 12), BILL, "BAZ BOX", "week", -1200),
        Upcoming(date(2026, 6, 19), BILL, "BAZ BOX", "week", -1200),
        Upcoming(date(2026, 6, 20), BILL, "LATE BILL", "month", -4000),
    ]


@pytest.mark.parametrize(("days", "last"), [(1, date(2026, 5, 25)), (5, date(2026, 5, 29))])
def test_the_window_counts_today_as_its_first_day(days: int, last: date) -> None:
    bills = [series("BAZ BOX", "week", 1200, date(2026, 5, 18), date(2026, 5, 25))]
    found = expected(bills, [], AS_OF, days)
    assert [item.day for item in found] == [date(2026, 5, 25)]
    assert all(item.day <= last for item in found)


def test_nothing_expected() -> None:
    assert expected([], [], AS_OF, 30) == []
