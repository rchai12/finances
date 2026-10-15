"""What counts as spending, and how it is grouped and totalled. Pure: no database."""

import calendar
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from finances.domain.models import Category

SPENDING = "spending"
INCOME = "income"
TRANSFER = "transfer"
UNSORTED_IN = "unsorted_in"
UNCATEGORIZED = "Uncategorized"
UNASSIGNED = "Unassigned"
NO_CARD = "No card"
BY = ("category", "group", "merchant", "person", "account", "bank", "card")

_MONTH = re.compile(r"([0-9]{4})-([0-9]{2})")
_BAD_MONTH = "month must be a year and month, like 2026-05"


@dataclass(frozen=True)
class Flow:
    amount_cents: int
    day: date
    kind: str
    category: str
    group: str
    merchant: str
    person: str
    account: str
    bank: str
    card: str


@dataclass(frozen=True)
class SpendingLine:
    label: str
    spent_cents: int
    count: int


@dataclass(frozen=True)
class SpendingSummary:
    spent_cents: int
    income_cents: int
    transfers: int
    unsorted_in_cents: int
    unsorted_in_count: int


def flow_kind(amount_cents: int, *, paired: bool, category: Category | None) -> str:
    if paired or (category is not None and category.is_transfer):
        return TRANSFER
    if category is not None and category.is_income:
        return INCOME
    if category is None and amount_cents > 0:
        return UNSORTED_IN
    return SPENDING


def check_by(by: str) -> None:
    if by not in BY:
        raise ValueError(f"by must be one of: {', '.join(BY)}")


def spending_lines(flows: Iterable[Flow], by: str) -> list[SpendingLine]:
    """Spending grouped by one field: largest spent first, then by label ignoring case."""
    check_by(by)
    spent: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    for flow in flows:
        if flow.kind == SPENDING:
            label = getattr(flow, by)
            spent[label] -= flow.amount_cents
            counts[label] += 1
    lines = [SpendingLine(label, spent[label], counts[label]) for label in counts]
    return sorted(lines, key=lambda line: (-line.spent_cents, line.label.lower(), line.label))


def summarize(flows: Iterable[Flow]) -> SpendingSummary:
    spent = income = transfers = unsorted_in = unsorted_count = 0
    for flow in flows:
        if flow.kind == SPENDING:
            spent -= flow.amount_cents
        elif flow.kind == INCOME:
            income += flow.amount_cents
        elif flow.kind == TRANSFER:
            transfers += 1
        else:
            unsorted_in += flow.amount_cents
            unsorted_count += 1
    return SpendingSummary(spent, income, transfers, unsorted_in, unsorted_count)


def month_bounds(day: date) -> tuple[date, date]:
    last = calendar.monthrange(day.year, day.month)[1]
    return day.replace(day=1), day.replace(day=last)


def month_range(text: str) -> tuple[date, date]:
    """The first and last day of a month written YYYY-MM."""
    found = _MONTH.fullmatch(text)
    if found is None:
        raise ValueError(_BAD_MONTH)
    try:
        first = date(int(found[1]), int(found[2]), 1)
    except ValueError:
        raise ValueError(_BAD_MONTH) from None
    return month_bounds(first)
