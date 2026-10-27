from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from finances.db.orm import CategoryRow, CategoryRuleRow, ProposalRow, to_proposal
from finances.db.repositories.categories import (
    CategoryExistsError,
    _category_row,
    _leaf_category,
    _rule_line,
    delete_category,
    rename_category,
)
from finances.domain.proposals import (
    CATEGORY,
    CATEGORY_DELETE,
    CATEGORY_RENAME,
    DECLINED,
    NEW_CATEGORY,
    OPEN,
    RULE,
    RULE_DELETE,
    RULE_EDIT,
    Proposal,
)
from finances.domain.text import PROPOSAL_TEXT_LIMIT, collapse_ws

_VALUE_KINDS = (CATEGORY, RULE, RULE_EDIT, RULE_DELETE)
_RULE_KINDS = (RULE_EDIT, RULE_DELETE)
_CHANGE_KINDS = (CATEGORY_RENAME, CATEGORY_DELETE)


def _now() -> datetime:
    return datetime.now(UTC)


def _dry_run(session: Session, name: str, *, rename_to: str | None, move_to: str) -> None:
    nested = session.begin_nested()
    try:
        if rename_to is not None:
            rename_category(session, name, rename_to)
        else:
            delete_category(session, name, move_to)
    finally:
        nested.rollback()


def _stored_move_to(session: Session, move_to: str | None) -> str:
    given = (move_to or "").strip()
    if not given:
        return ""
    return _leaf_category(session, given).name


def _rewrite_after_rename(
    session: Session, old_name: str, new_name: str, lines_before: dict[int, str]
) -> None:
    items = session.scalars(select(ProposalRow).where(ProposalRow.status == OPEN)).all()
    for item in items:
        if item.kind in _VALUE_KINDS and item.value == old_name:
            item.value = new_name
        if item.kind == NEW_CATEGORY and item.group_name == old_name:
            item.group_name = new_name
        if (
            item.kind in _RULE_KINDS
            and item.id in lines_before
            and item.before == lines_before[item.id]
        ):
            item.before = _rule_line(session, session.get(CategoryRuleRow, item.target_id))
    session.flush()


def _lines_before_rename(session: Session) -> dict[int, str]:
    found: dict[int, str] = {}
    items = session.scalars(
        select(ProposalRow).where(ProposalRow.status == OPEN, ProposalRow.kind.in_(_RULE_KINDS))
    ).all()
    for item in items:
        rule = session.get(CategoryRuleRow, item.target_id)
        if rule is None:
            continue
        found[item.id] = _rule_line(session, rule)
    return found


def category_change_is_out_of_date(session: Session, proposal: Proposal) -> bool:
    row = session.get(CategoryRow, proposal.target_id)
    if row is None:
        return True
    if row.name != proposal.before:
        return True
    try:
        if proposal.kind == CATEGORY_RENAME:
            _dry_run(session, row.name, rename_to=proposal.value, move_to="")
        else:
            _dry_run(session, row.name, rename_to=None, move_to=proposal.value)
    except (ValueError, CategoryExistsError):
        return True
    return False


def accept_category_change(session: Session, row: ProposalRow) -> None:
    if row.kind == CATEGORY_RENAME:
        lines_before = _lines_before_rename(session)
        old, renamed = rename_category(session, row.before or "", row.value)
        _rewrite_after_rename(session, old, renamed.name, lines_before)
        return
    delete_category(session, row.before or "", row.value)


def propose_category_change(
    session: Session,
    name: str,
    reason: str,
    *,
    rename_to: str | None = None,
    delete: bool = False,
    move_to: str | None = None,
) -> Proposal:
    clean_reason = collapse_ws(reason)
    if not 1 <= len(clean_reason) <= PROPOSAL_TEXT_LIMIT:
        raise ValueError("a reason must be 1 to 200 characters")
    row = _category_row(session, name)
    if row is None:
        raise ValueError("category not found")
    if rename_to is not None and delete:
        raise ValueError("rename or delete, not both")
    if rename_to is None and not delete:
        raise ValueError("name a new name or delete=true")
    if rename_to is not None and rename_to.strip() == row.name:
        raise ValueError("the name already is like this")
    if rename_to is not None:
        _dry_run(session, name, rename_to=rename_to, move_to="")
        kind = CATEGORY_RENAME
        stored = rename_to.strip()
    else:
        _dry_run(session, name, rename_to=None, move_to=move_to or "")
        kind = CATEGORY_DELETE
        stored = _stored_move_to(session, move_to)
    existing = session.scalars(
        select(ProposalRow).where(
            ProposalRow.kind.in_(_CHANGE_KINDS), ProposalRow.target_id == row.id
        )
    ).all()
    if any(
        item.status == DECLINED and item.kind == kind and item.value == stored for item in existing
    ):
        raise ValueError("a person declined this proposal already")
    if any(item.status == OPEN for item in existing):
        raise ValueError("this category already has an open proposal")
    stored_row = ProposalRow(
        kind=kind,
        target_id=row.id,
        value=stored,
        reason=clean_reason,
        status=OPEN,
        created_at=_now(),
        decided_at=None,
        other_id=None,
        pattern=None,
        match=None,
        priority=None,
        source=None,
        group_name=None,
        is_transfer=None,
        is_income=None,
        is_sensitive=None,
        is_tax=None,
        parent_id=None,
        before=row.name,
    )
    session.add(stored_row)
    session.flush()
    return to_proposal(stored_row)
