"""Bills and income expected in a window of days."""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from finances.analysis.recurring import recurring_charges, recurring_income
from finances.domain.upcoming import BILL, INCOME, Upcoming, expected


@dataclass(frozen=True)
class UpcomingReport:
    start: date
    end: date
    items: list[Upcoming]
    bills_cents: int
    income_cents: int


def upcoming_report(session: Session, start: date, days: int = 30) -> UpcomingReport:
    items = expected(
        recurring_charges(session, start), recurring_income(session, start), start, days
    )
    return UpcomingReport(
        start=start,
        end=start + timedelta(days=days - 1),
        items=items,
        bills_cents=sum(item.amount_cents for item in items if item.kind == BILL),
        income_cents=sum(item.amount_cents for item in items if item.kind == INCOME),
    )
