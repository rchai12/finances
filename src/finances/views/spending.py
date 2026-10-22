"""The spending report as plain text."""

from dataclasses import dataclass

from finances.analysis.spending import SpendingReport
from finances.domain.money import format_cents
from finances.views.format import net_text


@dataclass(frozen=True)
class SpendingRow:
    label: str
    spent: str
    refunds: str
    net: str
    count: str


def spending_rows(report: SpendingReport) -> list[SpendingRow]:
    return [
        SpendingRow(
            line.label,
            format_cents(line.purchases_cents),
            format_cents(line.refunds_cents),
            net_text(line.spent_cents),
            str(line.count),
        )
        for line in report.lines
    ]


def spending_heading(report: SpendingReport) -> str:
    return f"Spending from {report.start.isoformat()} to {report.end.isoformat()}, by {report.by}."


def spending_summary(report: SpendingReport) -> list[str]:
    summary = report.summary
    lines = [
        f"Spent: {format_cents(summary.spent_cents + summary.refunds_cents)}. "
        f"Refunds: {format_cents(summary.refunds_cents)}. "
        f"Net: {net_text(summary.spent_cents)}. "
        f"Income: {format_cents(summary.income_cents)}.",
        f"Transfers left out: {summary.transfers}.",
    ]
    if summary.unsorted_in_count > 0:
        lines.append(
            f"Money in without a category: {format_cents(summary.unsorted_in_cents)} "
            f"(count: {summary.unsorted_in_count})."
        )
    return lines
