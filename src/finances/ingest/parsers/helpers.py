"""Small parsing helpers shared by every statement parser."""

import re
from datetime import date, timedelta

from finances.domain.money import parse_money
from finances.ingest.statement import StatementError

EARLY_DAYS = 60
LATE_DAYS = 7
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


def collapse_ws(text: str) -> str:
    """Return text with outer whitespace removed and inner runs of whitespace made one space."""
    return " ".join(text.split())


def parse_amount(text: str) -> int:
    """Return integer cents for an amount as statements print it, such as "- $12.00"."""
    text = text.strip()
    if text.startswith("="):
        text = text[1:].lstrip()
    if text.startswith("+"):
        text = text[1:].lstrip()
        if text.startswith(("-", "(")) or text.endswith("-"):
            raise ValueError("invalid money text")
    if text.startswith("-"):
        text = "-" + text[1:].lstrip()
    return parse_money(text)


def infer_year(month: int, day: int, period_start: date, period_end: date) -> date:
    """Return the date with this month and day that belongs to the statement period."""
    early = period_start - timedelta(days=EARLY_DAYS)
    late = period_end + timedelta(days=LATE_DAYS)
    found: list[date] = []
    for year in (period_end.year - 1, period_end.year, period_end.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if early <= candidate <= late:
            found.append(candidate)
    if not found:
        raise StatementError("date is outside the statement period")
    if len(found) > 1:
        raise StatementError("date matches more than one year")
    return found[0]


def parse_month_day(text: str, period_start: date, period_end: date) -> date:
    """Return the date for text such as "Jan 5", "01/05" or "01-05"."""
    text = collapse_ws(text)
    named = re.fullmatch(r"([A-Za-z]{3}) ([0-9]{1,2})", text)
    numeric = re.fullmatch(r"([0-9]{1,2})[/-]([0-9]{1,2})", text)
    if named is not None:
        try:
            month = MONTHS.index(named.group(1).lower()) + 1
        except ValueError:
            raise StatementError("unrecognized date text") from None
        day = int(named.group(2))
    elif numeric is not None:
        month = int(numeric.group(1))
        day = int(numeric.group(2))
    else:
        raise StatementError("unrecognized date text")
    return infer_year(month, day, period_start, period_end)
