"""Net worth on a set of days, from each account's newest balance on or before that day."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

from finances.domain.periods import months_ending


@dataclass(frozen=True)
class NetWorthPoint:
    day: date
    net_worth_cents: int
    accounts: int


def point_days(today: date, months: int) -> list[date]:
    """One day a month, oldest first: the month's last day, except today for this month."""
    days = [end for _, end in months_ending(today, months)]
    days[-1] = today
    return days


def net_worth_points(
    balances: Iterable[Sequence[tuple[date, int]]], days: Iterable[date]
) -> list[NetWorthPoint]:
    """Sum, per day, each account's first snapshot on or before that day (newest first)."""
    accounts = [list(items) for items in balances]
    found: list[NetWorthPoint] = []
    for day in days:
        total = 0
        counted = 0
        for snapshots in accounts:
            pick = next((cents for when, cents in snapshots if when <= day), None)
            if pick is not None:
                total += pick
                counted += 1
        if counted:
            found.append(NetWorthPoint(day, total, counted))
    return found
