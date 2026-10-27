from dataclasses import dataclass

from finances.analysis.review import ReviewItem
from finances.domain.audit import rule_text
from finances.domain.money import format_cents
from finances.domain.proposals import (
    ALIAS,
    CATEGORY_DELETE,
    CATEGORY_RENAME,
    GROUP,
    NEW_CATEGORY,
    NOT_TRANSFER,
    RULE,
    RULE_DELETE,
    RULE_EDIT,
    TRANSFER,
    Advice,
    Proposal,
    group_flag_words,
)


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
                proposed=proposed_text(item.proposal),
                reason=item.proposal.reason,
                state=(
                    "out of date"
                    if item.out_of_date
                    else (
                        f"waits for #{item.waits_for}"
                        if item.waits_for is not None
                        else item.proposal.status
                    )
                ),
            )
        )
    return rows


def _rule_line(proposal: Proposal) -> str:
    return rule_text(
        proposal.match or "",
        proposal.pattern or "",
        proposal.value,
        0 if proposal.priority is None else proposal.priority,
    )


def proposed_text(proposal: Proposal) -> str:
    if proposal.kind == TRANSFER:
        return f"a transfer with transaction {proposal.other_id}"
    if proposal.kind == NOT_TRANSFER:
        return f"not a transfer with transaction {proposal.other_id}"
    if proposal.kind == RULE:
        return f"a rule: {_rule_line(proposal)}"
    if proposal.kind == ALIAS:
        return f"merge {proposal.source} into {proposal.value}"
    if proposal.kind == GROUP:
        extra = group_flag_words(
            transfer=proposal.transfer, income=proposal.income, sensitive=proposal.sensitive
        )
        return f"a new group: {proposal.value}" + (f" ({extra})" if extra else "")
    if proposal.kind == NEW_CATEGORY:
        tax = ", tax-relevant" if proposal.tax else ""
        return f"a new category: {proposal.value} in {proposal.group}{tax}"
    if proposal.kind == RULE_EDIT:
        return f"rule {proposal.target_id}: {_rule_line(proposal)}"
    if proposal.kind == RULE_DELETE:
        return f"delete rule {proposal.target_id}"
    if proposal.kind == CATEGORY_RENAME:
        return f"rename to {proposal.value}"
    if proposal.kind == CATEGORY_DELETE:
        if proposal.value:
            return f"delete, moving its uses to {proposal.value}"
        return "delete"
    return proposal.value


def accepted_text(proposal: Proposal) -> str:
    if proposal.kind == TRANSFER:
        return (
            f"Accepted proposal {proposal.id}: transactions {proposal.target_id} and "
            f"{proposal.other_id} are a transfer."
        )
    if proposal.kind == NOT_TRANSFER:
        return (
            f"Accepted proposal {proposal.id}: transactions {proposal.target_id} and "
            f"{proposal.other_id} are not a transfer."
        )
    if proposal.kind == RULE:
        return f"Accepted proposal {proposal.id}: a rule, {_rule_line(proposal)}."
    if proposal.kind == ALIAS:
        return f"Accepted proposal {proposal.id}: {proposal.source} merged into {proposal.value}."
    if proposal.kind == GROUP:
        return f"Accepted proposal {proposal.id}: the group {proposal.value}."
    if proposal.kind == NEW_CATEGORY:
        return (
            f"Accepted proposal {proposal.id}: the category {proposal.value} in {proposal.group}."
        )
    if proposal.kind == RULE_EDIT:
        return (
            f"Accepted proposal {proposal.id}: rule {proposal.target_id} is now "
            f"{_rule_line(proposal)}."
        )
    if proposal.kind == RULE_DELETE:
        return f"Accepted proposal {proposal.id}: rule {proposal.target_id} deleted."
    if proposal.kind == CATEGORY_RENAME:
        return f"Accepted proposal {proposal.id}: {proposal.before} is now {proposal.value}."
    if proposal.kind == CATEGORY_DELETE:
        if proposal.value:
            return (
                f"Accepted proposal {proposal.id}: {proposal.before} deleted, "
                f"its uses moved to {proposal.value}."
            )
        return f"Accepted proposal {proposal.id}: {proposal.before} deleted."
    return (
        f"Accepted proposal {proposal.id}: {proposal.value} for transaction {proposal.target_id}."
    )


def declined_text(proposal: Proposal, *, waited: bool = False) -> str:
    if waited:
        return f"Declined proposal {proposal.id}, which waited for {proposal.parent_id}."
    return f"Declined proposal {proposal.id}."


@dataclass(frozen=True)
class AdviceRow:
    id: str
    when: str
    subject: str
    text: str
    state: str


def advice_rows(notes: list[Advice]) -> list[AdviceRow]:
    return [
        AdviceRow(
            id=str(item.id),
            when=item.created_at.strftime("%Y-%m-%d %H:%M"),
            subject=item.subject,
            text=item.text,
            state="" if item.dismissed_at is None else "dismissed",
        )
        for item in notes
    ]
