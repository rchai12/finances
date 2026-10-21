"""Recurring charges among everything spent up to a day."""

from datetime import date

from sqlalchemy.orm import Session

from finances.analysis.spending import load_flows
from finances.domain.recurring import Charge, Recurring, find_recurring, find_recurring_income
from finances.domain.spending import INCOME, SPENDING, UNSORTED_IN


def recurring_charges(session: Session, as_of: date) -> list[Recurring]:
    charges = [
        Charge(flow.merchant, flow.day, flow.amount_cents)
        for flow in load_flows(session, date.min, as_of)
        if flow.kind == SPENDING
    ]
    return find_recurring(charges, as_of)


def recurring_income(session: Session, as_of: date) -> list[Recurring]:
    credits = [
        Charge(flow.merchant, flow.day, flow.amount_cents)
        for flow in load_flows(session, date.min, as_of)
        if flow.kind in (INCOME, UNSORTED_IN)
    ]
    return find_recurring_income(credits, as_of)
