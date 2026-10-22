"""The account page as plain text."""

from dataclasses import dataclass

from finances.analysis.account_page import AccountPage
from finances.domain.models import DataSource
from finances.domain.money import format_cents
from finances.domain.people import JOINT
from finances.views.format import net_text
from finances.views.spending import SpendingRow

_SOURCES = {DataSource.STATEMENT.value: "statement", DataSource.AGGREGATOR.value: "SimpleFIN"}


@dataclass(frozen=True)
class AccountMonthRow:
    month: str
    spent: str
    income: str


@dataclass(frozen=True)
class BalanceHistoryRow:
    date: str
    balance: str
    source: str


def account_detail_rows(page: AccountPage) -> list[tuple[str, str]]:
    """Name, institution, type, last 4, owner, status, and newest balance."""
    account = page.account
    owner = ""
    if page.owner == JOINT:
        owner = "Joint"
    elif page.owner is not None:
        owner = page.owner
    if page.balances:
        newest = page.balances[0]
        balance = (
            f"{format_cents(newest.balance_cents)} on {newest.as_of_date.isoformat()} "
            f"({_SOURCES[newest.source.value]})"
        )
    else:
        balance = "No balance yet"
    return [
        ("Name", account.name),
        ("Institution", account.institution),
        ("Type", account.type.value),
        ("Last 4", account.last4 or ""),
        ("Owner", owner),
        ("Status", "open" if account.is_active else "closed"),
        ("Balance", balance),
    ]


def group_rows(page: AccountPage) -> list[SpendingRow]:
    """Spending by group for the chosen month."""
    return [
        SpendingRow(
            line.label,
            format_cents(line.purchases_cents),
            format_cents(line.refunds_cents),
            net_text(line.spent_cents),
            str(line.count),
        )
        for line in page.spending
    ]


def account_month_rows(page: AccountPage) -> list[AccountMonthRow]:
    """Spent and income for each of the twelve months."""
    return [
        AccountMonthRow(
            month.start.isoformat()[:7],
            net_text(month.spent_cents),
            format_cents(month.income_cents),
        )
        for month in page.months
    ]


def balance_history_rows(page: AccountPage) -> list[BalanceHistoryRow]:
    """Each snapshot, newest first."""
    return [
        BalanceHistoryRow(
            item.as_of_date.isoformat(),
            format_cents(item.balance_cents),
            _SOURCES[item.source.value],
        )
        for item in page.balances
    ]
