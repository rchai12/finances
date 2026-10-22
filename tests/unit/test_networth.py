from datetime import date

import pytest

from finances.domain.networth import NetWorthPoint, net_worth_points, point_days
from finances.views.charts import net_worth_chart
from finances.views.networth import NetWorthRow, net_worth_rows


@pytest.mark.parametrize(
    ("today", "months", "days"),
    [
        (date(2026, 5, 25), 3, [date(2026, 3, 31), date(2026, 4, 30), date(2026, 5, 25)]),
        (date(2026, 2, 10), 3, [date(2025, 12, 31), date(2026, 1, 31), date(2026, 2, 10)]),
        (date(2024, 3, 1), 2, [date(2024, 2, 29), date(2024, 3, 1)]),
        (date(2026, 4, 30), 1, [date(2026, 4, 30)]),
    ],
)
def test_one_day_a_month_ending_today(today: date, months: int, days: list[date]) -> None:
    assert point_days(today, months) == days


CHECKING = [(date(2026, 5, 20), 300000), (date(2026, 4, 30), 250000), (date(2026, 3, 15), 200000)]
CARD = [(date(2026, 5, 24), -45000), (date(2026, 4, 30), -30000)]
SAVINGS = [(date(2026, 5, 1), 100000)]
DAYS = [date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30), date(2026, 5, 25)]


def test_each_account_counts_its_newest_balance_on_or_before_the_day() -> None:
    assert net_worth_points([CHECKING, CARD, SAVINGS], DAYS) == [
        NetWorthPoint(date(2026, 3, 31), 200000, 1),
        NetWorthPoint(date(2026, 4, 30), 220000, 2),
        NetWorthPoint(date(2026, 5, 25), 355000, 3),
    ]


def test_two_balances_on_one_day_take_the_first_listed() -> None:
    same_day = [(date(2026, 5, 20), 310000), (date(2026, 5, 20), 300000)]
    assert net_worth_points([same_day], [date(2026, 5, 25)]) == [
        NetWorthPoint(date(2026, 5, 25), 310000, 1)
    ]


def test_nothing_before_the_first_balance() -> None:
    assert net_worth_points([CARD], [date(2026, 3, 31)]) == []
    assert net_worth_points([], DAYS) == []


def test_rows_and_chart() -> None:
    points = [
        NetWorthPoint(date(2026, 4, 30), -30000, 1),
        NetWorthPoint(date(2026, 5, 25), 355000, 3),
    ]
    assert net_worth_rows(points) == [
        NetWorthRow("2026-04-30", "-$300.00", "1"),
        NetWorthRow("2026-05-25", "$3,550.00", "3"),
    ]
    assert net_worth_chart(points) == {
        "kind": "line",
        "labels": ["2026-04-30", "2026-05-25"],
        "series": [{"name": "Net worth", "cents": [-30000, 355000]}],
    }
    assert net_worth_chart([]) is None
