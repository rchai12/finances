"""Upcoming bills and income as plain text."""

from dataclasses import dataclass

from finances.analysis.upcoming import UpcomingReport
from finances.domain.money import format_cents


@dataclass(frozen=True)
class UpcomingRow:
    date: str
    what: str
    merchant: str
    every: str
    amount: str


def upcoming_rows(report: UpcomingReport) -> list[UpcomingRow]:
    return [
        UpcomingRow(
            date=item.day.isoformat(),
            what=item.kind,
            merchant=item.merchant,
            every=item.cadence,
            amount=format_cents(item.amount_cents),
        )
        for item in report.items
    ]


def upcoming_heading(report: UpcomingReport) -> str:
    return f"Expected from {report.start.isoformat()} to {report.end.isoformat()}."


def upcoming_summary(report: UpcomingReport) -> str:
    return (
        f"Bills: {format_cents(report.bills_cents)}. Income: {format_cents(report.income_cents)}."
    )
