"""One sync: fetch every account from SimpleFIN and apply each mapped one."""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from finances.db.repositories import list_feed_accounts, list_pending_feed_ids
from finances.domain.models import DEFAULT_LINK, FeedPull
from finances.sync.feed import AccountFeed, FeedError
from finances.sync.service import apply_feed
from finances.sync.simplefin import ProviderAccount, Transport, fetch_accounts

SYNC_DAYS = 30


@dataclass(frozen=True)
class AccountSync:
    """What happened to one account in a sync."""

    provider_account_id: str
    account_id: int | None
    pull: FeedPull | None
    problem: str | None


@dataclass(frozen=True)
class SyncReport:
    """What one sync did, account by account, and the aggregator's messages."""

    accounts: list[AccountSync]
    messages: list[str]


def _apply(
    session: Session, account_id: int, account: ProviderAccount, since: date, complete: bool
) -> AccountSync:
    """Apply one account's feed. Holds no longer listed are removed only from a complete answer."""
    removed = []
    if complete:
        delivered = {item.feed_id for item in account.transactions}
        removed = [
            feed_id
            for feed_id in list_pending_feed_ids(session, account_id, since)
            if feed_id not in delivered
        ]
    feed = AccountFeed(
        list(account.transactions), removed, account.balance_cents, account.balance_date
    )
    try:
        pull = apply_feed(session, account_id, feed)
    except FeedError as error:
        return AccountSync(account.provider_account_id, account_id, None, str(error))
    return AccountSync(account.provider_account_id, account_id, pull, None)


def run_sync(
    session: Session,
    access_url: str,
    *,
    today: date,
    transport: Transport,
    days: int = SYNC_DAYS,
    link: str = DEFAULT_LINK,
) -> SyncReport:
    """Fetch the last days of every account and apply each one mapped under the link.

    The caller commits.
    """
    since = today - timedelta(days=days)
    answer = fetch_accounts(access_url, since, today, transport)
    mappings = list_feed_accounts(session, link)
    by_provider = {mapping.provider_account_id: mapping for mapping in mappings}
    results = []
    for account in answer.accounts:
        mapping = by_provider.get(account.provider_account_id)
        if mapping is None:
            results.append(AccountSync(account.provider_account_id, None, None, "not mapped"))
        elif account.currency != "USD":
            results.append(
                AccountSync(
                    account.provider_account_id, mapping.account_id, None, "currency is not USD"
                )
            )
        else:
            complete = not answer.messages
            results.append(_apply(session, mapping.account_id, account, since, complete))
    delivered = {account.provider_account_id for account in answer.accounts}
    results += [
        AccountSync(
            mapping.provider_account_id,
            mapping.account_id,
            None,
            "not in the aggregator's answer",
        )
        for mapping in mappings
        if mapping.provider_account_id not in delivered
    ]
    return SyncReport(results, answer.messages)
