"""Calendar months, and which accounts' data covers a range. Pure: no database."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from finances.domain.spending import month_bounds, month_range

MONTHS_MAX = 24
_DAY = timedelta(days=1)


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


def joined_periods(periods: Iterable[tuple[date, date]]) -> list[tuple[date, date]]:
    """Join periods that touch or overlap, oldest first. Two periods one day apart stay apart."""
    ordered = sorted(periods, key=lambda period: period[0])
    if not ordered:
        return []
    joined: list[list[date]] = [[ordered[0][0], ordered[0][1]]]
    for start, end in ordered[1:]:
        _, last_end = joined[-1]
        if start <= last_end + _DAY:
            joined[-1][1] = max(last_end, end)
        else:
            joined.append([start, end])
    return [(item[0], item[1]) for item in joined]


def statement_gaps(periods: Iterable[tuple[date, date]]) -> list[tuple[date, date]]:
    """Each run of days between joined periods, as (first missing day, last missing day)."""
    joined = joined_periods(periods)
    return [
        (joined[index][1] + _DAY, joined[index + 1][0] - _DAY) for index in range(len(joined) - 1)
    ]


@dataclass(frozen=True)
class Period:
    start: date
    end: date


class PeriodError(ValueError):
    def __init__(self, code: Literal["conflict", "incomplete", "month"], message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_selection(*, month_present: bool, start_present: bool, end_present: bool) -> None:
    if month_present and (start_present or end_present):
        raise PeriodError("conflict", "month cannot accompany endpoints")
    if start_present != end_present:
        raise PeriodError("incomplete", "both endpoints are required")


def select_period(
    *, today: date, month: str | None = None, start: date | None = None, end: date | None = None
) -> Period:
    validate_selection(
        month_present=month is not None,
        start_present=start is not None,
        end_present=end is not None,
    )
    if month is not None:
        try:
            return Period(*month_range(month))
        except ValueError as error:
            raise PeriodError("month", str(error)) from error
    if start is not None and end is not None:
        return Period(start, end)
    return Period(*month_bounds(today))


def first_day(month: str | None, *, today: date) -> date:
    return select_period(month=month, today=today).start
