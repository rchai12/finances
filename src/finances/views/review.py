from dataclasses import dataclass

from finances.analysis.review import ReviewItem
from finances.domain.money import format_cents
from finances.domain.proposals import Proposal


@dataclass(frozen=True)
class ReviewRow:
    id: str
    date: str
    account: str
    description: str
    amount: str
    now: str
    proposed: str
    reason: str
    state: str


def review_rows(items: list[ReviewItem]) -> list[ReviewRow]:
    rows: list[ReviewRow] = []
    for item in items:
        transaction = item.transaction
        rows.append(
            ReviewRow(
                id=str(item.proposal.id),
                date="" if transaction is None else transaction.posted_date.isoformat(),
                account="" if item.account is None else item.account,
                description="" if transaction is None else transaction.description,
                amount="" if transaction is None else format_cents(transaction.amount_cents),
                now="" if item.current is None else item.current,
                proposed=item.proposal.value,
                reason=item.proposal.reason,
                state="out of date" if item.out_of_date else item.proposal.status,
            )
        )
    return rows


def accepted_text(proposal: Proposal) -> str:
    return (
        f"Accepted proposal {proposal.id}: {proposal.value} for transaction {proposal.target_id}."
    )


def declined_text(proposal: Proposal) -> str:
    return f"Declined proposal {proposal.id}."
