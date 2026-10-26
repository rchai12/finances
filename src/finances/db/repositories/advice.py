from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from finances.db.orm import AdviceRow, to_advice
from finances.domain.proposals import Advice


def _now() -> datetime:
    return datetime.now(UTC)


def dismiss_advice(session: Session, advice_id: int) -> Advice:
    row = session.get(AdviceRow, advice_id)
    if row is None:
        raise ValueError("note not found")
    if row.dismissed_at is not None:
        raise ValueError(f"note {advice_id} is already dismissed")
    row.dismissed_at = _now()
    session.flush()
    return to_advice(row)


def list_open_advice(session: Session, *, limit: int = 50) -> list[Advice]:
    stmt = (
        select(AdviceRow)
        .where(AdviceRow.dismissed_at.is_(None))
        .order_by(AdviceRow.created_at.desc(), AdviceRow.id.desc())
        .limit(limit)
    )
    return [to_advice(row) for row in session.scalars(stmt).all()]
