from collections.abc import Iterable
from datetime import date

from sqlalchemy import (
    delete,
    func,
    select,
)
from sqlalchemy.orm import Session

from finances.db.orm import (
    FeedItemRow,
    FeedPullRow,
    TransactionRow,
    TransferPairRow,
    TransferRejectionRow,
    to_feed_pull,
    to_transaction,
)
from finances.db.repositories.categories import remove_category
from finances.db.repositories.transactions import _FINGERPRINT_CHUNK
from finances.db.repositories.transfers import _names
from finances.domain.models import (
    DataSource,
    FeedPull,
    NewTransaction,
    Transaction,
)


def _feed_item(session: Session, transaction_id: int) -> FeedItemRow | None:
    stmt = select(FeedItemRow).where(FeedItemRow.transaction_id == transaction_id)
    return session.scalars(stmt).first()


def find_feed_transactions(
    session: Session, account_id: int, feed_ids: Iterable[str]
) -> dict[str, Transaction]:
    """Return the account's stored transactions for these feed ids, keyed by feed id."""
    pending = list(feed_ids)
    found: dict[str, Transaction] = {}
    for start in range(0, len(pending), _FINGERPRINT_CHUNK):
        chunk = pending[start : start + _FINGERPRINT_CHUNK]
        stmt = (
            select(FeedItemRow.feed_id, TransactionRow)
            .join(TransactionRow, TransactionRow.id == FeedItemRow.transaction_id)
            .where(FeedItemRow.account_id == account_id, FeedItemRow.feed_id.in_(chunk))
        )
        for feed_id, row in session.execute(stmt).all():
            found[feed_id] = to_transaction(row)
    return found


