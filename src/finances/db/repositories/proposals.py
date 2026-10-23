from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from finances.db.orm import AdviceRow, CategoryRuleRow, ProposalRow, to_advice, to_proposal
from finances.db.repositories.assignments import _assignment_row, set_category_by_hand
from finances.db.repositories.audit import record_change
from finances.db.repositories.categories import _category_row, _leaf_category, create_rule
from finances.db.repositories.transactions import get_transaction
from finances.db.repositories.transfers import (
    _check_transfer,
    create_transfer_pair,
    find_transfer_pair,
    list_transfer_rejections,
    reject_transfer,
)
from finances.domain.merchants import clean_merchant
from finances.domain.models import CONFIRMED, MANUAL, CategoryRule
from finances.domain.proposals import (
    ACCEPTED,
    CATEGORY,
    DECLINED,
    NOT_TRANSFER,
    OPEN,
    RULE,
    STATUSES,
    TRANSFER,
    Advice,
    Proposal,
    out_of_date,
    pair_out_of_date,
    proposal_text,
    rule_out_of_date,
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
    if row is not None and row.source == MANUAL:
        return True
    return find_transfer_pair(session, transaction_id) is not None


def propose_category(session: Session, transaction_id: int, category: str, reason: str) -> Proposal:
    clean = collapse_ws(reason)
    if not 1 <= len(clean) <= PROPOSAL_TEXT_LIMIT:
        raise ValueError("a reason must be 1 to 200 characters")
    if get_transaction(session, transaction_id) is None:
        raise ValueError("transaction not found")
    target = _leaf_category(session, category)
    if decided_by_a_person(session, transaction_id):
        raise ValueError("a person has already decided this transaction")
    existing = session.scalars(
        select(ProposalRow).where(
            ProposalRow.kind == CATEGORY, ProposalRow.target_id == transaction_id
        )
    ).all()
    if any(row.status == DECLINED and row.value == target.name for row in existing):
        raise ValueError("a person declined this proposal already")
    if any(row.status == OPEN for row in existing):
        raise ValueError("this transaction already has an open proposal")
    row = ProposalRow(
        kind=CATEGORY,
        target_id=transaction_id,
        value=target.name,
        reason=clean,
        status=OPEN,
        created_at=_now(),
        decided_at=None,
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


def _rule_exists(session: Session, match: str, pattern: str) -> bool:
    clean = normalize_pattern(pattern)
    stmt = select(CategoryRuleRow.id).where(
        CategoryRuleRow.match == match, CategoryRuleRow.pattern == clean
    )
    return session.scalars(stmt).first() is not None


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
    target = _leaf_category(session, category)
    probe = CategoryRule(0, stored, match, priority, target.id)
    if not rule_matches(probe, clean_merchant(example.description)):
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
    if any(row.status == DECLINED and row.value == target.name for row in existing):
        raise ValueError("a person declined this proposal already")
    if any(row.status == OPEN for row in existing):
        raise ValueError("this rule already has an open proposal")
    row = ProposalRow(
        kind=RULE,
        target_id=example_id,
        value=target.name,
        reason=clean,
        status=OPEN,
        created_at=_now(),
        decided_at=None,
        other_id=None,
        pattern=stored,
        match=match,
        priority=priority,
    )
    session.add(row)
    session.flush()
    return to_proposal(row)


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
    if proposal.kind == RULE:
        found = _category_row(session, proposal.value)
        return rule_out_of_date(
            category_found=found is not None and found.parent_id is not None,
            rule_exists=_rule_exists(session, proposal.match or "", proposal.pattern or ""),
        )
    if proposal.kind != CATEGORY:
        in_id = proposal.other_id
        exists = (
            get_transaction(session, proposal.target_id) is not None
            and in_id is not None
            and get_transaction(session, in_id) is not None
        )
        paired = find_transfer_pair(session, proposal.target_id) is not None or (
            in_id is not None and find_transfer_pair(session, in_id) is not None
        )
        rejected = in_id is not None and (proposal.target_id, in_id) in list_transfer_rejections(
            session
        )
        return pair_out_of_date(exists=exists, paired=paired, rejected=rejected)
    row = _assignment_row(session, proposal.target_id)
    return out_of_date(
        exists=get_transaction(session, proposal.target_id) is not None,
        set_by_hand=row is not None and row.source == MANUAL,
        paired=find_transfer_pair(session, proposal.target_id) is not None,
    )


def _open_row(session: Session, proposal_id: int) -> ProposalRow:
    row = session.get(ProposalRow, proposal_id)
    if row is None:
        raise ValueError("proposal not found")
    if row.status != OPEN:
        raise ValueError(f"proposal {proposal_id} is already {row.status}")
    return row


def accept_proposal(session: Session, proposal_id: int) -> Proposal:
    row = _open_row(session, proposal_id)
    if proposal_out_of_date(session, to_proposal(row)):
        if row.kind == CATEGORY:
            raise ValueError(
                f"proposal {proposal_id} is out of date: the transaction was decided since"
            )
        if row.kind == RULE:
            raise ValueError(
                f"proposal {proposal_id} is out of date: the rules or categories changed since"
            )
        raise ValueError(
            f"proposal {proposal_id} is out of date: the transactions were decided since"
        )
    if row.kind == TRANSFER:
        create_transfer_pair(session, row.target_id, row.other_id, CONFIRMED)
    elif row.kind == NOT_TRANSFER:
        reject_transfer(session, row.target_id, row.other_id)
    elif row.kind == RULE:
        create_rule(session, row.pattern, row.value, row.match, row.priority)
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
