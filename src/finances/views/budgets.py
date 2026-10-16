"""Budgets as plain text for the terminal."""

from dataclasses import dataclass

from finances.domain.budgets import BudgetLine
from finances.domain.money import format_cents


@dataclass(frozen=True)
class BudgetTableRow:
    budget: str
    kind: str
    target: str
    spent: str
    left: str
    used: str
    month_gone: str


def budget_rows(lines: list[BudgetLine]) -> list[BudgetTableRow]:
    """Format each budget line for the table."""
    return [
        BudgetTableRow(
            budget=line.name,
            kind="group" if line.is_group else "category",
            target=format_cents(line.target_cents),
            spent=format_cents(line.spent_cents),
            left=format_cents(line.left_cents),
            used=f"{line.used_percent}%",
            month_gone=f"{line.month_gone_percent}%",
        )
        for line in lines
    ]


def budgets_summary(lines: list[BudgetLine]) -> str:
    """How many budgets are over."""
    count = sum(1 for line in lines if line.spent_cents > line.target_cents)
    return f"Over budget: {count}."
