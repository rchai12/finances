from datetime import date

from finances.domain.forecast import Step, Walk, walk
from finances.domain.upcoming import BILL, INCOME, Upcoming

START = date(2026, 5, 25)


def bill(day: date, merchant: str, cents: int) -> Upcoming:
    return Upcoming(day, BILL, merchant, "month", -cents)


def pay(day: date, merchant: str, cents: int) -> Upcoming:
    return Upcoming(day, INCOME, merchant, "two_weeks", cents)


def test_a_dip_before_payday() -> None:
    items = [
        bill(date(2026, 5, 27), "ACME UTILITY", 12000),
        pay(date(2026, 5, 29), "PAYCHECK EXAMPLE CORP", 300000),
        bill(date(2026, 6, 2), "PAYMENT TO TEST CARD", 50000),
        pay(date(2026, 6, 12), "PAYCHECK EXAMPLE CORP", 300000),
    ]
    assert walk(30000, START, items) == Walk(
        steps=[
            Step(items[0], 18000),
            Step(items[1], 318000),
            Step(items[2], 268000),
            Step(items[3], 568000),
        ],
        in_cents=600000,
        out_cents=-62000,
        end_cents=568000,
        lowest_cents=18000,
        lowest_day=date(2026, 5, 27),
    )


def test_the_start_is_the_lowest_when_nothing_dips() -> None:
    found = walk(100000, START, [pay(date(2026, 5, 30), "INTEREST PAID", 100)])
    assert (found.end_cents, found.lowest_cents, found.lowest_day) == (100100, 100000, START)


def test_a_tie_keeps_the_earliest_day() -> None:
    items = [
        bill(date(2026, 5, 26), "A", 500),
        pay(date(2026, 5, 27), "B", 500),
        bill(date(2026, 5, 28), "C", 500),
    ]
    found = walk(1000, START, items)
    assert (found.lowest_cents, found.lowest_day) == (500, date(2026, 5, 26))


def test_a_card_owed_more() -> None:
    items = [
        bill(date(2026, 5, 29), "BAZ BOX", 1200),
        pay(date(2026, 6, 3), "PAYMENT THANK YOU", 50000),
    ]
    found = walk(-45000, START, items)
    assert (found.end_cents, found.lowest_cents, found.lowest_day) == (
        3800,
        -46200,
        date(2026, 5, 29),
    )


def test_nothing_expected() -> None:
    assert walk(-2500, START, []) == Walk([], 0, 0, -2500, -2500, START)
