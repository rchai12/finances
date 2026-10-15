from datetime import date

import pytest

from finances.domain.recurring import (
    CADENCES,
    Charge,
    Recurring,
    find_recurring,
    monthly_cost,
    next_charge,
)

AS_OF = date(2026, 5, 1)


def charges(merchant: str, cents: int, *days: date) -> list[Charge]:
    return [Charge(merchant, day, cents) for day in days]


def test_the_cadences() -> None:
    assert CADENCES == ("week", "month", "quarter", "year")


def test_a_monthly_subscription() -> None:
    found = find_recurring(
        charges(
            "QUUX STREAMING",
            -1599,
            date(2026, 1, 5),
            date(2026, 2, 5),
            date(2026, 3, 5),
            date(2026, 4, 5),
        ),
        AS_OF,
    )
    assert found == [
        Recurring(
            merchant="QUUX STREAMING",
            cadence="month",
            amount_cents=1599,
            monthly_cents=1599,
            count=4,
            first_day=date(2026, 1, 5),
            last_day=date(2026, 4, 5),
            next_day=date(2026, 5, 5),
            active=True,
        )
    ]


def test_a_price_rise_keeps_one_series_at_the_latest_amount() -> None:
    found = find_recurring(
        charges("ACME GYM", -3000, date(2026, 1, 10), date(2026, 2, 10))
        + charges("ACME GYM", -3500, date(2026, 3, 10)),
        AS_OF,
    )
    assert [(item.merchant, item.amount_cents, item.count) for item in found] == [
        ("ACME GYM", 3500, 3)
    ]


def test_one_merchant_billing_several_subscriptions() -> None:
    found = find_recurring(
        charges("FOOBAR APPS", -299, date(2026, 1, 3), date(2026, 2, 3), date(2026, 3, 3))
        + charges("FOOBAR APPS", -999, date(2026, 1, 20), date(2026, 2, 20), date(2026, 3, 20)),
        AS_OF,
    )
    assert [(item.merchant, item.cadence, item.amount_cents) for item in found] == [
        ("FOOBAR APPS", "month", 999),
        ("FOOBAR APPS", "month", 299),
    ]


def test_each_cadence_and_its_monthly_cost() -> None:
    found = find_recurring(
        charges(
            "BAZ BOX",
            -1200,
            date(2026, 4, 3),
            date(2026, 4, 10),
            date(2026, 4, 17),
            date(2026, 4, 24),
        )
        + charges("QUUX INSURANCE", -4500, date(2025, 10, 15), date(2026, 1, 15), date(2026, 4, 15))
        + charges("QUUX CLOUD", -9900, date(2025, 3, 1), date(2026, 3, 1)),
        AS_OF,
    )
    assert [(item.merchant, item.cadence, item.monthly_cents, item.next_day) for item in found] == [
        ("BAZ BOX", "week", 5200, date(2026, 5, 1)),
        ("QUUX INSURANCE", "quarter", 1500, date(2026, 7, 15)),
        ("QUUX CLOUD", "year", 825, date(2027, 3, 1)),
    ]


@pytest.mark.parametrize(
    "items",
    [
        charges("ACME COFFEE", -450, date(2026, 1, 2), date(2026, 1, 9), date(2026, 1, 30)),
        charges("ACME COFFEE", -450, date(2026, 2, 5), date(2026, 3, 5)),
        charges("ACME COFFEE", -450, date(2026, 1, 5), date(2026, 1, 5), date(2026, 2, 5)),
        charges("ACME COFFEE", -450, date(2026, 1, 5), date(2026, 3, 5), date(2026, 4, 5)),
        charges("ACME COFFEE", -450, date(2025, 3, 1)),
        [],
    ],
    ids=["irregular", "two-months", "same-day", "a-missed-month", "one-year-charge", "none"],
)
def test_not_recurring(items: list[Charge]) -> None:
    assert find_recurring(items, AS_OF) == []


@pytest.mark.parametrize(("as_of", "active"), [(date(2026, 5, 8), True), (date(2026, 5, 9), False)])
def test_active_until_the_latest_a_next_charge_could_come(as_of: date, active: bool) -> None:
    found = find_recurring(
        charges("QUUX STREAMING", -1599, date(2026, 2, 5), date(2026, 3, 5), date(2026, 4, 5)),
        as_of,
    )
    assert [item.active for item in found] == [active]


def test_the_largest_monthly_cost_comes_first_then_the_name() -> None:
    found = find_recurring(
        charges("beta", -500, date(2026, 1, 5), date(2026, 2, 5), date(2026, 3, 5))
        + charges("Alpha", -500, date(2026, 1, 6), date(2026, 2, 6), date(2026, 3, 6))
        + charges("Gamma", -800, date(2026, 1, 7), date(2026, 2, 7), date(2026, 3, 7)),
        AS_OF,
    )
    assert [item.merchant for item in found] == ["Gamma", "Alpha", "beta"]


@pytest.mark.parametrize(
    ("cents", "cadence", "monthly"),
    [
        (1000, "week", 4333),
        (1001, "week", 4338),
        (1000, "month", 1000),
        (1000, "quarter", 333),
        (1001, "quarter", 334),
        (1000, "year", 83),
        (1002, "year", 84),
    ],
)
def test_monthly_cost_rounds_half_up(cents: int, cadence: str, monthly: int) -> None:
    assert monthly_cost(cents, cadence) == monthly


@pytest.mark.parametrize(
    ("day", "cadence", "after"),
    [
        (date(2026, 1, 31), "week", date(2026, 2, 7)),
        (date(2026, 1, 31), "month", date(2026, 2, 28)),
        (date(2026, 11, 30), "quarter", date(2027, 2, 28)),
        (date(2024, 2, 29), "year", date(2025, 2, 28)),
    ],
)
def test_next_charge_keeps_the_day_of_the_month_where_it_can(
    day: date, cadence: str, after: date
) -> None:
    assert next_charge(day, cadence) == after
