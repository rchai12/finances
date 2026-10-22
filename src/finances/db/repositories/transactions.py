from collections.abc import Iterable
from datetime import date

from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from finances.db.orm import (
    TransactionRow,
    to_transaction,
)
from finances.domain.models import (
    NewTransaction,
    Transaction,
)

_FINGERPRINT_CHUNK = 500


def existing_fingerprints(
    session: Session, account_id: int, fingerprints: Iterable[str]
) -> set[str]:
    """Return which of these fingerprints already belong to a transaction of this account."""
    pending = list(fingerprints)
    found: set[str] = set()
    for start in range(0, len(pending), _FINGERPRINT_CHUNK):
        chunk = pending[start : start + _FINGERPRINT_CHUNK]
        stmt = select(TransactionRow.fingerprint).where(
            TransactionRow.account_id == account_id,
            TransactionRow.fingerprint.in_(chunk),
        )
        found.update(session.scalars(stmt).all())
    return found


def insert_transactions(session: Session, rows: list[NewTransaction]) -> int:
    """Add one transaction per item and return how many were added. The caller commits."""
    if not rows:
        return 0
    for item in rows:
        session.add(
            TransactionRow(
                account_id=item.account_id,
                statement_id=item.statement_id,
                posted_date=item.posted_date,
                transaction_date=item.transaction_date,
                amount_cents=item.amount_cents,
                description=item.description,
                section=item.section,
                card_last4=item.card_last4,
                cardholder=item.cardholder,
                external_id=item.external_id,
                source=item.source.value,
                is_pending=item.is_pending,
                fingerprint=item.fingerprint,
            )
        )
    session.flush()
    return len(rows)


def list_transactions(
    session: Session,
    account_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = 100,
) -> list[Transaction]:
    """Return transactions, latest posted date first, cut off after limit rows."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    stmt = select(TransactionRow)
    if account_id is not None:
        stmt = stmt.where(TransactionRow.account_id == account_id)
    if start is not None:
        stmt = stmt.where(TransactionRow.posted_date >= start)
    if end is not None:
        stmt = stmt.where(TransactionRow.posted_date <= end)
    stmt = stmt.order_by(TransactionRow.posted_date.desc(), TransactionRow.id.desc()).limit(limit)
    return [to_transaction(row) for row in session.scalars(stmt).all()]


def list_transactions_between(session: Session, start: date, end: date) -> list[Transaction]:
    """Posted transactions whose day (bought, else posted) is from start to end, in id order."""
    day = func.coalesce(TransactionRow.transaction_date, TransactionRow.posted_date)
    stmt = (
        select(TransactionRow)
        .where(TransactionRow.is_pending.is_(False), day >= start, day <= end)
        .order_by(TransactionRow.id)
    )
    return [to_transaction(row) for row in session.scalars(stmt).all()]


def list_transactions_by_day(
    session: Session, start: date | None, end: date | None
) -> list[Transaction]:
    """Transactions, pending included, whose day (bought, else posted) is within the bounds given;
    latest posted first, then highest id."""
    day = func.coalesce(TransactionRow.transaction_date, TransactionRow.posted_date)
    stmt = select(TransactionRow)
    if start is not None:
        stmt = stmt.where(day >= start)
    if end is not None:
        stmt = stmt.where(day <= end)
    stmt = stmt.order_by(TransactionRow.posted_date.desc(), TransactionRow.id.desc())
    return [to_transaction(row) for row in session.scalars(stmt).all()]


def list_transaction_descriptions(session: Session) -> list[tuple[int, str]]:
    """Return the id and description of every transaction, in id order."""
    stmt = select(TransactionRow.id, TransactionRow.description).order_by(TransactionRow.id)
    return [(row.id, row.description) for row in session.execute(stmt).all()]


def get_transaction(session: Session, transaction_id: int) -> Transaction | None:
    """Return the transaction with this id, or None."""
    row = session.get(TransactionRow, transaction_id)
    return to_transaction(row) if row is not None else None


def _require_transaction(session: Session, transaction_id: int) -> None:
    if session.get(TransactionRow, transaction_id) is None:
        raise ValueError("transaction not found")


def _distinct_transaction_ids(transaction_ids: Iterable[int]) -> list[int]:
    found: list[int] = []
    seen: set[int] = set()
    for transaction_id in transaction_ids:
        if transaction_id not in seen:
            seen.add(transaction_id)
            found.append(transaction_id)
    if not found:
        raise ValueError("choose at least one transaction")
    if len(found) > 1000:
        raise ValueError("at most 1000 transactions at once")
    return found
