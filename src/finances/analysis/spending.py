"""Where the money went: each transaction as a flow, and the spending report over a range."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from finances.analysis.people import load_attribution
from finances.db.repositories import (
    alias_map,
    list_accounts,
    list_categories,
    list_category_assignments,
    list_transactions_between,
    list_transfer_pairs,
    splits_for,
)
from finances.domain.merchants import merchant_name
from finances.domain.models import Transaction
from finances.domain.spending import (
    NO_CARD,
    PENDING,
    UNASSIGNED,
    UNCATEGORIZED,
    Flow,
    SpendingLine,
    SpendingSummary,
    check_by,
    flow_kind,
    spending_lines,
    summarize,
)
from finances.domain.splits import SPLIT


@dataclass(frozen=True)
class SpendingReport:
    start: date
    end: date
    by: str
    lines: list[SpendingLine]
    summary: SpendingSummary


def flows_for(session: Session, transactions: Iterable[Transaction]) -> list[Flow]:
    """One flow per transaction, in the order given; a pending one is of the kind PENDING."""
    categories = {category.id: category for category in list_categories(session)}
    assignments = list_category_assignments(session)
    paired = {
        transaction_id
        for pair in list_transfer_pairs(session)
        for transaction_id in (pair.out_transaction_id, pair.in_transaction_id)
    }
    accounts = {account.id: account for account in list_accounts(session, include_inactive=True)}
    attribution = load_attribution(session)
    aliases = alias_map(session)
    items = list(transactions)
    split = splits_for(session, [item.id for item in items])
    flows = []
    for item in items:
        assignment = assignments.get(item.id)
        category = None if assignment is None else categories[assignment.category_id]
        account = accounts[item.account_id]
        labeled = SPLIT if item.id in split else None
        kind_category = None if labeled is not None else category
        flows.append(
            Flow(
                amount_cents=item.amount_cents,
                day=item.transaction_date or item.posted_date,
                kind=PENDING
                if item.is_pending
                else flow_kind(item.amount_cents, paired=item.id in paired, category=kind_category),
                category=labeled
                if labeled is not None
                else (UNCATEGORIZED if category is None else category.name),
                group=labeled
                if labeled is not None
                else (UNCATEGORIZED if category is None else categories[category.group_id].name),
                merchant=merchant_name(item.description, aliases),
                person=attribution.person(item) or UNASSIGNED,
                account=account.name,
                bank=account.institution,
                card=item.card_last4 or NO_CARD,
            )
        )
    return flows


def load_flows(session: Session, start: date, end: date) -> list[Flow]:
    """One flow per posted transaction whose day is from start to end."""
    return flows_for(session, list_transactions_between(session, start, end))


def spending_report(
    session: Session, start: date, end: date, by: str = "category"
) -> SpendingReport:
    check_by(by)
    if start > end:
        raise ValueError("the start date is after the end date")
    flows = load_flows(session, start, end)
    return SpendingReport(start, end, by, spending_lines(flows, by), summarize(flows))
