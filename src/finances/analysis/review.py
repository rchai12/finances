from dataclasses import dataclass

from sqlalchemy.orm import Session

from finances.db.repositories import (
    account_names,
    get_transaction,
    list_categories,
    list_category_assignments,
    list_proposals,
    proposal_out_of_date,
    waits_for,
)
from finances.domain.models import Transaction
from finances.domain.proposals import CATEGORY, OPEN, Proposal


@dataclass(frozen=True)
class ReviewItem:
    proposal: Proposal
    transaction: Transaction | None
    account: str | None
    current: str | None
    out_of_date: bool
    waits_for: int | None = None


def review_items(session: Session, *, status: str = OPEN, limit: int = 50) -> list[ReviewItem]:
    names = {category.id: category.name for category in list_categories(session)}
    assignments = list_category_assignments(session)
    accounts = account_names(session)
    items: list[ReviewItem] = []
    for proposal in list_proposals(session, status=status, limit=limit):
        transaction = get_transaction(session, proposal.target_id)
        assignment = assignments.get(proposal.target_id)
        items.append(
            ReviewItem(
                proposal=proposal,
                transaction=transaction,
                account=None if transaction is None else accounts[transaction.account_id],
                current=None if assignment is None else names[assignment.category_id],
                out_of_date=proposal_out_of_date(session, proposal),
                waits_for=waits_for(session, proposal),
            )
        )
    return items


def open_suggestions(session: Session) -> dict[int, str]:
    found: dict[int, str] = {}
    for proposal in list_proposals(session, status=OPEN, limit=10_000):
        if (
            proposal.kind == CATEGORY
            and not proposal_out_of_date(session, proposal)
            and waits_for(session, proposal) is None
        ):
            found[proposal.target_id] = proposal.value
    return found