def insert_feed_transaction(session: Session, item: NewTransaction, feed_id: str) -> Transaction:
    """Add a transaction that came from the feed, with its feed id. The caller commits."""
    row = TransactionRow(
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
    session.add(row)
    session.flush()
    session.add(FeedItemRow(account_id=item.account_id, feed_id=feed_id, transaction_id=row.id))
    session.flush()
    return to_transaction(row)


def update_feed_transaction(
    session: Session,
    transaction_id: int,
    *,
    feed_id: str,
    posted_date: date,
    transaction_date: date | None,
    amount_cents: int,
    description: str,
    card_last4: str | None,
    is_pending: bool,
    fingerprint: str,
) -> Transaction:
    """Change a transaction that came from the feed, keeping its id. The caller commits."""
    row = session.get(TransactionRow, transaction_id)
    item = _feed_item(session, transaction_id)
    if row is None or item is None:
        raise ValueError("transaction did not come from the feed")
    row.posted_date = posted_date
    row.transaction_date = transaction_date
    row.amount_cents = amount_cents
    row.description = description
    row.card_last4 = card_last4
    row.is_pending = is_pending
    row.fingerprint = fingerprint
    item.feed_id = feed_id
    session.flush()
    return to_transaction(row)


def delete_feed_transaction(session: Session, transaction_id: int) -> bool:
    """Delete a transaction that came from the feed and its feed id; False if it did not."""
    item = _feed_item(session, transaction_id)
    if item is None:
        return False
    session.delete(item)
    remove_category(session, transaction_id)
    session.execute(delete(TransferPairRow).where(_names(TransferPairRow, transaction_id)))
    session.execute(
        delete(TransferRejectionRow).where(_names(TransferRejectionRow, transaction_id))
    )
    session.flush()
    session.delete(session.get(TransactionRow, transaction_id))
    session.flush()
    return True


def feed_posted_total(session: Session, account_id: int) -> int:
    """Return the sum of the account's posted transactions that came from the feed."""
    stmt = (
        select(func.coalesce(func.sum(TransactionRow.amount_cents), 0))
        .join(FeedItemRow, FeedItemRow.transaction_id == TransactionRow.id)
        .where(TransactionRow.account_id == account_id, TransactionRow.is_pending.is_(False))
    )
    return int(session.scalar(stmt))


def create_feed_pull(
    session: Session,
    *,
    account_id: int,
    inserted: int,
    updated: int,
    removed: int,
    unchanged: int,
    feed_total_cents: int,
    balance_cents: int | None,
    balance_date: date | None,
    drift_cents: int | None,
) -> FeedPull:
    """Add one feed pull record and return it. The caller commits."""
    row = FeedPullRow(
        account_id=account_id,
        inserted=inserted,
        updated=updated,
        removed=removed,
        unchanged=unchanged,
        feed_total_cents=feed_total_cents,
        balance_cents=balance_cents,
        balance_date=balance_date,
        drift_cents=drift_cents,
    )
    session.add(row)
    session.flush()
    return to_feed_pull(row)


def latest_feed_pull(
    session: Session, account_id: int, *, with_balance: bool = False
) -> FeedPull | None:
    """Return the account's newest pull, only among pulls with a balance when asked, or None."""
    stmt = select(FeedPullRow).where(FeedPullRow.account_id == account_id)
    if with_balance:
        stmt = stmt.where(FeedPullRow.balance_cents.is_not(None))
    row = session.scalars(stmt.order_by(FeedPullRow.id.desc()).limit(1)).first()
    return to_feed_pull(row) if row is not None else None


def list_provisional_transactions(
    session: Session, account_id: int, start: date, end: date
) -> list[Transaction]:
    """Return the account's posted aggregator rows dated from start to end, in id order."""
    stmt = (
        select(TransactionRow)
        .where(
            TransactionRow.account_id == account_id,
            TransactionRow.source == DataSource.AGGREGATOR.value,
            TransactionRow.is_pending.is_(False),
            TransactionRow.posted_date >= start,
            TransactionRow.posted_date <= end,
        )
        .order_by(TransactionRow.id)
    )
    return [to_transaction(row) for row in session.scalars(stmt).all()]


def confirm_transaction(
    session: Session,
    transaction_id: int,
    *,
    statement_id: int,
    posted_date: date,
    transaction_date: date | None,
    description: str,
    section: str | None,
    card_last4: str | None,
    cardholder: str | None,
    external_id: str | None,
    fingerprint: str,
) -> Transaction:
    """Turn a stored row into a statement row in place, keeping its id. The caller commits."""
    row = session.get(TransactionRow, transaction_id)
    if row is None:
        raise ValueError("transaction not found")
    row.statement_id = statement_id
    row.posted_date = posted_date
    row.transaction_date = transaction_date
    row.description = description
    row.section = section
    row.card_last4 = card_last4
    row.cardholder = cardholder
    row.external_id = external_id
    row.fingerprint = fingerprint
    row.source = DataSource.STATEMENT.value
    row.is_pending = False
    session.flush()
    return to_transaction(row)


def find_unlinked_statement_transactions(
    session: Session, account_id: int, amount_cents: int, start: date, end: date
) -> list[Transaction]:
    """Return the account's statement rows of this amount, dated start to end, with no feed id."""
    linked = select(FeedItemRow.id).where(FeedItemRow.transaction_id == TransactionRow.id)
    stmt = (
        select(TransactionRow)
        .where(
            TransactionRow.account_id == account_id,
            TransactionRow.source == DataSource.STATEMENT.value,
            TransactionRow.amount_cents == amount_cents,
            TransactionRow.posted_date >= start,
            TransactionRow.posted_date <= end,
            ~linked.exists(),
        )
        .order_by(TransactionRow.id)
    )
    return [to_transaction(row) for row in session.scalars(stmt).all()]


def link_feed_transaction(
    session: Session, account_id: int, feed_id: str, transaction_id: int
) -> None:
    """Tie a feed id to a stored transaction. The caller commits."""
    session.add(FeedItemRow(account_id=account_id, feed_id=feed_id, transaction_id=transaction_id))
    session.flush()
