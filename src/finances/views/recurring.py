"""Recurring charges as plain text."""

from dataclasses import dataclass

from finances.domain.money import format_cents
from finances.domain.recurring import Recurring


@dataclass(frozen=True)
class RecurringRow:
    merchant: str
    every: str
    amount: str
    monthly: str
    count: str
    last: str
    next: str
    active: str


def recurring_rows(items: list[Recurring], *, include_inactive: bool = False) -> list[RecurringRow]:
    return [
        RecurringRow(
            merchant=item.merchant,
            every=item.cadence,
            amount=format_cents(item.amount_cents),
            monthly=format_cents(item.monthly_cents),
            count=str(item.count),
            last=item.last_day.isoformat(),
            next=item.next_day.isoformat(),
            active="yes" if item.active else "no",
        )
        for item in items
        if include_inactive or item.active
    ]


def recurring_summary(items: list[Recurring]) -> str:
    active = [item for item in items if item.active]
    monthly = sum(item.monthly_cents for item in active)
    return f"Recurring: {len(active)} active, {format_cents(monthly)} a month."


def recurring_income_summary(items: list[Recurring]) -> str:
    active = [item for item in items if item.active]
    monthly = sum(item.monthly_cents for item in active)
    return f"Recurring income: {len(active)} active, {format_cents(monthly)} a month."
