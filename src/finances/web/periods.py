"""Translate web form values while retaining field-error precedence."""

from datetime import date

from finances.domain import periods
from finances.web import app as web_app
from finances.web.helpers import _day


def spending_range(form: dict[str, str]) -> tuple[date, date]:
    try:
        periods.validate_selection(
            month_present=bool(form["month"]),
            start_present=bool(form["start"]),
            end_present=bool(form["end"]),
        )
    except periods.PeriodError as error:
        messages = {
            "conflict": "give a month, or from and to, not both",
            "incomplete": "give both from and to",
        }
        raise ValueError(messages[error.code]) from error
    start, end = _day(form["start"], "from"), _day(form["end"], "to")
    month = form["month"] or None
    result = periods.select_period(
        month=month,
        start=start,
        end=end,
        today=web_app._today() if month is None and start is None and end is None else date.min,
    )
    return result.start, result.end


def first_day(text: str) -> date:
    return periods.first_day(text or None, today=web_app._today() if not text else date.min)
