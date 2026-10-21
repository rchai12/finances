"""Domain models. This module imports nothing from the rest of the project."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class AccountType(StrEnum):
    """Kind of bank or card account."""

    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    OTHER = "other"


@dataclass(frozen=True)
class Account:
    """One bank or card account, as stored."""

    id: int
    name: str
    institution: str
    type: AccountType
    currency: str
    last4: str | None
    is_active: bool
    created_at: datetime


def validate_last4(last4: str | None) -> str | None:
    """Return last4 unchanged if it is None or exactly four ASCII digits; otherwise raise."""
    if last4 is None:
        return None

    if not re.fullmatch(r"[0-9]{4}", last4):
        raise ValueError("last4 must be exactly 4 digits")

    return last4


def validate_currency(currency: str) -> str:
    """Return currency unchanged if it is exactly three ASCII capital letters; otherwise raise."""
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency must be three capital letters")
    return currency


def validate_provider_account_id(text: str) -> str:
    """Return an aggregator account id without outer spaces, or raise when it cannot be used."""
    clean = text.strip()
    if not 1 <= len(clean) <= 200:
        raise ValueError("feed account id must be 1 to 200 characters")
    return clean


class DataSource(StrEnum):
    """Where a stored transaction or balance came from."""

    STATEMENT = "statement"
    AGGREGATOR = "aggregator"


@dataclass(frozen=True)
class Statement:
    """One imported statement file, as stored."""

    id: int
    account_id: int
    source_filename: str
    file_sha256: str
    parser_name: str
    period_start: date
    period_end: date
    opening_balance_cents: int
    closing_balance_cents: int
    lines_parsed: int
    rows_inserted: int
    rows_duplicate: int
    imported_at: datetime


@dataclass(frozen=True)
class NewTransaction:
    """A transaction about to be stored. Amounts are from the account holder's side."""

    account_id: int
    statement_id: int | None
    posted_date: date
    transaction_date: date | None
    amount_cents: int
    description: str
    section: str | None
    card_last4: str | None
    cardholder: str | None
    external_id: str | None
    source: DataSource
    is_pending: bool
    fingerprint: str


@dataclass(frozen=True)
class Transaction:
    """One transaction, as stored."""

    id: int
    account_id: int
    statement_id: int | None
    posted_date: date
    transaction_date: date | None
    amount_cents: int
    description: str
    section: str | None
    card_last4: str | None
    cardholder: str | None
    external_id: str | None
    source: DataSource
    is_pending: bool
    fingerprint: str
    created_at: datetime


@dataclass(frozen=True)
class BalanceSnapshot:
    """An account balance as of one date, as stored."""

    id: int
    account_id: int
    as_of_date: date
    balance_cents: int
    source: DataSource
    created_at: datetime


@dataclass(frozen=True)
class FeedPull:
    """What applying one aggregator feed did to one account, as stored."""

    id: int
    account_id: int
    inserted: int
    updated: int
    removed: int
    unchanged: int
    feed_total_cents: int
    balance_cents: int | None
    balance_date: date | None
    drift_cents: int | None
    pulled_at: datetime


DEFAULT_LINK = "default"


@dataclass(frozen=True)
class FeedAccount:
    """Which aggregator account feeds one of our accounts, and under which link."""

    id: int
    account_id: int
    provider_account_id: str
    link: str = DEFAULT_LINK


@dataclass(frozen=True)
class SeenFeedAccount:
    """An aggregator account a sync has delivered under a link, mapped or not."""

    id: int
    link: str
    provider_account_id: str
    name: str
    institution: str
    first_seen: date
    last_seen: date
    ignored: bool


@dataclass(frozen=True)
class Person:
    """One person in the household."""

    id: int
    name: str


MANUAL = "manual"
BY_RULE = "rule"


@dataclass(frozen=True)
class Category:
    """A group of the category tree (group_id None), or a category inside one."""

    id: int
    name: str
    group_id: int | None
    is_transfer: bool
    is_income: bool
    is_sensitive: bool


@dataclass(frozen=True)
class CategoryRule:
    """A merchant pattern that puts transactions in a category."""

    id: int
    pattern: str
    match: str
    priority: int
    category_id: int


@dataclass(frozen=True)
class CategoryAssignment:
    """A transaction's category, set by hand or by a rule."""

    transaction_id: int
    category_id: int
    source: str
    rule_id: int | None


AUTO = "auto"
CONFIRMED = "confirmed"


@dataclass(frozen=True)
class TransferPair:
    """An outflow and an inflow of the same money between two of the household's accounts."""

    id: int
    out_transaction_id: int
    in_transaction_id: int
    status: str


@dataclass(frozen=True)
class Budget:
    """A monthly target for a category or a group."""

    id: int
    category_id: int
    amount_cents: int


@dataclass(frozen=True)
class SyncFailure:
    """The last failed sync of one SimpleFIN link, cleared by a good one."""

    link: str
    failed_at: datetime
    message: str
