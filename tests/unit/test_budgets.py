from datetime import date

import pytest

from finances.domain.budgets import BudgetLine, BudgetTarget, budget_lines, month_gone_percent
from finances.domain.insights import TYPES, Finding, over_budget

MAY = (date(2026, 5, 1), date(2026, 5, 31))


def test_over_budget_comes_after_fees() -> None:
    assert TYPES.index("over_budget") == TYPES.index("fees") + 1
    assert TYPES[-2:] == ("duplicate", "large_first_charge")


@pytest.mark.parametrize(
    ("today", "percent"),
    [
        (date(2026, 4, 30), 0),
        (date(2026, 5, 1), 3),
        (date(2026, 5, 16), 52),
        (date(2026, 5, 31), 100),
        (date(2026, 6, 1), 100),
    ],
)
def test_month_gone_percent(today: date, percent: int) -> None:
    assert month_gone_percent(*MAY, today) == percent


def test_budget_lines() -> None:
    targets = [
        BudgetTarget("Groceries", False, 20000),
        BudgetTarget("Food", True, 40000),
        BudgetTarget("dining", False, 25000),
        BudgetTarget("Travel", True, 10000),
    ]
    lines = budget_lines(
        targets,
        {"Groceries": 10000, "dining": 30000, "Coffee & Dessert": 450},
        {"Food": 40450},
        *MAY,
        date(2026, 6, 3),
    )
    assert lines == [
        BudgetLine("dining", False, 25000, 30000, -5000, 120, 100),
        BudgetLine("Food", True, 40000, 40450, -450, 101, 100),
        BudgetLine("Groceries", False, 20000, 10000, 10000, 50, 100),
        BudgetLine("Travel", True, 10000, 0, 10000, 0, 100),
    ]


def test_used_percent_rounds_half_up_and_can_go_below_zero() -> None:
    lines = budget_lines(
        [BudgetTarget("A", False, 800), BudgetTarget("B", False, 1000)],
        {"A": 4, "B": -250},
        {},
        *MAY,
        date(2026, 5, 16),
    )
    assert [(line.used_percent, line.month_gone_percent) for line in lines] == [(1, 52), (-25, 52)]


def test_over_budget() -> None:
    lines = [
        BudgetLine("Dining", False, 25000, 30000, -5000, 120, 100),
        BudgetLine("Food", True, 40000, 60000, -20000, 150, 100),
        BudgetLine("Groceries", False, 20000, 20000, 0, 100, 100),
        BudgetLine("Travel", True, 10000, 14999, -4999, 150, 100),
    ]
    month = date(2026, 5, 1)
    assert over_budget(month, lines) == [
        Finding(
            "over_budget",
            "medium",
            month,
            "Dining",
            5000,
            "Dining: $300.00 spent against a budget of $250.00.",
        ),
        Finding(
            "over_budget",
            "high",
            month,
            "Food",
            20000,
            "Food: $600.00 spent against a budget of $400.00.",
        ),
        Finding(
            "over_budget",
            "medium",
            month,
            "Travel",
            4999,
            "Travel: $149.99 spent against a budget of $100.00.",
        ),
    ]
    assert over_budget(month, []) == []
