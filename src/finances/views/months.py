"""The month report as plain text."""

from dataclasses import dataclass
from datetime import date

from finances.analysis.months import MonthLine
from finances.domain.money import format_cents
from finances.views.format import change_text, net_text


@dataclass(frozen=True)
class MonthRow:
    month: str
    spent: str
    income: str
    change: str
    covered: str


def _month(start: date) -> str:
    return start.isoformat()[:7]


def month_rows(lines: list[MonthLine]) -> list[MonthRow]:
    """One row per month; the change is this month's spent minus the month before's."""
    rows = []
    previous: int | None = None
    for line in lines:
        rows.append(
            MonthRow(
                month=_month(line.start),
                spent=net_text(line.spent_cents),
                income=format_cents(line.income_cents),
                change="" if previous is None else change_text(line.spent_cents - previous),
                covered="partly" if line.uncovered else "yes",
            )
        )
        previous = line.spent_cents
    return rows


def month_heading(lines: list[MonthLine]) -> str:
    return f"Months from {_month(lines[0].start)} to {_month(lines[-1].start)}."


def month_notes(lines: list[MonthLine]) -> list[str]:
    return [
        f"{_month(line.start)}: no data for the whole month from {', '.join(line.uncovered)}."
        for line in lines
        if line.uncovered
    ]
