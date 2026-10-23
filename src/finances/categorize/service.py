"""Run the rules over every transaction, leaving categories set by hand alone."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from finances.db.repositories import (
    accept_proposal,
    assign_by_rule,
    list_category_assignments,
    list_rules,
    list_transaction_descriptions,
    remove_category,
)
from finances.domain.merchants import clean_merchant
from finances.domain.models import BY_RULE, MANUAL, CategoryAssignment
from finances.domain.proposals import RULE, Proposal
from finances.domain.rules import pick_rule


@dataclass(frozen=True)
class CategorizeResult:
    total: int
    changed: int
    uncategorized: int


def categorize(session: Session) -> CategorizeResult:
    """Give each transaction not set by hand its best rule's category, or none. The caller commits.

    A transaction counts as changed when its category, or lack of one, differs afterwards.
    """
    rules = list_rules(session)
    held = list_category_assignments(session)
    total = changed = uncategorized = 0
    for transaction_id, description in list_transaction_descriptions(session):
        total += 1
        before = held.get(transaction_id)
        if before is not None and before.source == MANUAL:
            continue
        rule = pick_rule(clean_merchant(description), rules)
        after = (
            None
            if rule is None
            else CategoryAssignment(transaction_id, rule.category_id, BY_RULE, rule.id)
        )
        if after != before:
            if rule is None:
                remove_category(session, transaction_id)
            else:
                assign_by_rule(session, transaction_id, rule)
        if _category(before) != _category(after):
            changed += 1
        if after is None:
            uncategorized += 1
    return CategorizeResult(total, changed, uncategorized)


def _category(assignment: CategoryAssignment | None) -> int | None:
    return None if assignment is None else assignment.category_id


@dataclass(frozen=True)
class Accepted:
    proposals: list[Proposal]
    categorized: CategorizeResult | None


def accept_proposals(session: Session, proposal_ids: list[int]) -> Accepted:
    found = [accept_proposal(session, proposal_id) for proposal_id in proposal_ids]
    if any(item.kind == RULE for item in found):
        return Accepted(found, categorize(session))
    return Accepted(found, None)
