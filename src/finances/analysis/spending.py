"""Where the money went: each transaction as a flow, and the spending report over a range."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from finances.analysis.people import load_attribution
from finances.db.repositories import (
    list_accounts,
    list_categories,
    list_category_assignments,
    list_transactions_between,
    list_transfer_pairs,
)
from finances.domain.merchants import clean_merchant
from finances.domain.spending import (
    NO_CARD,
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


@dataclass(frozen=True)
class SpendingReport:
    start: date
    end: date
    by: str
    lines: list[SpendingLine]
    summary: SpendingSummary


def load_flows(session: Session, start: date, end: date) -> list[Flow]:
    """One flow per posted transaction whose day is from start to end."""
    categories = {category.id: category for category in list_categories(session)}
    assignments = list_category_assignments(session)
    paired = {
        transaction_id
        for pair in list_transfer_pairs(session)
        for transaction_id in (pair.out_transaction_id, pair.in_transaction_id)
    }
    accounts = {account.id: account for account in list_accounts(session, include_inactive=True)}
    attribution = load_attribution(session)
    flows = []
    for item in list_transactions_between(session, start, end):
        assignment = assignments.get(item.id)
        category = None if assignment is None else categories[assignment.category_id]
        account = accounts[item.account_id]
        flows.append(
            Flow(
                amount_cents=item.amount_cents,
                day=item.transaction_date or item.posted_date,
                kind=flow_kind(item.amount_cents, paired=item.id in paired, category=category),
                category=UNCATEGORIZED if category is None else category.name,
                group=UNCATEGORIZED if category is None else categories[category.group_id].name,
                merchant=clean_merchant(item.description),
                person=attribution.person(item) or UNASSIGNED,
                account=account.name,
                bank=account.institution,
                card=item.card_last4 or NO_CARD,
            )
        )
    return flows


def spending_report(
    session: Session, start: date, end: date, by: str = "category"
) -> SpendingReport:
    check_by(by)
    if start > end:
        raise ValueError("the start date is after the end date")
    flows = load_flows(session, start, end)
    return SpendingReport(start, end, by, spending_lines(flows, by), summarize(flows))
