"""Store an aggregator feed as provisional transactions and measure balance drift."""

from sqlalchemy.orm import Session

from finances.db.repositories import (
    create_feed_pull,
    delete_feed_transaction,
    feed_posted_total,
    find_feed_transactions,
    get_account,
    insert_feed_transaction,
    latest_feed_pull,
    set_balance_snapshot,
    update_feed_transaction,
)
from finances.domain.models import (
    DataSource,
    FeedPull,
    NewTransaction,
    Transaction,
    validate_last4,
)
from finances.sync.feed import AccountFeed, FeedError, FeedTransaction, feed_fingerprint

_ID_LIMIT = 100
_DESCRIPTION_LIMIT = 500


def _usable_id(feed_id: str) -> bool:
    return 0 < len(feed_id) <= _ID_LIMIT and feed_id == feed_id.strip()


def _description(text: str) -> str:
    return " ".join(text.split())[:_DESCRIPTION_LIMIT].rstrip()


def _check(feed: AccountFeed) -> None:
    """Raise FeedError when the feed breaks a rule. Messages never carry feed content."""
    ids = [item.feed_id for item in feed.transactions]
    replaced = [
        item.replaces_feed_id for item in feed.transactions if item.replaces_feed_id is not None
    ]
    if not all(_usable_id(name) for name in [*ids, *replaced, *feed.removed_feed_ids]):
        raise FeedError("feed has an unusable transaction id")
    for item in feed.transactions:
        if not _description(item.description):
            raise FeedError("feed has an empty description")
        try:
            validate_last4(item.card_last4)
        except ValueError:
            raise FeedError("feed has unusable card digits") from None
    if len(set(ids)) != len(ids):
        raise FeedError("feed has a duplicate transaction id")
    if set(ids) & set(feed.removed_feed_ids):
        raise FeedError("feed removes a transaction it also delivers")
    if (feed.balance_cents is None) != (feed.balance_date is None):
        raise FeedError("feed balance and its date must come together")


def _unchanged(stored: Transaction, item: FeedTransaction, description: str) -> bool:
    return (
        stored.posted_date,
        stored.transaction_date,
        stored.amount_cents,
        stored.description,
        stored.card_last4,
        stored.is_pending,
    ) == (
        item.posted_date,
        item.transaction_date,
        item.amount_cents,
        description,
        item.card_last4,
        item.is_pending,
    )


def apply_feed(session: Session, account_id: int, feed: AccountFeed) -> FeedPull:
    """Store what the feed delivers for one account. The caller commits."""
    if get_account(session, account_id) is None:
        raise FeedError("account not found")
    _check(feed)
    wanted = [item.feed_id for item in feed.transactions]
    wanted += [
        item.replaces_feed_id for item in feed.transactions if item.replaces_feed_id is not None
    ]
    stored_by_id = find_feed_transactions(session, account_id, wanted)
    inserted = updated = unchanged = removed = 0

    for item in feed.transactions:
        description = _description(item.description)
        key = item.feed_id
        stored = stored_by_id.get(key)
        if stored is None and item.replaces_feed_id is not None:
            candidate = stored_by_id.get(item.replaces_feed_id)
            if candidate is not None and candidate.source == DataSource.AGGREGATOR:
                key, stored = item.replaces_feed_id, candidate
        fingerprint = feed_fingerprint(account_id, item.feed_id)
        if stored is None:
            new = NewTransaction(
                account_id=account_id,
                statement_id=None,
                posted_date=item.posted_date,
                transaction_date=item.transaction_date,
                amount_cents=item.amount_cents,
                description=description,
                section=None,
                card_last4=item.card_last4,
                cardholder=None,
                external_id=None,
                source=DataSource.AGGREGATOR,
                is_pending=item.is_pending,
                fingerprint=fingerprint,
            )
            stored_by_id[item.feed_id] = insert_feed_transaction(session, new, item.feed_id)
            inserted += 1
        elif stored.source == DataSource.STATEMENT or (
            key == item.feed_id and _unchanged(stored, item, description)
        ):
            unchanged += 1
        else:
            del stored_by_id[key]
            stored_by_id[item.feed_id] = update_feed_transaction(
                session,
                stored.id,
                feed_id=item.feed_id,
                posted_date=item.posted_date,
                transaction_date=item.transaction_date,
                amount_cents=item.amount_cents,
                description=description,
                card_last4=item.card_last4,
                is_pending=item.is_pending,
                fingerprint=fingerprint,
            )
            updated += 1

    gone = find_feed_transactions(session, account_id, dict.fromkeys(feed.removed_feed_ids))
    for stored in gone.values():
        if stored.source == DataSource.AGGREGATOR:
            delete_feed_transaction(session, stored.id)
            removed += 1

    total = feed_posted_total(session, account_id)
    drift = None
    if feed.balance_cents is not None and feed.balance_date is not None:
        previous = latest_feed_pull(session, account_id, with_balance=True)
        if previous is not None and previous.balance_cents is not None:
            moved = feed.balance_cents - previous.balance_cents
            drift = moved - (total - previous.feed_total_cents)
        set_balance_snapshot(
            session, account_id, feed.balance_date, feed.balance_cents, DataSource.AGGREGATOR
        )
    return create_feed_pull(
        session,
        account_id=account_id,
        inserted=inserted,
        updated=updated,
        removed=removed,
        unchanged=unchanged,
        feed_total_cents=total,
        balance_cents=feed.balance_cents,
        balance_date=feed.balance_date,
        drift_cents=drift,
    )
