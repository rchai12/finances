"""One sync: fetch every account from SimpleFIN and apply each mapped one."""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.repositories import (
    clear_sync_failure,
    list_feed_accounts,
    list_pending_feed_ids,
    record_seen_feed_account,
    record_sync_failure,
)
from finances.domain.models import DEFAULT_LINK, FeedPull
from finances.sync.feed import AccountFeed, FeedError
from finances.sync.links import load_access_url
from finances.sync.service import apply_feed
from finances.sync.simplefin import (
    AggregatorUnreachable,
    ProviderAccount,
    SyncError,
    Transport,
    fetch_accounts,
)

SYNC_DAYS = 30
KEYCHAIN_FAILED = "keychain"
NOT_SET_UP = "not set up"
AGGREGATOR_FAILED = "aggregator"
RETRY_WAITS = (30, 60, 120)


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
    """Fetch the last days of every account, remember each, and apply those mapped under the link.

    The caller commits.
    """
    since = today - timedelta(days=days)
    answer = fetch_accounts(access_url, since, today, transport)
    for account in answer.accounts:
        record_seen_feed_account(
            session, link, account.provider_account_id, account.name, account.institution, today
        )
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


@dataclass(frozen=True)
class LinkRun:
    """What one link's sync did, or why it could not run."""

    link: str
    report: SyncReport | None
    error: str | None
    failure: str | None = field(default=None, compare=False)
    cause: str | None = field(default=None, compare=False)


def _stamp(now: Callable[[], datetime] | None) -> datetime:
    return datetime.now(UTC) if now is None else now()


def _remember(engine: Engine, run: LinkRun, now: Callable[[], datetime] | None) -> None:
    with session_scope(engine) as session:
        if run.failure in (AGGREGATOR_FAILED, KEYCHAIN_FAILED):
            record_sync_failure(session, run.link, _stamp(now), run.cause or "")
        elif run.report is not None:
            clear_sync_failure(session, run.link)


def run_links(
    engine: Engine,
    links: list[str],
    *,
    today: date,
    transport: Transport,
    days: int = SYNC_DAYS,
    retry_waits: Sequence[int] = (),
    sleep: Callable[[float], None] | None = None,
    on_retry: Callable[[str, int], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> list[LinkRun]:
    """Sync each link in its own committed session. One link failing never stops the next."""
    runs = []
    for link in links:
        try:
            access_url = load_access_url(link)
        except SyncError as error:
            run = LinkRun(link, None, f"link {link}: {error}", KEYCHAIN_FAILED, str(error))
            runs.append(run)
            _remember(engine, run, now)
            continue
        if access_url is None:
            run = LinkRun(link, None, f"link {link} is not set up", NOT_SET_UP)
            runs.append(run)
            _remember(engine, run, now)
            continue
        waits = list(retry_waits)
        while True:
            try:
                with session_scope(engine) as session:
                    report = run_sync(
                        session, access_url, today=today, transport=transport, days=days, link=link
                    )
            except AggregatorUnreachable as error:
                if not waits:
                    run = LinkRun(
                        link, None, f"link {link}: {error}", AGGREGATOR_FAILED, str(error)
                    )
                    runs.append(run)
                    _remember(engine, run, now)
                    break
                seconds = waits.pop(0)
                if on_retry is not None:
                    on_retry(link, seconds)
                if sleep is None:
                    time.sleep(seconds)
                else:
                    sleep(seconds)
            except SyncError as error:
                run = LinkRun(link, None, f"link {link}: {error}", AGGREGATOR_FAILED, str(error))
                runs.append(run)
                _remember(engine, run, now)
                break
            else:
                run = LinkRun(link, report, None)
                runs.append(run)
                _remember(engine, run, now)
                break
    return runs
