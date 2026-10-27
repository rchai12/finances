from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finances.db.orm import AdviceRow, ProposalRow, to_advice, to_proposal
from finances.db.repositories.aliases import add_alias, alias_map
from finances.db.repositories.assignments import (
    _assigned_name,
    _assignment_row,
    set_category_by_hand,
)
from finances.db.repositories.audit import record_change
from finances.db.repositories.categories import _category_row, _rule_exists, create_rule
from finances.db.repositories.category_changes import (
    accept_category_change,
    category_change_is_out_of_date,
)
from finances.db.repositories.chains import (
    _split_or_paired,
    category_is_out_of_date,
    chain_out_of_date,
    pair_is_out_of_date,
    proposed_category,
    waits_for,
)
from finances.db.repositories.rule_changes import accept_rule_change, rule_change_is_out_of_date
from finances.db.repositories.transactions import get_transaction
from finances.db.repositories.transfers import (
    _check_transfer,
    create_transfer_pair,
    find_transfer_pair,
    list_transfer_rejections,
    reject_transfer,
)
from finances.domain.merchants import check_alias, clean_merchant, merchant_names
from finances.domain.models import CONFIRMED, MANUAL, CategoryRule
from finances.domain.proposals import (
    ACCEPTED,
    ALIAS,
    CATEGORY,
    CATEGORY_DELETE,
    CATEGORY_RENAME,
    DECLINED,
    GROUP,
    NEW_CATEGORY,
    NOT_TRANSFER,
    OPEN,
    RULE,
    RULE_DELETE,
    RULE_EDIT,
    STATUSES,
    TRANSFER,
    Advice,
    Proposal,
    proposal_text,
)
from finances.domain.rules import MATCHES, normalize_pattern, rule_matches
from finances.domain.text import (
    ADVICE_TEXT_LIMIT,
    NAME_LIMIT,
    PROPOSAL_TEXT_LIMIT,
    RULE_PATTERN_LIMIT,
    collapse_ws,
)


def _now() -> datetime:
    return datetime.now(UTC)


def decided_by_a_person(session: Session, transaction_id: int) -> bool:
    row = _assignment_row(session, transaction_id)
    return (row is not None and row.source == MANUAL) or _split_or_paired(session, transaction_id)


def propose_category(session: Session, transaction_id: int, category: str, reason: str) -> Proposal:
    clean = collapse_ws(reason)
    if not 1 <= len(clean) <= PROPOSAL_TEXT_LIMIT:
        raise ValueError("a reason must be 1 to 200 characters")
    if get_transaction(session, transaction_id) is None:
        raise ValueError("transaction not found")
    stored, parent_id = proposed_category(session, category)
    if _split_or_paired(session, transaction_id):
        raise ValueError("a person has already decided this transaction")
    current = _assigned_name(session, transaction_id)
    if current == stored:
        raise ValueError("the transaction already has this category")
    existing = session.scalars(
        select(ProposalRow).where(
            ProposalRow.kind == CATEGORY, ProposalRow.target_id == transaction_id
        )
    ).all()
    if any(row.status == DECLINED and row.value == stored for row in existing):
        raise ValueError("a person declined this proposal already")
    if any(row.status == OPEN for row in existing):
        raise ValueError("this transaction already has an open proposal")
    row = ProposalRow(
        kind=CATEGORY,
        target_id=transaction_id,
        value=stored,
        reason=clean,
        status=OPEN,
        created_at=_now(),
        decided_at=None,
        parent_id=parent_id,
        before=current,
    )
    session.add(row)
    session.flush()
    return to_proposal(row)


def _propose_pair(session: Session, kind: str, out_id: int, in_id: int, reason: str) -> Proposal:
    clean = collapse_ws(reason)
    if not 1 <= len(clean) <= PROPOSAL_TEXT_LIMIT:
        raise ValueError("a reason must be 1 to 200 characters")
    _check_transfer(session, out_id, in_id)
    if (
        find_transfer_pair(session, out_id) is not None
        or find_transfer_pair(session, in_id) is not None
    ):
        raise ValueError("a person or the rules already paired one of these transactions")
    if (out_id, in_id) in list_transfer_rejections(session):
        raise ValueError("a person said these two are not a transfer")
    existing = session.scalars(
        select(ProposalRow).where(
            ProposalRow.target_id == out_id,
            ProposalRow.other_id == in_id,
            ProposalRow.kind.in_((TRANSFER, NOT_TRANSFER)),
        )
    ).all()
    if any(row.status == DECLINED and row.kind == kind for row in existing):
        raise ValueError("a person declined this proposal already")
    if any(row.status == OPEN for row in existing):
        raise ValueError("these two already have an open proposal")
    row = ProposalRow(
        kind=kind,
        target_id=out_id,
        value="",
        reason=clean,
        status=OPEN,
        created_at=_now(),
        decided_at=None,
        other_id=in_id,
    )
    session.add(row)
    session.flush()
    return to_proposal(row)


