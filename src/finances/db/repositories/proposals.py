from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from finances.db.orm import AdviceRow, ProposalRow, to_advice, to_proposal
from finances.db.repositories.assignments import _assignment_row, set_category_by_hand
from finances.db.repositories.audit import record_change
from finances.db.repositories.categories import _leaf_category
from finances.db.repositories.transactions import get_transaction
from finances.db.repositories.transfers import find_transfer_pair
from finances.domain.models import MANUAL
from finances.domain.proposals import (
    ACCEPTED,
    CATEGORY,
    DECLINED,
    OPEN,
    STATUSES,
    Advice,
    Proposal,
    out_of_date,
    proposal_text,
)
from finances.domain.text import ADVICE_TEXT_LIMIT, NAME_LIMIT, PROPOSAL_TEXT_LIMIT, collapse_ws


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
        raise ValueError(
            f"proposal {proposal_id} is out of date: the transaction was decided since"
        )
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
