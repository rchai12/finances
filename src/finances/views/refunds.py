"""Refund text for the transaction page."""

from dataclasses import dataclass

from finances.analysis.refunds import RefundFacts
from finances.domain.models import Transaction
from finances.domain.money import format_cents


@dataclass(frozen=True)
class RefundLine:
    id: int
    date: str
    amount: str


@dataclass(frozen=True)
class RefundView:
    amount: str
    purchase: RefundLine | None


def _line(item: Transaction) -> RefundLine:
    day = item.transaction_date or item.posted_date
    return RefundLine(item.id, day.isoformat(), format_cents(item.amount_cents))


def refund_view(facts: RefundFacts, amount: str) -> RefundView | None:
    if not facts.is_refund:
        return None
    purchase = None if facts.purchase is None else _line(facts.purchase)
    return RefundView(amount, purchase)


def refunded_lines(facts: RefundFacts) -> list[RefundLine]:
    return [_line(item) for item in facts.refunds]
