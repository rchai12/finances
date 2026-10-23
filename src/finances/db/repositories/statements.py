from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from finances.db.orm import (
    StatementRow,
    to_statement,
)
from finances.db.repositories.audit import record_change
from finances.domain.audit import SYSTEM
from finances.domain.models import Statement


def create_statement(
    session: Session,
    *,
    account_id: int,
    source_filename: str,
    file_sha256: str,
    parser_name: str,
    period_start: date,
    period_end: date,
    opening_balance_cents: int,
    closing_balance_cents: int,
    lines_parsed: int,
    rows_inserted: int,
    rows_duplicate: int,
) -> Statement:
    """Add one statement record and return it. The caller commits."""
    row = StatementRow(
        account_id=account_id,
        source_filename=source_filename,
        file_sha256=file_sha256,
        parser_name=parser_name,
        period_start=period_start,
        period_end=period_end,
        opening_balance_cents=opening_balance_cents,
        closing_balance_cents=closing_balance_cents,
        lines_parsed=lines_parsed,
        rows_inserted=rows_inserted,
        rows_duplicate=rows_duplicate,
    )
    session.add(row)
    session.flush()
    record_change(
        session,
        action="statement_imported",
        kind="statement",
        record_id=row.id,
        after=f"{row.parser_name}, {row.period_start.isoformat()} to {row.period_end.isoformat()}",
        who=SYSTEM,
    )
    return to_statement(row)


def find_statement_by_hash(session: Session, file_sha256: str) -> Statement | None:
    """Return the statement with this file hash, or None."""
    stmt = select(StatementRow).where(StatementRow.file_sha256 == file_sha256)
    row = session.scalars(stmt).first()
    return to_statement(row) if row is not None else None


def list_statements(session: Session, account_id: int | None = None) -> list[Statement]:
    """Return statements, latest period first and highest id when periods match."""
    stmt = select(StatementRow)
    if account_id is not None:
        stmt = stmt.where(StatementRow.account_id == account_id)
    stmt = stmt.order_by(StatementRow.period_end.desc(), StatementRow.id.desc())
    return [to_statement(row) for row in session.scalars(stmt).all()]


def statement_periods(session: Session, account_id: int) -> list[tuple[date, date]]:
    """Return the first and last day of each of the account's stored statements."""
    return [(item.period_start, item.period_end) for item in list_statements(session, account_id)]


def statement_covers(session: Session, account_id: int, day: date) -> bool:
    """Return whether a stored statement of the account has day inside its period."""
    stmt = (
        select(StatementRow.id)
        .where(
            StatementRow.account_id == account_id,
            StatementRow.period_start <= day,
            StatementRow.period_end >= day,
        )
        .limit(1)
    )
    return session.scalars(stmt).first() is not None
