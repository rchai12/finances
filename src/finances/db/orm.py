"""SQLAlchemy ORM tables. From this project, this module imports only the domain."""

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

from finances.domain.audit import Change
from finances.domain.models import (
    DEFAULT_LINK,
    Account,
    AccountType,
    BalanceSnapshot,
    Budget,
    Category,
    CategoryAssignment,
    CategoryRule,
    DataSource,
    FeedAccount,
    FeedPull,
    Person,
    SeenFeedAccount,
    Statement,
    SyncFailure,
    Transaction,
    TransferPair,
)
from finances.domain.proposals import Advice, Proposal
from finances.domain.text import (
    ADVICE_TEXT_LIMIT,
    AUDIT_TEXT_LIMIT,
    CATEGORY_NAME_LIMIT,
    DESCRIPTION_LIMIT,
    FEED_ID_LIMIT,
    NAME_LIMIT,
    PROPOSAL_TEXT_LIMIT,
    PROVIDER_ACCOUNT_ID_LIMIT,
    RULE_PATTERN_LIMIT,
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
    name: Mapped[str] = mapped_column(String(NAME_LIMIT), nullable=False, unique=True)
    institution: Mapped[str] = mapped_column(String(NAME_LIMIT), nullable=False)
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
    description: Mapped[str] = mapped_column(String(DESCRIPTION_LIMIT), nullable=False)
    section: Mapped[str | None] = mapped_column(String(30), nullable=True)
    card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    cardholder: Mapped[str | None] = mapped_column(String(NAME_LIMIT), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(NAME_LIMIT), nullable=True)
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
    feed_id: Mapped[str] = mapped_column(String(FEED_ID_LIMIT), nullable=False)
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
    provider_account_id: Mapped[str] = mapped_column(
        String(PROVIDER_ACCOUNT_ID_LIMIT), nullable=False
    )
    link: Mapped[str] = mapped_column(String(50), nullable=False, default=DEFAULT_LINK)


def to_feed_account(row: FeedAccountRow) -> FeedAccount:
    """Return the domain FeedAccount for a row of the feed_accounts table."""
    return FeedAccount(
        id=row.id,
        account_id=row.account_id,
        provider_account_id=row.provider_account_id,
        link=row.link,
    )


class FeedSeenAccountRow(Base):
    """One row of the feed_seen_accounts table: an aggregator account a sync has delivered."""

    __tablename__ = "feed_seen_accounts"
    __table_args__ = (
        UniqueConstraint(
            "link", "provider_account_id", name="uq_feed_seen_accounts_link_provider_account"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    link: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(
        String(PROVIDER_ACCOUNT_ID_LIMIT), nullable=False
    )
    name: Mapped[str] = mapped_column(String(NAME_LIMIT), nullable=False)
    institution: Mapped[str] = mapped_column(String(NAME_LIMIT), nullable=False)
    first_seen: Mapped[date] = mapped_column(Date, nullable=False)
    last_seen: Mapped[date] = mapped_column(Date, nullable=False)
    ignored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


def to_seen_feed_account(row: FeedSeenAccountRow) -> SeenFeedAccount:
    """Return the domain SeenFeedAccount for a row of the feed_seen_accounts table."""
    return SeenFeedAccount(
        id=row.id,
        link=row.link,
        provider_account_id=row.provider_account_id,
        name=row.name,
        institution=row.institution,
        first_seen=row.first_seen,
        last_seen=row.last_seen,
        ignored=row.ignored,
    )


class PersonRow(Base):
    """One row of the people table."""

    __tablename__ = "people"
    __table_args__ = (UniqueConstraint("name", name="uq_people_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(NAME_LIMIT), nullable=False)


class AccountOwnerRow(Base):
    """One row of the account_owners table. A null person_id means the account is Joint."""

    __tablename__ = "account_owners"
    __table_args__ = (UniqueConstraint("account_id", name="uq_account_owners_account_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True)


class CardholderAliasRow(Base):
    """One row of the cardholder_aliases table: a normalized cardholder name and its person."""

    __tablename__ = "cardholder_aliases"
    __table_args__ = (UniqueConstraint("cardholder", name="uq_cardholder_aliases_cardholder"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cardholder: Mapped[str] = mapped_column(String(NAME_LIMIT), nullable=False)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False)


def to_person(row: PersonRow) -> Person:
    """Return the domain Person for a row of the people table."""
    return Person(id=row.id, name=row.name)


class CategoryRow(Base):
    """One row of the categories table: a group when parent_id is null, else a category."""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", name="uq_categories_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(CATEGORY_NAME_LIMIT), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    is_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_income: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False)


class CategoryRuleRow(Base):
    """One row of the category_rules table."""

    __tablename__ = "category_rules"
    __table_args__ = (UniqueConstraint("match", "pattern", name="uq_category_rules_match_pattern"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern: Mapped[str] = mapped_column(String(RULE_PATTERN_LIMIT), nullable=False)
    match: Mapped[str] = mapped_column(String(12), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)


class TransactionCategoryRow(Base):
    """One row of the transaction_categories table: a transaction's one category."""

    __tablename__ = "transaction_categories"
    __table_args__ = (
        UniqueConstraint("transaction_id", name="uq_transaction_categories_transaction_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("category_rules.id"), nullable=True)


def to_category(row: CategoryRow) -> Category:
    """Return the domain Category for a row of the categories table."""
    return Category(
        id=row.id,
        name=row.name,
        group_id=row.parent_id,
        is_transfer=row.is_transfer,
        is_income=row.is_income,
        is_sensitive=row.is_sensitive,
    )


def to_category_rule(row: CategoryRuleRow) -> CategoryRule:
    """Return the domain CategoryRule for a row of the category_rules table."""
    return CategoryRule(
        id=row.id,
        pattern=row.pattern,
        match=row.match,
        priority=row.priority,
        category_id=row.category_id,
    )


def to_category_assignment(row: TransactionCategoryRow) -> CategoryAssignment:
    """Return the domain CategoryAssignment for a row of the transaction_categories table."""
    return CategoryAssignment(
        transaction_id=row.transaction_id,
        category_id=row.category_id,
        source=row.source,
        rule_id=row.rule_id,
    )


class TransferPairRow(Base):
    """One row of the transfer_pairs table: an outflow and an inflow that are one transfer."""

    __tablename__ = "transfer_pairs"
    __table_args__ = (
        UniqueConstraint("out_transaction_id", name="uq_transfer_pairs_out_transaction_id"),
        UniqueConstraint("in_transaction_id", name="uq_transfer_pairs_in_transaction_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    out_transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    in_transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)


class TransferRejectionRow(Base):
    """One row of the transfer_rejections table: two transactions that are not a transfer."""

    __tablename__ = "transfer_rejections"
    __table_args__ = (
        UniqueConstraint(
            "out_transaction_id", "in_transaction_id", name="uq_transfer_rejections_pair"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    out_transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    in_transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False)


def to_transfer_pair(row: TransferPairRow) -> TransferPair:
    """Return the domain TransferPair for a row of the transfer_pairs table."""
    return TransferPair(
        id=row.id,
        out_transaction_id=row.out_transaction_id,
        in_transaction_id=row.in_transaction_id,
        status=row.status,
    )


class BudgetRow(Base):
    """One row of the budgets table: a monthly target for a category or a group."""

    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("category_id", name="uq_budgets_category_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)


def to_budget(row: BudgetRow) -> Budget:
    """Return the domain Budget for a row of the budgets table."""
    return Budget(id=row.id, category_id=row.category_id, amount_cents=row.amount_cents)


class SyncFailureRow(Base):
    """One row of the sync_failures table: the last failed sync of a SimpleFIN link."""

    __tablename__ = "sync_failures"
    __table_args__ = (UniqueConstraint("link", name="uq_sync_failures_link"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    link: Mapped[str] = mapped_column(String(30), nullable=False)
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    message: Mapped[str] = mapped_column(String(PROVIDER_ACCOUNT_ID_LIMIT), nullable=False)


def to_sync_failure(row: SyncFailureRow) -> SyncFailure:
    """Return the domain SyncFailure for a row of the sync_failures table."""
    return SyncFailure(link=row.link, failed_at=_as_utc(row.failed_at), message=row.message)


class AuditRow(Base):
    """One row of the audit_log table: a change a person made, never edited."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    who: Mapped[str] = mapped_column(String(10), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    before: Mapped[str | None] = mapped_column(String(AUDIT_TEXT_LIMIT), nullable=True)
    after: Mapped[str | None] = mapped_column(String(AUDIT_TEXT_LIMIT), nullable=True)


def to_change(row: AuditRow) -> Change:
    """Return the domain Change for a row of the audit_log table."""
    return Change(
        id=row.id,
        at=_as_utc(row.at),
        who=row.who,
        action=row.action,
        kind=row.kind,
        record_id=row.record_id,
        before=row.before,
        after=row.after,
    )


class ProposalRow(Base):
    """One row of the proposals table: a suggestion waiting for a person."""

    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[str] = mapped_column(String(PROPOSAL_TEXT_LIMIT), nullable=False)
    reason: Mapped[str] = mapped_column(String(PROPOSAL_TEXT_LIMIT), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    other_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


def to_proposal(row: ProposalRow) -> Proposal:
    """Return the domain Proposal for a row of the proposals table."""
    return Proposal(
        id=row.id,
        kind=row.kind,
        target_id=row.target_id,
        value=row.value,
        reason=row.reason,
        status=row.status,
        created_at=_as_utc(row.created_at),
        decided_at=None if row.decided_at is None else _as_utc(row.decided_at),
        other_id=row.other_id,
    )


class AdviceRow(Base):
    """One row of the advice_log table: a note the agent kept."""

    __tablename__ = "advice_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    subject: Mapped[str] = mapped_column(String(NAME_LIMIT), nullable=False)
    text: Mapped[str] = mapped_column(String(ADVICE_TEXT_LIMIT), nullable=False)


def to_advice(row: AdviceRow) -> Advice:
    """Return the domain Advice for a row of the advice_log table."""
    return Advice(
        id=row.id,
        created_at=_as_utc(row.created_at),
        subject=row.subject,
        text=row.text,
    )
