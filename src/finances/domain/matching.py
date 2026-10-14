"""Pair transactions from two sources by amount and day. Imports nothing from the project."""

from dataclasses import dataclass
from datetime import date

MATCH_MAX_DAYS = 5

Score = tuple[int, int, int]


@dataclass(frozen=True)
class MatchItem:
    """One transaction as the matcher sees it: the caller's key, an amount, a day, and a zone."""

    key: int
    amount_cents: int
    day: date
    zone: int = 0


def period_zone(day: date, periods: list[tuple[date, date]]) -> int:
    """Return 2k before the k-th period by first day, 2k + 1 inside it, and 2n after all n."""
    ordered = sorted(periods)
    for index, (first, last) in enumerate(ordered):
        if day < first:
            return 2 * index
        if day <= last:
            return 2 * index + 1
    return 2 * len(ordered)


def _gain(one: MatchItem, other: MatchItem, max_days: int) -> Score | None:
    """The score one pair adds: a pair, whether it stays in one zone, and minus its days apart."""
    gap = abs((one.day - other.day).days)
    if gap > max_days:
        return None
    return (1, int(one.zone == other.zone), -gap)


def _plus(one: Score, other: Score) -> Score:
    return (one[0] + other[0], one[1] + other[1], one[2] + other[2])


def _pair_sorted(
    left: list[MatchItem], right: list[MatchItem], max_days: int
) -> list[tuple[int, int]]:
    """Pair two day-sorted lists of one amount without crossing, scoring best; return indexes."""
    rows, columns = len(left), len(right)
    best: list[list[Score]] = [[(0, 0, 0)] * (columns + 1) for _ in range(rows + 1)]
    for i in range(rows - 1, -1, -1):
        for j in range(columns - 1, -1, -1):
            found = max(best[i + 1][j], best[i][j + 1])
            gain = _gain(left[i], right[j], max_days)
            if gain is not None:
                found = max(found, _plus(gain, best[i + 1][j + 1]))
            best[i][j] = found
    pairs = []
    i = j = 0
    while i < rows and j < columns:
        gain = _gain(left[i], right[j], max_days)
        if gain is not None and _plus(gain, best[i + 1][j + 1]) == best[i][j]:
            pairs.append((i, j))
            i, j = i + 1, j + 1
        elif best[i][j + 1] == best[i][j]:
            j += 1
        else:
            i += 1
    return pairs


def match_one_to_one(
    left: list[MatchItem], right: list[MatchItem], max_days: int = MATCH_MAX_DAYS
) -> list[tuple[int, int]]:
    """Return (left key, right key) pairs with equal amounts and days at most max_days apart.

    Each amount is paired on its own: the most pairs, then the most pairs within one zone, then
    the fewest days apart, preferring earlier items when pairings score the same.
    """
    left_by_amount: dict[int, list[int]] = {}
    for position, item in enumerate(left):
        left_by_amount.setdefault(item.amount_cents, []).append(position)
    right_by_amount: dict[int, list[int]] = {}
    for position, item in enumerate(right):
        right_by_amount.setdefault(item.amount_cents, []).append(position)
    paired: list[tuple[int, int]] = []
    for amount, left_positions in left_by_amount.items():
        lefts = sorted(left_positions, key=lambda position: (left[position].day, position))
        rights = sorted(
            right_by_amount.get(amount, []),
            key=lambda position: (right[position].day, position),
        )
        found = _pair_sorted([left[p] for p in lefts], [right[p] for p in rights], max_days)
        paired += [(lefts[i], rights[j]) for i, j in found]
    return [(left[i].key, right[j].key) for i, j in sorted(paired)]
