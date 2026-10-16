"""Chart data for the account page: cents in, JSON shape for charts.js."""

from finances.analysis.account_page import AccountMonth
from finances.domain.models import BalanceSnapshot
from finances.domain.spending import SpendingLine


def pie_chart(lines: list[SpendingLine]) -> dict | None:
    """Pie of groups with positive spent; None when none remain."""
    kept = [line for line in lines if line.spent_cents > 0]
    if not kept:
        return None
    return {
        "kind": "pie",
        "labels": [line.label for line in kept],
        "series": [{"name": "Spent", "cents": [line.spent_cents for line in kept]}],
    }


def months_chart(months: list[AccountMonth]) -> dict:
    """Bars of spent and income for each month."""
    return {
        "kind": "bar",
        "labels": [month.start.isoformat()[:7] for month in months],
        "series": [
            {"name": "Spent", "cents": [month.spent_cents for month in months]},
            {"name": "Income", "cents": [month.income_cents for month in months]},
        ],
    }


def balance_chart(balances: list[BalanceSnapshot]) -> dict | None:
    """Line of balances oldest first; None when there are none."""
    if not balances:
        return None
    oldest_first = list(reversed(balances))
    return {
        "kind": "line",
        "labels": [item.as_of_date.isoformat() for item in oldest_first],
        "series": [{"name": "Balance", "cents": [item.balance_cents for item in oldest_first]}],
    }
