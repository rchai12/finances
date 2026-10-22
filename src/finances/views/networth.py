"""Net worth over time as plain text."""

from dataclasses import dataclass

from finances.domain.money import format_cents
from finances.domain.networth import NetWorthPoint


@dataclass(frozen=True)
class NetWorthRow:
    date: str
    net_worth: str
    accounts: str


def net_worth_rows(points: list[NetWorthPoint]) -> list[NetWorthRow]:
    return [
        NetWorthRow(
            date=point.day.isoformat(),
            net_worth=format_cents(point.net_worth_cents),
            accounts=str(point.accounts),
        )
        for point in points
    ]
