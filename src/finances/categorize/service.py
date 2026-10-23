"""Run the rules over every transaction, leaving categories set by hand alone."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from finances.db.repositories import (
    accept_proposal,
    alias_map,
    assign_by_rule,
    check_rule,
    get_transaction,
    list_accounts,
    list_categories,
    list_category_assignments,
    list_rules,
    list_transaction_descriptions,
    remove_category,
)
from finances.domain.merchants import merchant_name, merchant_names
from finances.domain.models import BY_RULE, MANUAL, CategoryAssignment, CategoryRule, Transaction
from finances.domain.proposals import RULE, Proposal
from finances.domain.rules import pick_rule_for


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
    aliases = alias_map(session)
    held = list_category_assignments(session)
    total = changed = uncategorized = 0
    for transaction_id, description in list_transaction_descriptions(session):
        total += 1
        before = held.get(transaction_id)
        if before is not None and before.source == MANUAL:
            continue
        rule = pick_rule_for(merchant_names(description, aliases), rules)
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


PREVIEW_EXAMPLES = 10


@dataclass(frozen=True)
class RuleChange:
    transaction: Transaction
    account: str
    merchant: str
    now: str | None


@dataclass(frozen=True)
class RulePreview:
    category: str
    changes: int
    examples: list[RuleChange]


def preview_rule(
    session: Session, pattern: str, category: str, *, match: str = "contains", priority: int = 0
) -> RulePreview:
    """Count the transactions this rule would put in its category, without adding it."""
    clean, target = check_rule(session, pattern, category, match)
    rules = list_rules(session)
    imagined = CategoryRule(
        id=max((rule.id for rule in rules), default=0) + 1,
        pattern=clean,
        match=match,
        priority=priority,
        category_id=target.id,
    )
    combined = [*rules, imagined]
    aliases = alias_map(session)
    held = list_category_assignments(session)
    names = {item.id: item.name for item in list_categories(session)}
    accounts = {item.id: item.name for item in list_accounts(session, include_inactive=True)}
    counted: list[RuleChange] = []
    for transaction_id, description in list_transaction_descriptions(session):
        before = held.get(transaction_id)
        if before is not None and before.source == MANUAL:
            continue
        picked = pick_rule_for(merchant_names(description, aliases), combined)
        if picked is not imagined:
            continue
        current = _category(before)
        if current == imagined.category_id:
            continue
        item = get_transaction(session, transaction_id)
        assert item is not None
        counted.append(
            RuleChange(
                item,
                accounts[item.account_id],
                merchant_name(description, aliases),
                None if current is None else names[current],
            )
        )
    counted.sort(key=lambda row: (row.transaction.posted_date, row.transaction.id), reverse=True)
    return RulePreview(target.name, len(counted), counted[:PREVIEW_EXAMPLES])


@dataclass(frozen=True)
class Accepted:
    proposals: list[Proposal]
    categorized: CategorizeResult | None


def accept_proposals(session: Session, proposal_ids: list[int]) -> Accepted:
    found = [accept_proposal(session, proposal_id) for proposal_id in proposal_ids]
    if any(item.kind == RULE for item in found):
        return Accepted(found, categorize(session))
    return Accepted(found, None)
