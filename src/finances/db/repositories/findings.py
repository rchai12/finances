from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from finances.db.orm import FindingStatusRow, to_finding_status
from finances.db.repositories.audit import record_change
from finances.domain.findings import (
    FINDING_STATUSES,
    HANDLED,
    IGNORED,
    FindingStatus,
    finding_text,
    status_of,
)
from finances.domain.insights import TYPES, Finding
from finances.domain.text import NAME_LIMIT, fit


def _now() -> datetime:
    return datetime.now(UTC)


def _store_finding_status(session: Session, finding: Finding, status: str) -> FindingStatus:
    row = FindingStatusRow(
        type=fit(finding.type, NAME_LIMIT),
        subject=fit(finding.subject, NAME_LIMIT),
        month=finding.month if status == HANDLED else None,
        status=status,
        set_at=_now(),
    )
    session.add(row)
    session.flush()
    action = "finding_handled" if status == HANDLED else "finding_ignored"
    record_change(
        session,
        action=action,
        kind="finding",
        record_id=row.id,
        after=finding_text(row.type, row.subject, row.month),
    )
    return to_finding_status(row)


def set_finding_status(session: Session, finding: Finding, status: str) -> FindingStatus:
    if status not in FINDING_STATUSES:
        raise ValueError("status must be one of: " + ", ".join(FINDING_STATUSES))
    current = status_of(finding, list_finding_statuses(session))
    if current is not None:
        raise ValueError(f"this finding is already {current}")
    return _store_finding_status(session, finding, status)


def reopen_finding(session: Session, type: str, subject: str, month: date) -> list[FindingStatus]:
    if type not in TYPES:
        raise ValueError("type must be one of: " + ", ".join(TYPES))
    wanted = subject.strip().casefold()
    matching = [
        row
        for row in session.scalars(select(FindingStatusRow).where(FindingStatusRow.type == type))
        if row.subject.casefold() == wanted
        and (row.status == IGNORED or (row.status == HANDLED and row.month == month))
    ]
    if not matching:
        raise ValueError("this finding is open")
    matching.sort(key=lambda row: (0 if row.status == IGNORED else 1, row.id))
    removed = []
    for row in matching:
        stored = to_finding_status(row)
        record_change(
            session,
            action="finding_reopened",
            kind="finding",
            record_id=row.id,
            before=finding_text(row.type, row.subject, row.month),
        )
        session.delete(row)
        removed.append(stored)
    session.flush()
    return removed


def list_finding_statuses(session: Session) -> list[FindingStatus]:
    stmt = select(FindingStatusRow).order_by(FindingStatusRow.id)
    return [to_finding_status(row) for row in session.scalars(stmt).all()]
