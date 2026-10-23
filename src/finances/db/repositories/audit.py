from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from finances.db.orm import AuditRow, to_change
from finances.domain.audit import ACTIONS, KINDS, PERSON, WHO, Change
from finances.domain.text import AUDIT_TEXT_LIMIT, fit


def _now() -> datetime:
    return datetime.now(UTC)


def record_change(
    session: Session,
    *,
    action: str,
    kind: str,
    record_id: int | None,
    before: str | None = None,
    after: str | None = None,
    who: str = PERSON,
) -> Change:
    if action not in ACTIONS:
        raise ValueError("action must be one of: " + ", ".join(ACTIONS))
    if kind not in KINDS:
        raise ValueError("kind must be one of: " + ", ".join(KINDS))
    if who not in WHO:
        raise ValueError("who must be one of: " + ", ".join(WHO))
    row = AuditRow(
        at=_now(),
        who=who,
        action=action,
        kind=kind,
        record_id=record_id,
        before=None if before is None else fit(before, AUDIT_TEXT_LIMIT),
        after=None if after is None else fit(after, AUDIT_TEXT_LIMIT),
    )
    session.add(row)
    session.flush()
    return to_change(row)


def list_changes(
    session: Session, *, since: date | None = None, action: str | None = None, limit: int = 50
) -> list[Change]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    stmt = select(AuditRow)
    if since is not None:
        start = datetime(since.year, since.month, since.day, tzinfo=UTC)
        stmt = stmt.where(AuditRow.at >= start)
    if action is not None:
        stmt = stmt.where(AuditRow.action == action)
    stmt = stmt.order_by(AuditRow.at.desc(), AuditRow.id.desc()).limit(limit)
    return [to_change(row) for row in session.scalars(stmt).all()]
