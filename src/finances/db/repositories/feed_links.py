from datetime import (
    date,
    datetime,
)

from sqlalchemy import (
    exists,
    select,
)
from sqlalchemy.orm import Session

from finances.db.orm import (
    FeedAccountRow,
    FeedItemRow,
    FeedSeenAccountRow,
    SyncFailureRow,
    TransactionRow,
    to_feed_account,
    to_seen_feed_account,
    to_sync_failure,
)
from finances.domain.models import (
    DEFAULT_LINK,
    DataSource,
    FeedAccount,
    SeenFeedAccount,
    SyncFailure,
    validate_provider_account_id,
)
from finances.domain.text import (
    NAME_LIMIT,
    PROVIDER_ACCOUNT_ID_LIMIT,
    fit,
)


def map_feed_account(
    session: Session, account_id: int, provider_account_id: str, link: str = DEFAULT_LINK
) -> FeedAccount:
    """Make the link's aggregator account feed the account, replacing its old one.

    The caller commits.
    """
    provider_account_id = validate_provider_account_id(provider_account_id)
    taken = session.scalars(
        select(FeedAccountRow).where(
            FeedAccountRow.link == link,
            FeedAccountRow.provider_account_id == provider_account_id,
        )
    ).first()
    if taken is not None and taken.account_id != account_id:
        raise ValueError("feed account is already mapped to another account")
    row = session.scalars(
        select(FeedAccountRow).where(FeedAccountRow.account_id == account_id)
    ).first()
    if row is None:
        row = FeedAccountRow(
            account_id=account_id, provider_account_id=provider_account_id, link=link
        )
        session.add(row)
    else:
        row.provider_account_id = provider_account_id
        row.link = link
    session.flush()
    return to_feed_account(row)


def list_feed_accounts(session: Session, link: str | None = None) -> list[FeedAccount]:
    """Return every mapping, or only the link's when one is given, in id order."""
    stmt = select(FeedAccountRow).order_by(FeedAccountRow.id)
    if link is not None:
        stmt = stmt.where(FeedAccountRow.link == link)
    return [to_feed_account(row) for row in session.scalars(stmt).all()]


def record_seen_feed_account(
    session: Session, link: str, provider_account_id: str, name: str, institution: str, day: date
) -> None:
    """Remember that a sync delivered this aggregator account under the link. The caller commits."""
    row = session.scalars(
        select(FeedSeenAccountRow).where(
            FeedSeenAccountRow.link == link,
            FeedSeenAccountRow.provider_account_id == provider_account_id,
        )
    ).first()
    if row is None:
        row = FeedSeenAccountRow(
            link=link,
            provider_account_id=provider_account_id,
            first_seen=day,
            last_seen=day,
            ignored=False,
        )
        session.add(row)
    else:
        row.last_seen = max(row.last_seen, day)
    row.name = fit(name, NAME_LIMIT)
    row.institution = fit(institution, NAME_LIMIT)
    session.flush()


def list_new_feed_accounts(
    session: Session, link: str | None = None, *, ignored: bool = False
) -> list[SeenFeedAccount]:
    """Return the seen accounts not mapped under their own link, by link, first day, then id."""
    mapped = exists().where(
        FeedAccountRow.link == FeedSeenAccountRow.link,
        FeedAccountRow.provider_account_id == FeedSeenAccountRow.provider_account_id,
    )
    stmt = (
        select(FeedSeenAccountRow)
        .where(~mapped, FeedSeenAccountRow.ignored.is_(ignored))
        .order_by(FeedSeenAccountRow.link, FeedSeenAccountRow.first_seen, FeedSeenAccountRow.id)
    )
    if link is not None:
        stmt = stmt.where(FeedSeenAccountRow.link == link)
    return [to_seen_feed_account(row) for row in session.scalars(stmt).all()]


def set_feed_account_ignored(
    session: Session, link: str, provider_account_id: str, ignored: bool
) -> None:
    """Stop or start offering a seen account for setup. The caller commits."""
    row = session.scalars(
        select(FeedSeenAccountRow).where(
            FeedSeenAccountRow.link == link,
            FeedSeenAccountRow.provider_account_id == provider_account_id,
        )
    ).first()
    if row is None:
        raise ValueError("SimpleFIN account not found")
    row.ignored = ignored
    session.flush()


def list_feed_links(session: Session) -> list[str]:
    """Return the links that have a mapping or a seen account, sorted."""
    mapped = session.scalars(select(FeedAccountRow.link).distinct()).all()
    seen = session.scalars(select(FeedSeenAccountRow.link).distinct()).all()
    return sorted({*mapped, *seen})


def list_pending_feed_ids(session: Session, account_id: int, since: date) -> list[str]:
    """Return the feed ids of the account's pending aggregator rows dated since or later."""
    stmt = (
        select(FeedItemRow.feed_id)
        .join(TransactionRow, TransactionRow.id == FeedItemRow.transaction_id)
        .where(
            TransactionRow.account_id == account_id,
            TransactionRow.source == DataSource.AGGREGATOR.value,
            TransactionRow.is_pending.is_(True),
            TransactionRow.posted_date >= since,
        )
        .order_by(TransactionRow.id)
    )
    return list(session.scalars(stmt).all())


def record_sync_failure(session: Session, link: str, failed_at: datetime, message: str) -> None:
    """Store or replace this link's last failure. The caller commits."""
    found = session.scalars(select(SyncFailureRow).where(SyncFailureRow.link == link)).first()
    cut = fit(message, PROVIDER_ACCOUNT_ID_LIMIT)
    if found is None:
        session.add(SyncFailureRow(link=link, failed_at=failed_at, message=cut))
    else:
        found.failed_at = failed_at
        found.message = cut
    session.flush()


def clear_sync_failure(session: Session, link: str) -> None:
    """Delete this link's last failure, if any. The caller commits."""
    found = session.scalars(select(SyncFailureRow).where(SyncFailureRow.link == link)).first()
    if found is not None:
        session.delete(found)
        session.flush()


def list_sync_failures(session: Session) -> list[SyncFailure]:
    """Return every stored sync failure, ordered by link."""
    stmt = select(SyncFailureRow).order_by(SyncFailureRow.link)
    return [to_sync_failure(row) for row in session.scalars(stmt).all()]
