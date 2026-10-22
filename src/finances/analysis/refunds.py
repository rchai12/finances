"""Refund facts for one transaction: whether it is a refund, and the likely match."""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from finances.analysis.spending import flows_for
from finances.db.repositories import get_transaction, list_transactions_by_day
from finances.domain.merchants import clean_merchant
from finances.domain.models import Transaction
from finances.domain.refunds import REFUND_WINDOW_DAYS, Purchase, likely_purchase
from finances.domain.spending import SPENDING, is_refund


@dataclass(frozen=True)
class RefundFacts:
    is_refund: bool
    purchase: Transaction | None
    refunds: list[Transaction]


def refund_facts(session: Session, transaction_id: int) -> RefundFacts:
    """The refund match for this transaction, from posted spending of the same merchant."""
    item = get_transaction(session, transaction_id)
    empty = RefundFacts(False, None, [])
    if item is None:
        return empty
    day = item.transaction_date or item.posted_date
    start = day - timedelta(days=REFUND_WINDOW_DAYS)
    end = day + timedelta(days=REFUND_WINDOW_DAYS)
    loaded = [
        found
        for found in list_transactions_by_day(session, start, end)
        if found.account_id == item.account_id
    ]
    flows = flows_for(session, loaded)
    merchant = clean_merchant(item.description)
    pairs = [
        (found, flow)
        for found, flow in zip(loaded, flows, strict=True)
        if flow.kind == SPENDING and flow.merchant == merchant
    ]
    current = next(flow for found, flow in zip(loaded, flows, strict=True) if found.id == item.id)
    purchases = [
        Purchase(found.id, flow.day, flow.amount_cents)
        for found, flow in pairs
        if flow.amount_cents < 0
    ]
    if is_refund(current):
        found_id = likely_purchase(current.day, item.amount_cents, purchases)
        purchase = next((found for found, _ in pairs if found.id == found_id), None)
        return RefundFacts(True, purchase, [])
    if item.amount_cents >= 0:
        return empty
    matched = []
    last = day + timedelta(days=REFUND_WINDOW_DAYS)
    for found, flow in pairs:
        if not is_refund(flow) or not (day <= flow.day <= last):
            continue
        if likely_purchase(flow.day, found.amount_cents, purchases) == item.id:
            matched.append((flow.day, found.id, found))
    matched.sort()
    return RefundFacts(False, None, [found for _, _, found in matched])
