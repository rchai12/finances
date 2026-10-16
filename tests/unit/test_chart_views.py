from datetime import UTC, date, datetime

from finances.analysis.account_page import AccountMonth
from finances.domain.models import BalanceSnapshot, DataSource
from finances.domain.spending import SpendingLine
from finances.views.charts import balance_chart, months_chart, pie_chart


def test_pie_chart_drops_negative_and_zero_lines() -> None:
    assert (
        pie_chart(
            [
                SpendingLine("Food", -500, 1),
                SpendingLine("Home", 0, 0),
            ]
        )
        is None
    )
    assert pie_chart(
        [
            SpendingLine("Food", 1000, 1),
            SpendingLine("Home", 0, 0),
            SpendingLine("Shopping", -200, 1),
        ]
    ) == {
        "kind": "pie",
        "labels": ["Food"],
        "series": [{"name": "Spent", "cents": [1000]}],
    }


def test_months_chart_of_twelve_empty_months() -> None:
    months = [
        AccountMonth(date(2025, month, 1) if month >= 6 else date(2026, month, 1), 0, 0)
        for month in (6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5)
    ]
    assert months_chart(months) == {
        "kind": "bar",
        "labels": [
            "2025-06",
            "2025-07",
            "2025-08",
            "2025-09",
            "2025-10",
            "2025-11",
            "2025-12",
            "2026-01",
            "2026-02",
            "2026-03",
            "2026-04",
            "2026-05",
        ],
        "series": [
            {"name": "Spent", "cents": [0] * 12},
            {"name": "Income", "cents": [0] * 12},
        ],
    }


def test_balance_chart_keeps_two_snapshots_on_one_day_oldest_first() -> None:
    day = date(2026, 5, 20)
    made = datetime(2026, 5, 20, tzinfo=UTC)
    newer = BalanceSnapshot(2, 1, day, -20000, DataSource.AGGREGATOR, made)
    older = BalanceSnapshot(1, 1, day, -10000, DataSource.STATEMENT, made)
    assert balance_chart([newer, older]) == {
        "kind": "line",
        "labels": ["2026-05-20", "2026-05-20"],
        "series": [{"name": "Balance", "cents": [-10000, -20000]}],
    }
    assert balance_chart([]) is None
