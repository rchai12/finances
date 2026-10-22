"""Walk a balance through expected bills and income. Pure: no database."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from finances.domain.upcoming import Upcoming


@dataclass(frozen=True)
class Step:
    item: Upcoming
    balance_cents: int


@dataclass(frozen=True)
class Walk:
    steps: list[Step]
    in_cents: int
    out_cents: int
    end_cents: int
    lowest_cents: int
    lowest_day: date


def walk(balance_cents: int, start: date, items: Iterable[Upcoming]) -> Walk:
    """Add each item in order; the lowest point keeps the earliest day on a tie."""
    current = balance_cents
    in_cents = 0
    out_cents = 0
    lowest_cents = balance_cents
    lowest_day = start
    steps: list[Step] = []
    for item in items:
        current += item.amount_cents
        steps.append(Step(item, current))
        if item.amount_cents > 0:
            in_cents += item.amount_cents
        if item.amount_cents < 0:
            out_cents += item.amount_cents
        if current < lowest_cents:
            lowest_cents = current
            lowest_day = item.day
    return Walk(steps, in_cents, out_cents, current, lowest_cents, lowest_day)
