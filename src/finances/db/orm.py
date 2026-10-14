"""SQLAlchemy ORM tables. From this project, this module imports only the domain models."""

from datetime import UTC, date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from finances.domain.models import (
    DEFAULT_LINK,
    Account,
    AccountType,
    BalanceSnapshot,
    DataSource,
    FeedAccount,
    FeedPull,
    Statement,
    Transaction,
)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class of every ORM table."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class AccountRow(Base):
    """One row of the accounts table."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    institution: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


def to_account(row: AccountRow) -> Account:
    """Return the domain Account for a row of the accounts table."""
    if row.created_at.tzinfo is None:
        created_at = row.created_at.replace(tzinfo=UTC)
    else:
        created_at = row.created_at

    return Account(
        id=row.id,
        name=row.name,
        institution=row.institution,
        type=AccountType(row.type),
        currency=row.currency,
        last4=row.last4,
        is_active=row.is_active,
        created_at=created_at,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class StatementRow(Base):
    """One row of the statements table."""

    __tablename__ = "statements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    parser_name: Mapped[str] = mapped_column(String(50), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    opening_balance_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    closing_balance_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lines_parsed: Mapped[int] = mapped_column(Integer, nullable=False)
    rows_inserted: Mapped[int] = mapped_column(Integer, nullable=False)
    rows_duplicate: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class TransactionRow(Base):
    """One row of the transactions table."""

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "fingerprint", name="uq_transactions_account_fingerprint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    statement_id: Mapped[int | None] = mapped_column(ForeignKey("statements.id"), nullable=True)
    posted_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    section: Mapped[str | None] = mapped_column(String(30), nullable=True)
    card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    cardholder: Mapped[str | None] = mapped_column(String(100), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    is_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class BalanceSnapshotRow(Base):
    """One row of the balance_snapshots table."""

    __tablename__ = "balance_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "as_of_date",
            "source",
            name="uq_balance_snapshots_account_date_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    balance_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


def to_statement(row: StatementRow) -> Statement:
    """Return the domain Statement for a row of the statements table."""
    return Statement(
        id=row.id,
        account_id=row.account_id,
        source_filename=row.source_filename,
        file_sha256=row.file_sha256,
        parser_name=row.parser_name,
        period_start=row.period_start,
        period_end=row.period_end,
        opening_balance_cents=row.opening_balance_cents,
        closing_balance_cents=row.closing_balance_cents,
        lines_parsed=row.lines_parsed,
        rows_inserted=row.rows_inserted,
        rows_duplicate=row.rows_duplicate,
        imported_at=_as_utc(row.imported_at),
    )


def to_transaction(row: TransactionRow) -> Transaction:
    """Return the domain Transaction for a row of the transactions table."""
    return Transaction(
        id=row.id,
        account_id=row.account_id,
        statement_id=row.statement_id,
        posted_date=row.posted_date,
        transaction_date=row.transaction_date,
        amount_cents=row.amount_cents,
        description=row.description,
        section=row.section,
        card_last4=row.card_last4,
        cardholder=row.cardholder,
        external_id=row.external_id,
        source=DataSource(row.source),
        is_pending=row.is_pending,
        fingerprint=row.fingerprint,
        created_at=_as_utc(row.created_at),
    )


def to_balance_snapshot(row: BalanceSnapshotRow) -> BalanceSnapshot:
    """Return the domain BalanceSnapshot for a row of the balance_snapshots table."""
    return BalanceSnapshot(
        id=row.id,
        account_id=row.account_id,
        as_of_date=row.as_of_date,
        balance_cents=row.balance_cents,
        source=DataSource(row.source),
        created_at=_as_utc(row.created_at),
    )


class FeedItemRow(Base):
    """One row of the feed_items table: which feed transaction a stored transaction came from."""

    __tablename__ = "feed_items"
    __table_args__ = (
        UniqueConstraint("account_id", "feed_id", name="uq_feed_items_account_feed"),
        UniqueConstraint("transaction_id", name="uq_feed_items_transaction_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    feed_id: Mapped[str] = mapped_column(String(100), nullable=False)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)


class FeedPullRow(Base):
    """One row of the feed_pulls table."""

    __tablename__ = "feed_pulls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    inserted: Mapped[int] = mapped_column(Integer, nullable=False)
    updated: Mapped[int] = mapped_column(Integer, nullable=False)
    removed: Mapped[int] = mapped_column(Integer, nullable=False)
    unchanged: Mapped[int] = mapped_column(Integer, nullable=False)
    feed_total_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    balance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    drift_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pulled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


def to_feed_pull(row: FeedPullRow) -> FeedPull:
    """Return the domain FeedPull for a row of the feed_pulls table."""
    return FeedPull(
        id=row.id,
        account_id=row.account_id,
        inserted=row.inserted,
        updated=row.updated,
        removed=row.removed,
        unchanged=row.unchanged,
        feed_total_cents=row.feed_total_cents,
        balance_cents=row.balance_cents,
        balance_date=row.balance_date,
        drift_cents=row.drift_cents,
        pulled_at=_as_utc(row.pulled_at),
    )


class FeedAccountRow(Base):
    """One row of the feed_accounts table: which aggregator account feeds one of ours."""

    __tablename__ = "feed_accounts"
    __table_args__ = (
        UniqueConstraint("account_id", name="uq_feed_accounts_account_id"),
        UniqueConstraint(
            "link", "provider_account_id", name="uq_feed_accounts_link_provider_account"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(200), nullable=False)
    link: Mapped[str] = mapped_column(String(50), nullable=False, default=DEFAULT_LINK)


def to_feed_account(row: FeedAccountRow) -> FeedAccount:
    """Return the domain FeedAccount for a row of the feed_accounts table."""
    return FeedAccount(
        id=row.id,
        account_id=row.account_id,
        provider_account_id=row.provider_account_id,
        link=row.link,
    )