def propose_transfer(session: Session, out_id: int, in_id: int, reason: str) -> Proposal:
    return _propose_pair(session, TRANSFER, out_id, in_id, reason)


def propose_not_transfer(session: Session, out_id: int, in_id: int, reason: str) -> Proposal:
    return _propose_pair(session, NOT_TRANSFER, out_id, in_id, reason)


def propose_rule(
    session: Session,
    example_id: int,
    pattern: str,
    category: str,
    reason: str,
    *,
    match: str = "contains",
    priority: int = 0,
) -> Proposal:
    clean = collapse_ws(reason)
    if not 1 <= len(clean) <= PROPOSAL_TEXT_LIMIT:
        raise ValueError("a reason must be 1 to 200 characters")
    stored = normalize_pattern(pattern)
    if not 1 <= len(stored) <= RULE_PATTERN_LIMIT:
        raise ValueError(f"a rule pattern must be 1 to {RULE_PATTERN_LIMIT} characters")
    if match not in MATCHES:
        raise ValueError(f"match must be one of: {', '.join(MATCHES)}")
    example = get_transaction(session, example_id)
    if example is None:
        raise ValueError("transaction not found")
    stored_name, parent_id = proposed_category(session, category)
    probe = CategoryRule(0, stored, match, priority, 0)
    names = merchant_names(example.description, alias_map(session))
    if not any(rule_matches(probe, name) for name in names):
        raise ValueError("the rule does not match the example transaction")
    if _rule_exists(session, match, stored):
        raise ValueError("a rule with this pattern and match already exists")
    existing = session.scalars(
        select(ProposalRow).where(
            ProposalRow.kind == RULE,
            ProposalRow.match == match,
            ProposalRow.pattern == stored,
        )
    ).all()
    if any(row.status == DECLINED and row.value == stored_name for row in existing):
        raise ValueError("a person declined this proposal already")
    if any(row.status == OPEN for row in existing):
        raise ValueError("this rule already has an open proposal")
    row = ProposalRow(
        kind=RULE,
        target_id=example_id,
        value=stored_name,
        reason=clean,
        status=OPEN,
        created_at=_now(),
        decided_at=None,
        other_id=None,
        pattern=stored,
        match=match,
        priority=priority,
        parent_id=parent_id,
    )
    session.add(row)
    session.flush()
    return to_proposal(row)


def propose_merchant_alias(session: Session, example_id: int, target: str, reason: str) -> Proposal:
    clean = collapse_ws(reason)
    if not 1 <= len(clean) <= PROPOSAL_TEXT_LIMIT:
        raise ValueError("a reason must be 1 to 200 characters")
    example = get_transaction(session, example_id)
    if example is None:
        raise ValueError("transaction not found")
    source, stored = check_alias(clean_merchant(example.description), target, alias_map(session))
    existing = session.scalars(
        select(ProposalRow).where(ProposalRow.kind == ALIAS, ProposalRow.source == source)
    ).all()
    if any(row.status == DECLINED and row.value == stored for row in existing):
        raise ValueError("a person declined this proposal already")
    if any(row.status == OPEN for row in existing):
        raise ValueError("this merchant already has an open proposal")
    row = ProposalRow(
        kind=ALIAS,
        target_id=example_id,
        value=stored,
        reason=clean,
        status=OPEN,
        created_at=_now(),
        decided_at=None,
        other_id=None,
        pattern=None,
        match=None,
        priority=None,
        source=source,
    )
    session.add(row)
    session.flush()
    return to_proposal(row)


def count_open_proposals(session: Session) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(ProposalRow).where(ProposalRow.status == OPEN)
        )
        or 0
    )


def list_proposals(
    session: Session, *, status: str | None = None, limit: int = 50
) -> list[Proposal]:
    if status is not None and status not in STATUSES:
        raise ValueError("status must be one of: open, accepted, declined")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    stmt = select(ProposalRow)
    if status is not None:
        stmt = stmt.where(ProposalRow.status == status)
    stmt = stmt.order_by(ProposalRow.created_at.desc(), ProposalRow.id.desc()).limit(limit)
    return [to_proposal(row) for row in session.scalars(stmt).all()]


