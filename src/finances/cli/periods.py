"""Translate CLI period arguments into shared calendar selections."""

from datetime import date, datetime

from finances import clock
from finances.cli.common import fail
from finances.domain import periods


def spending_range(
    month: str | None, start: datetime | None, end: datetime | None
) -> tuple[date, date]:
    try:
        result = periods.select_period(
            month=month,
            start=None if start is None else start.date(),
            end=None if end is None else end.date(),
            today=clock.today() if month is None and start is None and end is None else date.min,
        )
    except periods.PeriodError as error:
        messages = {
            "conflict": "give --month, or --from and --to, not both",
            "incomplete": "give both --from and --to",
        }
        fail(messages.get(error.code, str(error)))
    return result.start, result.end


def first_day(month: str | None) -> date:
    try:
        return periods.first_day(month, today=clock.today() if month is None else date.min)
    except periods.PeriodError as error:
        fail(str(error))
