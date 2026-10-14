"""Store an aggregator feed as provisional transactions and measure balance drift."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from finances.db.repositories import (
    create_feed_pull,
    delete_feed_transaction,
    feed_posted_total,
    find_feed_transactions,
    find_unlinked_statement_transactions,
    get_account,
    insert_feed_transaction,
    latest_feed_pull,
    link_feed_transaction,
    set_balance_snapshot,
    statement_covers,
    statement_periods,
    update_feed_transaction,
)
from finances.domain.matching import MATCH_MAX_DAYS, MatchItem, match_one_to_one, period_zone
from finances.domain.models import (
    DataSource,
    FeedPull,
    NewTransaction,
    Transaction,
    validate_last4,
)
from finances.domain.text import DESCRIPTION_LIMIT, FEED_ID_LIMIT, fit
from finances.sync.feed import AccountFeed, FeedError, FeedTransaction, feed_fingerprint


def _usable_id(feed_id: str) -> bool:
    return 0 < len(feed_id) <= FEED_ID_LIMIT and feed_id == feed_id.strip()


def _check(feed: AccountFeed) -> None:
    """Raise FeedError when the feed breaks a rule. Messages never carry feed content."""
    ids = [item.feed_id for item in feed.transactions]
    replaced = [
        item.replaces_feed_id for item in feed.transactions if item.replaces_feed_id is not None
    ]
    if not all(_usable_id(name) for name in [*ids, *replaced, *feed.removed_feed_ids]):
        raise FeedError("feed has an unusable transaction id")
    for item in feed.transactions:
        if not fit(item.description, DESCRIPTION_LIMIT):
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


def _resolve(
    item: FeedTransaction, stored_by_id: dict[str, Transaction]
) -> tuple[str, Transaction | None]:
    """Return the feed id the item is stored under and its stored row, if any."""
    key = item.feed_id
    stored = stored_by_id.get(key)
    if stored is None and item.replaces_feed_id is not None:
        candidate = stored_by_id.get(item.replaces_feed_id)
        if candidate is not None and candidate.source == DataSource.AGGREGATOR:
            key, stored = item.replaces_feed_id, candidate
    return key, stored


def _settles(item: FeedTransaction, stored: Transaction | None) -> bool:
    return not item.is_pending and (
        stored is None or (stored.is_pending and stored.source == DataSource.AGGREGATOR)
    )


def _statement_rows(
    session: Session, account_id: int, settling: list[tuple[int, FeedTransaction]]
) -> dict[int, Transaction]:
    """Pair a pull's settling transactions with unlinked statement rows, all at once.

    Returns each paired transaction's statement row, keyed by its position in the feed.
    """
    reach = timedelta(days=MATCH_MAX_DAYS)
    days_by_amount: dict[int, list[date]] = {}
    for _, item in settling:
        days_by_amount.setdefault(item.amount_cents, []).append(item.posted_date)
    rows: dict[int, Transaction] = {}
    for amount, days in days_by_amount.items():
        found = find_unlinked_statement_transactions(
            session, account_id, amount, min(days) - reach, max(days) + reach
        )
        rows.update((row.id, row) for row in found)
    periods = statement_periods(session, account_id)
    pairs = match_one_to_one(
        [
            MatchItem(
                index, item.amount_cents, item.posted_date, period_zone(item.posted_date, periods)
            )
            for index, item in settling
        ],
        [
            MatchItem(
                row.id, row.amount_cents, row.posted_date, period_zone(row.posted_date, periods)
            )
            for row in sorted(rows.values(), key=lambda row: row.id)
        ],
    )
    return {index: rows[row_id] for index, row_id in pairs}


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
    settling = [
        (index, item)
        for index, item in enumerate(feed.transactions)
        if _settles(item, _resolve(item, stored_by_id)[1])
    ]
    partners = _statement_rows(session, account_id, settling)

    for index, item in enumerate(feed.transactions):
        description = fit(item.description, DESCRIPTION_LIMIT)
        key, stored = _resolve(item, stored_by_id)
        if _settles(item, stored):
            statement_row = partners.get(index)
            if statement_row is not None or statement_covers(session, account_id, item.posted_date):
                if stored is not None:
                    delete_feed_transaction(session, stored.id)
                    del stored_by_id[key]
                    removed += 1
                else:
                    unchanged += 1
                if statement_row is not None:
                    link_feed_transaction(session, account_id, item.feed_id, statement_row.id)
                    stored_by_id[item.feed_id] = statement_row
                continue
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
