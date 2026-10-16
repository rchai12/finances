"""The home page's numbers, gathered from earlier reports."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from finances.analysis.balances import BalanceReport, balance_report
from finances.analysis.budgets import budget_report
from finances.analysis.health import gather_health
from finances.analysis.insights import InsightsReport, insights_report
from finances.analysis.months import MonthLine, month_report
from finances.categorize.transfers import transfer_suggestions
from finances.db.repositories import count_uncategorized
from finances.domain.budgets import BudgetLine
from finances.domain.health import Problem


@dataclass(frozen=True)
class Dashboard:
    today: date
    balance: BalanceReport
    months: list[MonthLine]
    insights: InsightsReport
    problems: list[Problem]
    uncategorized: int
    transfers_waiting: int
    budgets: tuple[BudgetLine, ...] = ()


def dashboard(session: Session, today: date, backup_folder: Path) -> Dashboard:
    """Balances, two months, this month's findings, health, and what waits for a person."""
    first = date(today.year, today.month, 1)
    return Dashboard(
        today=today,
        balance=balance_report(session),
        months=month_report(session, today, 2),
        insights=insights_report(session, first),
        problems=gather_health(session, backup_folder, today),
        uncategorized=count_uncategorized(session),
        transfers_waiting=len(transfer_suggestions(session)),
        budgets=tuple(budget_report(session, first, today)),
    )
