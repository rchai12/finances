"""Charges that come again at a regular rhythm: subscriptions and bills. Pure: no database."""

import calendar
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise

CADENCES = ("week", "month", "quarter", "year")

# cadence: (fewest days between charges, most days, fewest charges)
_BANDS = {
    "week": (6, 8, 3),
    "month": (27, 33, 3),
    "quarter": (85, 97, 3),
    "year": (350, 380, 2),
}
# cadence: (numerator, denominator) of the factor from one charge to a month
_MONTHLY = {"week": (52, 12), "month": (1, 1), "quarter": (1, 3), "year": (1, 12)}
_STEP_MONTHS = {"month": 1, "quarter": 3, "year": 12}
_STEP_DAYS = 7


@dataclass(frozen=True)
class Charge:
    merchant: str
    day: date
    amount_cents: int


@dataclass(frozen=True)
class Recurring:
    merchant: str
    cadence: str
    amount_cents: int
    monthly_cents: int
    count: int
    first_day: date
    last_day: date
    next_day: date
    active: bool
    previous_cents: int | None = None


def monthly_cost(amount_cents: int, cadence: str) -> int:
    """What one charge of this cadence costs a month, rounded half up to whole cents."""
    numerator, denominator = _MONTHLY[cadence]
    return (2 * amount_cents * numerator + denominator) // (2 * denominator)


def next_charge(day: date, cadence: str) -> date:
    """The day the next charge is due; a short month moves it to the month's last day."""
    if cadence == "week":
        return day + timedelta(days=_STEP_DAYS)
    year, month = divmod(day.year * 12 + day.month - 1 + _STEP_MONTHS[cadence], 12)
    last = calendar.monthrange(year, month + 1)[1]
    return date(year, month + 1, min(day.day, last))


def _cadence(charges: list[Charge]) -> str | None:
    gaps = [(later.day - earlier.day).days for earlier, later in pairwise(charges)]
    for cadence in CADENCES:
        low, high, fewest = _BANDS[cadence]
        if len(charges) >= fewest and all(low <= gap <= high for gap in gaps):
            return cadence
    return None


def _series(charges: list[Charge], as_of: date) -> Recurring | None:
    cadence = _cadence(charges)
    if cadence is None:
        return None
    first, last = charges[0], charges[-1]
    amount = -last.amount_cents
    previous = -charges[-2].amount_cents
    return Recurring(
        merchant=last.merchant,
        cadence=cadence,
        amount_cents=amount,
        monthly_cents=monthly_cost(amount, cadence),
        count=len(charges),
        first_day=first.day,
        last_day=last.day,
        next_day=next_charge(last.day, cadence),
        active=as_of <= last.day + timedelta(days=_BANDS[cadence][1]),
        previous_cents=None if previous == amount else previous,
    )


def find_recurring(charges: Iterable[Charge], as_of: date) -> list[Recurring]:
    """Each merchant's charges as one series, or else each amount of that merchant on its own."""
    by_merchant: defaultdict[str, list[Charge]] = defaultdict(list)
    for charge in charges:
        if charge.amount_cents < 0:
            by_merchant[charge.merchant].append(charge)
    found = []
    for merchant_charges in by_merchant.values():
        ordered = sorted(merchant_charges, key=lambda charge: (charge.day, charge.amount_cents))
        whole = _series(ordered, as_of)
        if whole is not None:
            found.append(whole)
            continue
        by_amount: defaultdict[int, list[Charge]] = defaultdict(list)
        for charge in ordered:
            by_amount[charge.amount_cents].append(charge)
        for same_amount in by_amount.values():
            item = _series(same_amount, as_of)
            if item is not None:
                found.append(item)
    return sorted(
        found,
        key=lambda item: (
            not item.active,
            -item.monthly_cents,
            item.merchant.lower(),
            item.merchant,
            -item.amount_cents,
        ),
    )
