"""Bills and income expected in a window of days. Pure: no database."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from finances.domain.recurring import Recurring, next_charge

BILL = "bill"
INCOME = "income"


@dataclass(frozen=True)
class Upcoming:
    day: date
    kind: str
    merchant: str
    cadence: str
    amount_cents: int


def expected(
    bills: Iterable[Recurring], income: Iterable[Recurring], start: date, days: int
) -> list[Upcoming]:
    """Each due day of the active series that falls in the window, today counted as the first."""
    end = start + timedelta(days=days - 1)
    found: list[Upcoming] = []
    for item, kind, sign in (
        *((bill, BILL, -1) for bill in bills),
        *((credit, INCOME, 1) for credit in income),
    ):
        if not item.active:
            continue
        day = item.next_day
        while day <= end:
            if day >= start:
                found.append(
                    Upcoming(day, kind, item.merchant, item.cadence, sign * item.amount_cents)
                )
            day = next_charge(day, item.cadence)
    return sorted(
        found,
        key=lambda item: (
            item.day,
            0 if item.kind == INCOME else 1,
            item.merchant.lower(),
            item.merchant,
            item.amount_cents,
        ),
    )
