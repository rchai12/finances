"""What one aggregator pull delivers for one account, before any provider is chosen."""

import hashlib
from dataclasses import dataclass, field
from datetime import date


class FeedError(Exception):
    """Raised when a feed cannot be applied. Nothing is written."""


@dataclass(frozen=True)
class FeedTransaction:
    """One transaction as the feed reports it. Amounts are from the account holder's side."""

    feed_id: str
    posted_date: date
    amount_cents: int
    description: str
    is_pending: bool = False
    transaction_date: date | None = None
    card_last4: str | None = None
    replaces_feed_id: str | None = None


@dataclass(frozen=True)
class AccountFeed:
    """Everything one pull delivers for one account."""

    transactions: list[FeedTransaction] = field(default_factory=list)
    removed_feed_ids: list[str] = field(default_factory=list)
    balance_cents: int | None = None
    balance_date: date | None = None


def feed_fingerprint(account_id: int, feed_id: str) -> str:
    """Return the fingerprint stored for a transaction that came from the feed."""
    return hashlib.sha256(f"feed\n{account_id}\n{feed_id}".encode()).hexdigest()
