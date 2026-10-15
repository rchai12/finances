"""Calendar months, and which accounts' data covers a range. Pure: no database."""

from collections.abc import Mapping
from datetime import date

from finances.domain.spending import month_bounds

MONTHS_MAX = 24


def months_ending(day: date, count: int) -> list[tuple[date, date]]:
    """The first and last day of `count` months, oldest first, the last being day's month."""
    if not 1 <= count <= MONTHS_MAX:
        raise ValueError(f"count must be from 1 to {MONTHS_MAX}")
    last = day.year * 12 + day.month - 1
    return [
        month_bounds(date(index // 12, index % 12 + 1, 1))
        for index in range(last - count + 1, last + 1)
    ]


def uncovered(spans: Mapping[str, tuple[date, date] | None], start: date, end: date) -> list[str]:
    """The names whose data does not reach from start to end, ignoring case in the order."""
    names = [
        name
        for name, span in spans.items()
        if span is None or not (span[0] <= start and span[1] >= end)
    ]
    return sorted(names, key=lambda name: (name.lower(), name))
