"""CSV text for the transactions, year, and spending exports."""

import csv
import io

from finances.analysis.export import ExportLine
from finances.analysis.spending import SpendingReport
from finances.analysis.yearend import YearReport
from finances.domain.money import decimal_text
from finances.domain.spending import UNASSIGNED, UNCATEGORIZED, SpendingLine
from finances.views.format import mask_last4


def transactions_csv(lines: list[ExportLine]) -> str:
    rows = [
        [
            "ID",
            "Posted",
            "Date",
            "Account",
            "Description",
            "Merchant",
            "Category",
            "Group",
            "Kind",
            "Amount",
            "Card",
            "Person",
            "Part",
            "Tags",
            "Note",
        ]
    ]
    for line in lines:
        item = line.found.transaction
        flow = line.found.flow
        rows.append(
            [
                str(item.id),
                item.posted_date.isoformat(),
                flow.day.isoformat(),
                line.account,
                item.description,
                flow.merchant,
                "" if flow.category == UNCATEGORIZED else flow.category,
                "" if flow.group == UNCATEGORIZED else flow.group,
                flow.kind,
                decimal_text(flow.amount_cents),
                mask_last4(item.card_last4),
                "" if flow.person == UNASSIGNED else flow.person,
                "" if line.found.part is None else str(line.found.part),
                "; ".join(line.tags),
                line.note or "",
            ]
        )
    return _csv(rows)


def year_csv(report: YearReport) -> str:
    rows = [["Section", "Label", "Spent", "Refunds", "Net", "Count"]]
    for section, lines in (
        ("group", report.groups),
        ("category", report.categories),
        ("tax", report.tax),
    ):
        for line in lines:
            rows.append([section, line.label, *_amounts(line)])
    return _csv(rows)


def spending_csv(report: SpendingReport) -> str:
    rows = [[report.by.capitalize(), "Spent", "Refunds", "Net", "Count"]]
    for line in report.lines:
        rows.append([line.label, *_amounts(line)])
    return _csv(rows)


def _amounts(line: SpendingLine) -> list[str]:
    return [
        decimal_text(line.purchases_cents),
        decimal_text(line.refunds_cents),
        decimal_text(line.spent_cents),
        str(line.count),
    ]


def _csv(rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerows(rows)
    return buffer.getvalue()
