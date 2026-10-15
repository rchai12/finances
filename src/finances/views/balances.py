"""The balance report as plain text."""

from dataclasses import dataclass

from finances.analysis.balances import BalanceReport
from finances.domain.models import DataSource
from finances.domain.money import format_cents

_SOURCES = {DataSource.STATEMENT.value: "statement", DataSource.AGGREGATOR.value: "SimpleFIN"}


@dataclass(frozen=True)
class BalanceRow:
    account: str
    type: str
    balance: str
    as_of: str
    source: str


def balance_rows(report: BalanceReport) -> list[BalanceRow]:
    return [
        BalanceRow(
            account=line.account,
            type=line.type,
            balance="" if line.balance_cents is None else format_cents(line.balance_cents),
            as_of="" if line.as_of is None else line.as_of.isoformat(),
            source="" if line.source is None else _SOURCES[line.source],
        )
        for line in report.lines
    ]


def balance_summary(report: BalanceReport) -> list[str]:
    lines = [
        f"Cash: {format_cents(report.cash_cents)}. Cards: {format_cents(report.cards_cents)}. "
        f"Other: {format_cents(report.other_cents)}.",
        f"Net worth: {format_cents(report.net_worth_cents)}.",
    ]
    if report.without_balance:
        lines.append(f"No balance yet: {', '.join(report.without_balance)}.")
    return lines
