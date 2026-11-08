from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from finances.db.orm import ProposalRow, to_proposal
from finances.db.repositories.findings import (
    _store_finding_status,
    list_finding_statuses,
)
from finances.domain.findings import FINDING_STATUSES, HANDLED, status_for, status_of
from finances.domain.insights import Finding
from finances.domain.proposals import DECLINED, FINDING_STATUS, OPEN, Proposal
from finances.domain.text import NAME_LIMIT, PROPOSAL_TEXT_LIMIT, collapse_ws, fit


def _now() -> datetime:
    return datetime.now(UTC)


def finding_status_is_out_of_date(session: Session, proposal: Proposal) -> bool:
    month = proposal.finding_month
    assert month is not None
    return (
        status_for(
            proposal.finding_type or "",
            proposal.finding_subject or "",
            month,
            list_finding_statuses(session),
        )
        is not None
    )


def accept_finding_status(session: Session, row: ProposalRow) -> None:
    month = row.finding_month
    assert month is not None
    finding = Finding(row.finding_type or "", "low", month, row.finding_subject or "", 0, "")
    _store_finding_status(session, finding, row.value)


def propose_finding_status(
    session: Session, finding: Finding, status: str, reason: str
) -> Proposal:
    clean_reason = collapse_ws(reason)
    if not 1 <= len(clean_reason) <= PROPOSAL_TEXT_LIMIT:
        raise ValueError("a reason must be 1 to 200 characters")
    if status not in FINDING_STATUSES:
        raise ValueError("status must be one of: " + ", ".join(FINDING_STATUSES))
    current = status_of(finding, list_finding_statuses(session))
    if current is not None:
        raise ValueError(f"this finding is already {current}")
    existing = session.scalars(select(ProposalRow).where(ProposalRow.kind == FINDING_STATUS)).all()
    wanted = finding.subject.casefold()
    if any(
        item.status == DECLINED
        and item.value == status
        and item.finding_type == finding.type
        and (item.finding_subject or "").casefold() == wanted
        and (status != HANDLED or item.finding_month == finding.month)
        for item in existing
    ):
        raise ValueError("a person declined this proposal already")
    if any(
        item.status == OPEN
        and item.finding_type == finding.type
        and (item.finding_subject or "").casefold() == wanted
        and item.finding_month == finding.month
        for item in existing
    ):
        raise ValueError("this finding already has an open proposal")
    stored = ProposalRow(
        kind=FINDING_STATUS,
        target_id=0,
        value=status,
        reason=clean_reason,
        status=OPEN,
        created_at=_now(),
        finding_type=fit(finding.type, NAME_LIMIT),
        finding_subject=fit(finding.subject, NAME_LIMIT),
        finding_month=finding.month,
    )
    session.add(stored)
    session.flush()
    return to_proposal(stored)
