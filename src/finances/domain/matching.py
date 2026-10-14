"""Pair transactions from two sources by amount and day. Imports nothing from the project."""

from dataclasses import dataclass
from datetime import date

MATCH_MAX_DAYS = 5


@dataclass(frozen=True)
class MatchItem:
    """One transaction as the matcher sees it: the caller's key, an amount, and a day."""

    key: int
    amount_cents: int
    day: date


def match_one_to_one(
    left: list[MatchItem], right: list[MatchItem], max_days: int = MATCH_MAX_DAYS
) -> list[tuple[int, int]]:
    """Return (left key, right key) pairs with equal amounts and days at most max_days apart."""
    right_by_amount: dict[int, list[int]] = {}
    for position, item in enumerate(right):
        right_by_amount.setdefault(item.amount_cents, []).append(position)
    compatible = []
    for left_position, item in enumerate(left):
        for right_position in right_by_amount.get(item.amount_cents, []):
            gap = abs((item.day - right[right_position].day).days)
            if gap <= max_days:
                compatible.append((gap, left_position, right_position))
    compatible.sort()
    paired: dict[int, int] = {}
    taken: set[int] = set()
    for _, left_position, right_position in compatible:
        if left_position not in paired and right_position not in taken:
            paired[left_position] = right_position
            taken.add(right_position)
    return [(left[position].key, right[paired[position]].key) for position in sorted(paired)]