def proposal_out_of_date(session: Session, proposal: Proposal) -> bool:
    if proposal.kind in (GROUP, NEW_CATEGORY):
        from finances.db.repositories.new_categories import new_is_out_of_date

        return new_is_out_of_date(session, proposal)
    if proposal.kind in (CATEGORY_RENAME, CATEGORY_DELETE):
        return category_change_is_out_of_date(session, proposal)
    if proposal.kind in (RULE_EDIT, RULE_DELETE):
        return rule_change_is_out_of_date(session, proposal)
    if proposal.kind == RULE:
        found = _category_row(session, proposal.value)
        if _rule_exists(session, proposal.match or "", proposal.pattern or ""):
            return True
        missing = found is None or found.parent_id is None
        return chain_out_of_date(session, proposal, target_missing=missing)
    if proposal.kind == ALIAS:
        try:
            check_alias(proposal.source or "", proposal.value, alias_map(session))
        except ValueError:
            return True
        return False
    if proposal.kind != CATEGORY:
        return pair_is_out_of_date(session, proposal)
    return category_is_out_of_date(session, proposal)


def _open_row(session: Session, proposal_id: int) -> ProposalRow:
    row = session.get(ProposalRow, proposal_id)
    if row is None:
        raise ValueError("proposal not found")
    if row.status != OPEN:
        raise ValueError(f"proposal {proposal_id} is already {row.status}")
    return row


def accept_proposal(session: Session, proposal_id: int) -> Proposal:
    row = _open_row(session, proposal_id)
    waiting = waits_for(session, to_proposal(row))
    if waiting is not None:
        raise ValueError(f"proposal {proposal_id} waits for proposal {waiting}")
    if proposal_out_of_date(session, to_proposal(row)):
        if row.kind in (GROUP, NEW_CATEGORY, CATEGORY_RENAME, CATEGORY_DELETE):
            raise ValueError(f"proposal {proposal_id} is out of date: the categories changed since")
        if row.kind == CATEGORY:
            if row.parent_id is None and _category_row(session, row.value) is None:
                set_category_by_hand(session, row.target_id, row.value)
            raise ValueError(
                f"proposal {proposal_id} is out of date: the transaction was decided since"
            )
        if row.kind in (RULE, RULE_EDIT, RULE_DELETE):
            raise ValueError(
                f"proposal {proposal_id} is out of date: the rules or categories changed since"
            )
        if row.kind == ALIAS:
            raise ValueError(
                f"proposal {proposal_id} is out of date: the merchant aliases changed since"
            )
        raise ValueError(
            f"proposal {proposal_id} is out of date: the transactions were decided since"
        )
    if row.kind in (GROUP, NEW_CATEGORY):
        from finances.db.repositories.new_categories import accept_new

        accept_new(session, row)
    elif row.kind in (CATEGORY_RENAME, CATEGORY_DELETE):
        accept_category_change(session, row)
    elif row.kind == TRANSFER:
        create_transfer_pair(session, row.target_id, row.other_id, CONFIRMED)
    elif row.kind == NOT_TRANSFER:
        reject_transfer(session, row.target_id, row.other_id)
    elif row.kind == RULE:
        create_rule(session, row.pattern, row.value, row.match, row.priority)
    elif row.kind == ALIAS:
        add_alias(session, row.source or "", row.value)
    elif row.kind in (RULE_EDIT, RULE_DELETE):
        accept_rule_change(session, row)
    else:
        set_category_by_hand(session, row.target_id, row.value)
    row.status = ACCEPTED
    row.decided_at = _now()
    session.flush()
    record_change(
        session,
        action="proposal_accepted",
        kind="proposal",
        record_id=row.id,
        after=proposal_text(to_proposal(row)),
    )
    return to_proposal(row)


def decline_proposal(session: Session, proposal_id: int) -> Proposal:
    row = _open_row(session, proposal_id)
    row.status = DECLINED
    row.decided_at = _now()
    session.flush()
    record_change(
        session,
        action="proposal_declined",
        kind="proposal",
        record_id=row.id,
        after=proposal_text(to_proposal(row)),
    )
    return to_proposal(row)


def log_advice(session: Session, text: str, subject: str = "") -> Advice:
    clean_text = text.strip()
    if not 1 <= len(clean_text) <= ADVICE_TEXT_LIMIT:
        raise ValueError("advice must be 1 to 1000 characters")
    clean_subject = collapse_ws(subject)
    if len(clean_subject) > NAME_LIMIT:
        raise ValueError("a subject is at most 100 characters")
    row = AdviceRow(created_at=_now(), subject=clean_subject, text=clean_text)
    session.add(row)
    session.flush()
    return to_advice(row)


def list_advice(session: Session, *, limit: int = 20) -> list[Advice]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    stmt = select(AdviceRow).order_by(AdviceRow.created_at.desc(), AdviceRow.id.desc()).limit(limit)
    return [to_advice(row) for row in session.scalars(stmt).all()]
