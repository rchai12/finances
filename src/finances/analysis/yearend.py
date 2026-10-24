"""A calendar year's spending, and the tax-relevant categories pulled out."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from finances.analysis.spending import load_flows
from finances.db.repositories import list_categories
from finances.domain.spending import SpendingLine, SpendingSummary, spending_lines, summarize


@dataclass(frozen=True)
class YearReport:
    year: int
    start: date
    end: date
    summary: SpendingSummary
    groups: list[SpendingLine]
    categories: list[SpendingLine]
    tax: list[SpendingLine]


def year_report(session: Session, year: int) -> YearReport:
    """Spending, groups, categories, and tax-relevant lines for a calendar year."""
    if year < 1 or year > 9999:
        raise ValueError("year must be from 1 to 9999")
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    flows = load_flows(session, start, end, parts=True)
    groups = spending_lines(flows, "group")
    categories = spending_lines(flows, "category")
    by_name = {line.label: line for line in categories}
    tax = [
        by_name.get(item.name, SpendingLine(item.name, 0, 0, 0))
        for item in list_categories(session)
        if item.is_tax
    ]
    return YearReport(year, start, end, summarize(flows), groups, categories, tax)
