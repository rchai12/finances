"""How months compare: spent and income per month, and which accounts' data covers each."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from finances.analysis.spending import load_flows
from finances.db.repositories import account_data_span, list_accounts
from finances.domain.periods import months_ending, uncovered
from finances.domain.spending import summarize


@dataclass(frozen=True)
class MonthLine:
    start: date
    spent_cents: int
    income_cents: int
    uncovered: list[str]


def month_report(session: Session, day: date, count: int) -> list[MonthLine]:
    """One line per month of the `count` months ending in day's month, oldest first."""
    months = months_ending(day, count)
    spans = {
        account.name: account_data_span(session, account.id) for account in list_accounts(session)
    }
    lines = []
    for start, end in months:
        summary = summarize(load_flows(session, start, end, parts=True))
        lines.append(
            MonthLine(
                start, summary.spent_cents, summary.income_cents, uncovered(spans, start, end)
            )
        )
    return lines
