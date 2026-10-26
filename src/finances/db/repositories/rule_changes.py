from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from finances.db.orm import CategoryRow, CategoryRuleRow, ProposalRow, to_proposal
from finances.db.repositories.categories import (
    _leaf_category,
    _rule_line,
    delete_rule,
    edit_rule,
)
from finances.domain.audit import rule_text
from finances.domain.proposals import DECLINED, OPEN, RULE_DELETE, RULE_EDIT, Proposal
from finances.domain.rules import MATCHES, normalize_pattern
from finances.domain.text import PROPOSAL_TEXT_LIMIT, RULE_PATTERN_LIMIT, collapse_ws


def _now() -> datetime:
    return datetime.now(UTC)


def _rule_row(session: Session, rule_id: int) -> CategoryRuleRow:
    row = session.get(CategoryRuleRow, rule_id)
    if row is None:
        raise ValueError("rule not found")
    return row


def rule_change_is_out_of_date(session: Session, proposal: Proposal) -> bool:
    row = session.get(CategoryRuleRow, proposal.target_id)
    if row is None:
        return True
    return _rule_line(session, row) != proposal.before


def accept_rule_change(session: Session, row: ProposalRow) -> None:
    if row.kind == RULE_DELETE:
        delete_rule(session, row.target_id)
        return
    edit_rule(
        session,
        row.target_id,
        pattern=row.pattern,
        match=row.match,
        priority=row.priority,
        category=row.value,
    )


def propose_rule_change(
    session: Session,
    rule_id: int,
    reason: str,
    *,
    delete: bool = False,
    pattern: str | None = None,
    match: str | None = None,
    priority: int | None = None,
    category: str | None = None,
) -> Proposal:
    clean_reason = collapse_ws(reason)
    if not 1 <= len(clean_reason) <= PROPOSAL_TEXT_LIMIT:
        raise ValueError("a reason must be 1 to 200 characters")
    row = _rule_row(session, rule_id)
    given = (pattern is not None, match is not None, priority is not None, category is not None)
    if delete and any(given):
        raise ValueError("a deletion changes no fields")
    if not delete and not any(given):
        raise ValueError("name at least one field to change")
    stored_pattern = normalize_pattern(row.pattern if pattern is None else pattern)
    if not 1 <= len(stored_pattern) <= RULE_PATTERN_LIMIT:
        raise ValueError(f"a rule pattern must be 1 to {RULE_PATTERN_LIMIT} characters")
    stored_match = row.match if match is None else match
    if stored_match not in MATCHES:
        raise ValueError(f"match must be one of: {', '.join(MATCHES)}")
    if category is None:
        stored_name = session.get(CategoryRow, row.category_id).name
    else:
        stored_name = _leaf_category(session, category).name
    stored_priority = row.priority if priority is None else priority
    if not delete:
        would = rule_text(stored_match, stored_pattern, stored_name, stored_priority)
        if would == _rule_line(session, row):
            raise ValueError("the rule already is like this")
    taken = select(CategoryRuleRow).where(
        CategoryRuleRow.match == stored_match,
        CategoryRuleRow.pattern == stored_pattern,
        CategoryRuleRow.id != rule_id,
    )
    if session.scalars(taken).first() is not None:
        raise ValueError("a rule with this pattern and match already exists")
    kind = RULE_DELETE if delete else RULE_EDIT
    existing = session.scalars(
        select(ProposalRow).where(
            ProposalRow.kind.in_((RULE_EDIT, RULE_DELETE)),
            ProposalRow.target_id == rule_id,
        )
    ).all()
    if any(
        item.status == DECLINED
        and item.kind == kind
        and item.pattern == stored_pattern
        and item.match == stored_match
        and item.priority == stored_priority
        and item.value == stored_name
        for item in existing
    ):
        raise ValueError("a person declined this proposal already")
    if any(item.status == OPEN for item in existing):
        raise ValueError("this rule already has an open proposal")
    stored = ProposalRow(
        kind=kind,
        target_id=rule_id,
        value=stored_name,
        reason=clean_reason,
        status=OPEN,
        created_at=_now(),
        decided_at=None,
        other_id=None,
        pattern=stored_pattern,
        match=stored_match,
        priority=stored_priority,
        source=None,
        group_name=None,
        is_transfer=None,
        is_income=None,
        is_sensitive=None,
        is_tax=None,
        parent_id=None,
        before=_rule_line(session, row),
    )
    session.add(stored)
    session.flush()
    return to_proposal(stored)
