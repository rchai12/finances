"""Database reads and writes. Functions take a Session and return domain objects."""

from collections.abc import Iterable
from datetime import date

from sqlalchemy import ColumnElement, delete, exists, func, or_, select
from sqlalchemy.orm import Session

from finances.db.orm import (
    AccountOwnerRow,
    AccountRow,
    BalanceSnapshotRow,
    CardholderAliasRow,
    CategoryRow,
    CategoryRuleRow,
    FeedAccountRow,
    FeedItemRow,
    FeedPullRow,
    FeedSeenAccountRow,
    PersonRow,
    StatementRow,
    TransactionCategoryRow,
    TransactionRow,
    TransferPairRow,
    TransferRejectionRow,
    to_account,
    to_balance_snapshot,
    to_category,
    to_category_assignment,
    to_category_rule,
    to_feed_account,
    to_feed_pull,
    to_person,
    to_seen_feed_account,
    to_statement,
    to_transaction,
    to_transfer_pair,
)
from finances.domain.models import (
    AUTO,
    BY_RULE,
    CONFIRMED,
    DEFAULT_LINK,
    MANUAL,
    Account,
    AccountType,
    BalanceSnapshot,
    Category,
    CategoryAssignment,
    CategoryRule,
    DataSource,
    FeedAccount,
    FeedPull,
    NewTransaction,
    Person,
    SeenFeedAccount,
    Statement,
    Transaction,
    TransferPair,
    validate_currency,
    validate_last4,
    validate_provider_account_id,
)
from finances.domain.people import JOINT, normalize_cardholder, validate_person_name
from finances.domain.rules import MATCHES, normalize_pattern
from finances.domain.text import CATEGORY_NAME_LIMIT, NAME_LIMIT, RULE_PATTERN_LIMIT, fit
from finances.domain.transfers import Movement

_FINGERPRINT_CHUNK = 500
_ACCOUNT_TYPES = tuple(item.value for item in AccountType)


class AccountExistsError(Exception):
    """Raised when an account with the same name already exists."""


def get_account_by_name(session: Session, name: str) -> Account | None:
    """Return the account with this name, ignoring case and outer spaces, or None."""
    # Remove outer spaces and convert to lowercase for comparison
    clean_name = name.strip().lower()

    # Query for accounts where the cleaned name matches
    stmt = select(AccountRow).where(func.lower(AccountRow.name) == clean_name)
    row = session.scalars(stmt).first()

    return to_account(row) if row is not None else None


def create_account(
    session: Session,
    name: str,
    institution: str,
    account_type: AccountType | str,
    currency: str = "USD",
    last4: str | None = None,
) -> Account:
    """Add an account and return it. The caller commits."""
    if account_type not in _ACCOUNT_TYPES:
        raise ValueError(f"type must be one of: {', '.join(_ACCOUNT_TYPES)}")

    # Clean the name and institution by removing outer spaces
    clean_name = name.strip()
    clean_institution = institution.strip()

    # Validate that name and institution are not empty after cleaning
    if not clean_name:
        raise ValueError("account name must not be empty")
    if not clean_institution:
        raise ValueError("institution must not be empty")
    if len(clean_name) > NAME_LIMIT:
        raise ValueError(f"account name must be at most {NAME_LIMIT} characters")
    if len(clean_institution) > NAME_LIMIT:
        raise ValueError(f"institution must be at most {NAME_LIMIT} characters")

    # Check if an account with this name already exists (case-insensitive comparison)
    stmt = select(AccountRow).where(func.lower(AccountRow.name) == clean_name.lower())
    existing_account = session.scalars(stmt).first()

    if existing_account is not None:
        raise AccountExistsError("an account with this name already exists")

    # Validate last4 if provided
    if last4 is not None:
        validate_last4(last4)

    type_value = AccountType(account_type).value
    validate_currency(currency)

    # Create new account row
    row = AccountRow(
        name=clean_name,
        institution=clean_institution,
        type=type_value,
        currency=currency,
        last4=last4,
    )

    # Add the row to session and flush to get the ID
    session.add(row)
    session.flush()

    # Return the Account domain object
    return to_account(row)


def find_accounts_by_last4(session: Session, last4: str) -> list[Account]:
    """Return the accounts with these last four digits, active or not, in id order."""
    # Validate the last4 parameter first
    validate_last4(last4)

    # Query for accounts with matching last4, ordered by id
    stmt = select(AccountRow).where(AccountRow.last4 == last4).order_by(AccountRow.id)
    rows = session.scalars(stmt).all()

    # Convert to Account objects
    return [to_account(row) for row in rows]


def list_accounts(session: Session, include_inactive: bool = False) -> list[Account]:
    """Return the accounts sorted by name, leaving out inactive ones unless asked."""
    # Build base query
    stmt = select(AccountRow)

    # Filter by active status if needed
    if not include_inactive:
        stmt = stmt.where(AccountRow.is_active.is_(True))

    # Order by name (case-insensitive) and return all
    stmt = stmt.order_by(func.lower(AccountRow.name))
    rows = session.scalars(stmt).all()

    # Convert to Account objects
    return [to_account(row) for row in rows]


def account_names(session: Session) -> dict[int, str]:
    """Map the id of every account, closed included, to its name."""
    return {account.id: account.name for account in list_accounts(session, include_inactive=True)}


def create_statement(
    session: Session,
    *,
    account_id: int,
    source_filename: str,
    file_sha256: str,
    parser_name: str,
    period_start: date,
    period_end: date,
    opening_balance_cents: int,
    closing_balance_cents: int,
    lines_parsed: int,
    rows_inserted: int,
    rows_duplicate: int,
) -> Statement:
    """Add one statement record and return it. The caller commits."""
    row = StatementRow(
        account_id=account_id,
        source_filename=source_filename,
        file_sha256=file_sha256,
        parser_name=parser_name,
        period_start=period_start,
        period_end=period_end,
        opening_balance_cents=opening_balance_cents,
        closing_balance_cents=closing_balance_cents,
        lines_parsed=lines_parsed,
        rows_inserted=rows_inserted,
        rows_duplicate=rows_duplicate,
    )
    session.add(row)
    session.flush()
    return to_statement(row)


def find_statement_by_hash(session: Session, file_sha256: str) -> Statement | None:
    """Return the statement with this file hash, or None."""
    stmt = select(StatementRow).where(StatementRow.file_sha256 == file_sha256)
    row = session.scalars(stmt).first()
    return to_statement(row) if row is not None else None


def list_statements(session: Session, account_id: int | None = None) -> list[Statement]:
    """Return statements, latest period first and highest id when periods match."""
    stmt = select(StatementRow)
    if account_id is not None:
        stmt = stmt.where(StatementRow.account_id == account_id)
    stmt = stmt.order_by(StatementRow.period_end.desc(), StatementRow.id.desc())
    return [to_statement(row) for row in session.scalars(stmt).all()]


def existing_fingerprints(
    session: Session, account_id: int, fingerprints: Iterable[str]
) -> set[str]:
    """Return which of these fingerprints already belong to a transaction of this account."""
    pending = list(fingerprints)
    found: set[str] = set()
    for start in range(0, len(pending), _FINGERPRINT_CHUNK):
        chunk = pending[start : start + _FINGERPRINT_CHUNK]
        stmt = select(TransactionRow.fingerprint).where(
            TransactionRow.account_id == account_id,
            TransactionRow.fingerprint.in_(chunk),
        )
        found.update(session.scalars(stmt).all())
    return found


def insert_transactions(session: Session, rows: list[NewTransaction]) -> int:
    """Add one transaction per item and return how many were added. The caller commits."""
    if not rows:
        return 0
    for item in rows:
        session.add(
            TransactionRow(
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
        )
    session.flush()
    return len(rows)


def list_transactions(
    session: Session,
    account_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = 100,
) -> list[Transaction]:
    """Return transactions, latest posted date first, cut off after limit rows."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    stmt = select(TransactionRow)
    if account_id is not None:
        stmt = stmt.where(TransactionRow.account_id == account_id)
    if start is not None:
        stmt = stmt.where(TransactionRow.posted_date >= start)
    if end is not None:
        stmt = stmt.where(TransactionRow.posted_date <= end)
    stmt = stmt.order_by(TransactionRow.posted_date.desc(), TransactionRow.id.desc()).limit(limit)
    return [to_transaction(row) for row in session.scalars(stmt).all()]


def add_balance_snapshot(
    session: Session, account_id: int, as_of_date: date, balance_cents: int, source: DataSource
) -> BalanceSnapshot:
    """Record a balance, or return the one already stored for that account, date, and source."""
    stmt = select(BalanceSnapshotRow).where(
        BalanceSnapshotRow.account_id == account_id,
        BalanceSnapshotRow.as_of_date == as_of_date,
        BalanceSnapshotRow.source == source.value,
    )
    row = session.scalars(stmt).first()
    if row is not None:
        return to_balance_snapshot(row)
    row = BalanceSnapshotRow(
        account_id=account_id,
        as_of_date=as_of_date,
        balance_cents=balance_cents,
        source=source.value,
    )
    session.add(row)
    session.flush()
    return to_balance_snapshot(row)


def latest_balance(session: Session, account_id: int) -> BalanceSnapshot | None:
    """Return the account's newest snapshot, or None when it has none."""
    stmt = (
        select(BalanceSnapshotRow)
        .where(BalanceSnapshotRow.account_id == account_id)
        .order_by(BalanceSnapshotRow.as_of_date.desc(), BalanceSnapshotRow.id.desc())
        .limit(1)
    )
    row = session.scalars(stmt).first()
    return to_balance_snapshot(row) if row is not None else None


def get_account(session: Session, account_id: int) -> Account | None:
    """Return the account with this id, or None."""
    row = session.get(AccountRow, account_id)
    return to_account(row) if row is not None else None


def set_balance_snapshot(
    session: Session, account_id: int, as_of_date: date, balance_cents: int, source: DataSource
) -> BalanceSnapshot:
    """Record a balance, replacing the one already stored for that account, date, and source."""
    stmt = select(BalanceSnapshotRow).where(
        BalanceSnapshotRow.account_id == account_id,
        BalanceSnapshotRow.as_of_date == as_of_date,
        BalanceSnapshotRow.source == source.value,
    )
    row = session.scalars(stmt).first()
    if row is None:
        row = BalanceSnapshotRow(account_id=account_id, as_of_date=as_of_date, source=source.value)
        session.add(row)
    row.balance_cents = balance_cents
    session.flush()
    return to_balance_snapshot(row)


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


def statement_periods(session: Session, account_id: int) -> list[tuple[date, date]]:
    """Return the first and last day of each of the account's stored statements."""
    return [(item.period_start, item.period_end) for item in list_statements(session, account_id)]


def statement_covers(session: Session, account_id: int, day: date) -> bool:
    """Return whether a stored statement of the account has day inside its period."""
    stmt = (
        select(StatementRow.id)
        .where(
            StatementRow.account_id == account_id,
            StatementRow.period_start <= day,
            StatementRow.period_end >= day,
        )
        .limit(1)
    )
    return session.scalars(stmt).first() is not None


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


class PersonExistsError(Exception):
    """Raised when a person with the same name already exists."""


def create_person(session: Session, name: str) -> Person:
    """Add a person and return it. The caller commits."""
    clean = validate_person_name(name)
    if get_person_by_name(session, clean) is not None:
        raise PersonExistsError("a person with this name already exists")
    row = PersonRow(name=clean)
    session.add(row)
    session.flush()
    return to_person(row)


def get_person_by_name(session: Session, name: str) -> Person | None:
    """Return the person with this name, ignoring case and outer spaces, or None."""
    stmt = select(PersonRow).where(func.lower(PersonRow.name) == name.strip().lower())
    row = session.scalars(stmt).first()
    return to_person(row) if row is not None else None


def resolve_owner(session: Session, owner: str) -> Person | None:
    """Return the person an owner field names, or None for Joint. Raise when there is none."""
    if owner.strip().lower() == JOINT.lower():
        return None
    person = get_person_by_name(session, owner)
    if person is None:
        raise ValueError("person not found")
    return person


def list_people(session: Session) -> list[Person]:
    """Return everyone, sorted by name without regard to case, then by id."""
    stmt = select(PersonRow).order_by(func.lower(PersonRow.name), PersonRow.id)
    return [to_person(row) for row in session.scalars(stmt).all()]


def set_account_owner(session: Session, account_id: int, person_id: int | None) -> None:
    """Make the person own the account, or make it Joint when person_id is None."""
    stmt = select(AccountOwnerRow).where(AccountOwnerRow.account_id == account_id)
    row = session.scalars(stmt).first()
    if row is None:
        session.add(AccountOwnerRow(account_id=account_id, person_id=person_id))
    else:
        row.person_id = person_id
    session.flush()


def list_account_owners(session: Session) -> dict[int, int | None]:
    """Map each account with an owner row to its person's id, or None for Joint."""
    rows = session.scalars(select(AccountOwnerRow)).all()
    return {row.account_id: row.person_id for row in rows}


def set_cardholder_alias(session: Session, cardholder: str, person_id: int) -> str:
    """Tie a cardholder name to a person and return the name as stored."""
    clean = normalize_cardholder(cardholder)
    if not 1 <= len(clean) <= NAME_LIMIT:
        raise ValueError("a cardholder name must be 1 to 100 characters")
    stmt = select(CardholderAliasRow).where(CardholderAliasRow.cardholder == clean)
    row = session.scalars(stmt).first()
    if row is None:
        session.add(CardholderAliasRow(cardholder=clean, person_id=person_id))
    else:
        row.person_id = person_id
    session.flush()
    return clean


def list_cardholder_aliases(session: Session) -> dict[str, int]:
    """Map every stored cardholder name to its person's id."""
    rows = session.scalars(select(CardholderAliasRow)).all()
    return {row.cardholder: row.person_id for row in rows}


class CategoryExistsError(Exception):
    """Raised when a group or category with the same name already exists."""


def list_categories(session: Session) -> list[Category]:
    """Return every group and category, sorted by name without regard to case, then by id."""
    stmt = select(CategoryRow).order_by(func.lower(CategoryRow.name), CategoryRow.id)
    return [to_category(row) for row in session.scalars(stmt).all()]


def _category_row(session: Session, name: str) -> CategoryRow | None:
    stmt = select(CategoryRow).where(func.lower(CategoryRow.name) == name.strip().lower())
    return session.scalars(stmt).first()


def get_category_by_name(session: Session, name: str) -> Category | None:
    """Return the group or category with this name, ignoring case and outer spaces, or None."""
    row = _category_row(session, name)
    return to_category(row) if row is not None else None


def create_category(session: Session, name: str, group: str) -> Category:
    """Add a category under a group, with the group's flags, and return it. The caller commits."""
    clean = name.strip()
    if not 1 <= len(clean) <= CATEGORY_NAME_LIMIT:
        raise ValueError(f"a category name must be 1 to {CATEGORY_NAME_LIMIT} characters")
    parent = _category_row(session, group)
    if parent is None or parent.parent_id is not None:
        raise ValueError("group not found")
    if _category_row(session, clean) is not None:
        raise CategoryExistsError("a category with this name already exists")
    row = CategoryRow(
        name=clean,
        parent_id=parent.id,
        is_transfer=parent.is_transfer,
        is_income=parent.is_income,
        is_sensitive=parent.is_sensitive,
    )
    session.add(row)
    session.flush()
    return to_category(row)


def _leaf_category(session: Session, name: str) -> CategoryRow:
    """Return the category with this name, refusing a group or an unknown name."""
    row = _category_row(session, name)
    if row is None:
        raise ValueError("category not found")
    if row.parent_id is None:
        raise ValueError("rules and transactions take a category, not a group")
    return row


def list_rules(session: Session) -> list[CategoryRule]:
    """Return every rule in the order they are tried: highest priority first, then by id."""
    stmt = select(CategoryRuleRow).order_by(CategoryRuleRow.priority.desc(), CategoryRuleRow.id)
    return [to_category_rule(row) for row in session.scalars(stmt).all()]


def create_rule(
    session: Session, pattern: str, category: str, match: str = "contains", priority: int = 0
) -> CategoryRule:
    """Add a rule with its pattern normalized and return it. The caller commits."""
    clean = normalize_pattern(pattern)
    if not 1 <= len(clean) <= RULE_PATTERN_LIMIT:
        raise ValueError(f"a rule pattern must be 1 to {RULE_PATTERN_LIMIT} characters")
    if match not in MATCHES:
        raise ValueError(f"match must be one of: {', '.join(MATCHES)}")
    target = _leaf_category(session, category)
    taken = select(CategoryRuleRow).where(
        CategoryRuleRow.match == match, CategoryRuleRow.pattern == clean
    )
    if session.scalars(taken).first() is not None:
        raise ValueError("a rule with this pattern and match already exists")
    row = CategoryRuleRow(pattern=clean, match=match, priority=priority, category_id=target.id)
    session.add(row)
    session.flush()
    return to_category_rule(row)


def delete_rule(session: Session, rule_id: int) -> None:
    """Delete a rule and the assignments it set. The caller commits."""
    row = session.get(CategoryRuleRow, rule_id)
    if row is None:
        raise ValueError("rule not found")
    session.execute(delete(TransactionCategoryRow).where(TransactionCategoryRow.rule_id == rule_id))
    session.delete(row)
    session.flush()


def list_category_assignments(session: Session) -> dict[int, CategoryAssignment]:
    """Map each categorized transaction's id to its assignment."""
    rows = session.scalars(select(TransactionCategoryRow)).all()
    return {row.transaction_id: to_category_assignment(row) for row in rows}


def _assignment_row(session: Session, transaction_id: int) -> TransactionCategoryRow | None:
    stmt = select(TransactionCategoryRow).where(
        TransactionCategoryRow.transaction_id == transaction_id
    )
    return session.scalars(stmt).first()


def _assign(
    session: Session, transaction_id: int, category_id: int, source: str, rule_id: int | None
) -> None:
    row = _assignment_row(session, transaction_id)
    if row is None:
        row = TransactionCategoryRow(transaction_id=transaction_id)
        session.add(row)
    row.category_id = category_id
    row.source = source
    row.rule_id = rule_id
    session.flush()


def assign_by_rule(session: Session, transaction_id: int, rule: CategoryRule) -> None:
    """Store, or replace, the transaction's category as set by the rule. The caller commits."""
    _assign(session, transaction_id, rule.category_id, BY_RULE, rule.id)


def remove_category(session: Session, transaction_id: int) -> None:
    """Remove the transaction's category, if it has one. The caller commits."""
    row = _assignment_row(session, transaction_id)
    if row is not None:
        session.delete(row)
        session.flush()


def _require_transaction(session: Session, transaction_id: int) -> None:
    if session.get(TransactionRow, transaction_id) is None:
        raise ValueError("transaction not found")


def set_category_by_hand(session: Session, transaction_id: int, category: str) -> Category:
    """Set the transaction's category by hand, so rules leave it alone. The caller commits."""
    _require_transaction(session, transaction_id)
    target = _leaf_category(session, category)
    _assign(session, transaction_id, target.id, MANUAL, None)
    return to_category(target)


def clear_category_by_hand(session: Session, transaction_id: int) -> None:
    """Remove the transaction's category, leaving it to the rules. The caller commits."""
    _require_transaction(session, transaction_id)
    remove_category(session, transaction_id)


def list_transaction_descriptions(session: Session) -> list[tuple[int, str]]:
    """Return the id and description of every transaction, in id order."""
    stmt = select(TransactionRow.id, TransactionRow.description).order_by(TransactionRow.id)
    return [(row.id, row.description) for row in session.execute(stmt).all()]


def get_transaction(session: Session, transaction_id: int) -> Transaction | None:
    """Return the transaction with this id, or None."""
    row = session.get(TransactionRow, transaction_id)
    return to_transaction(row) if row is not None else None


def list_uncategorized(session: Session, limit: int) -> list[Transaction]:
    """Return transactions without a category, latest posted date first, at most limit."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    categorized = exists().where(TransactionCategoryRow.transaction_id == TransactionRow.id)
    paired = exists().where(_names(TransferPairRow, TransactionRow.id))
    stmt = (
        select(TransactionRow)
        .where(~categorized, ~paired)
        .order_by(TransactionRow.posted_date.desc(), TransactionRow.id.desc())
        .limit(limit)
    )
    return [to_transaction(row) for row in session.scalars(stmt).all()]


def _names(
    table: type[TransferPairRow] | type[TransferRejectionRow], transaction_id: object
) -> ColumnElement[bool]:
    """True for a pair or rejection with the transaction on either side."""
    return or_(
        table.out_transaction_id == transaction_id, table.in_transaction_id == transaction_id
    )


def list_transfer_movements(session: Session) -> list[Movement]:
    """Return each posted, non-zero transaction that is in no pair, in id order."""
    paired = exists().where(_names(TransferPairRow, TransactionRow.id))
    stmt = (
        select(
            TransactionRow.id,
            TransactionRow.account_id,
            TransactionRow.amount_cents,
            TransactionRow.posted_date,
        )
        .where(TransactionRow.is_pending.is_(False), TransactionRow.amount_cents != 0, ~paired)
        .order_by(TransactionRow.id)
    )
    return [Movement(*row) for row in session.execute(stmt).all()]


def list_transfer_rejections(session: Session) -> set[tuple[int, int]]:
    """Return the (out id, in id) of every pair said not to be a transfer."""
    stmt = select(TransferRejectionRow.out_transaction_id, TransferRejectionRow.in_transaction_id)
    return {(out_id, in_id) for out_id, in_id in session.execute(stmt).all()}


def list_transfer_pairs(session: Session) -> list[TransferPair]:
    """Return every transfer pair, in id order."""
    stmt = select(TransferPairRow).order_by(TransferPairRow.id)
    return [to_transfer_pair(row) for row in session.scalars(stmt).all()]


def _check_transfer(session: Session, out_id: int, in_id: int) -> None:
    """Refuse two transactions that cannot be one transfer."""
    out = session.get(TransactionRow, out_id)
    into = session.get(TransactionRow, in_id)
    if out is None or into is None:
        raise ValueError("transaction not found")
    if out.account_id == into.account_id:
        raise ValueError("a transfer goes from one account to another")
    if out.amount_cents >= 0 or into.amount_cents != -out.amount_cents:
        raise ValueError("a transfer pairs money out with the same amount in")


def _drop_rejection(session: Session, out_id: int, in_id: int) -> None:
    session.execute(
        delete(TransferRejectionRow).where(
            TransferRejectionRow.out_transaction_id == out_id,
            TransferRejectionRow.in_transaction_id == in_id,
        )
    )


def _store_rejection(session: Session, out_id: int, in_id: int) -> None:
    if (out_id, in_id) not in list_transfer_rejections(session):
        session.add(TransferRejectionRow(out_transaction_id=out_id, in_transaction_id=in_id))
    session.flush()


def create_transfer_pair(session: Session, out_id: int, in_id: int, status: str) -> TransferPair:
    """Pair an outflow with an inflow and return the pair. The caller commits."""
    _check_transfer(session, out_id, in_id)
    for transaction_id in (out_id, in_id):
        taken = select(TransferPairRow.id).where(_names(TransferPairRow, transaction_id))
        if session.scalars(taken).first() is not None:
            raise ValueError(f"transaction {transaction_id} is already in a transfer")
    if status not in (AUTO, CONFIRMED):
        raise ValueError("status must be auto or confirmed")
    _drop_rejection(session, out_id, in_id)
    row = TransferPairRow(out_transaction_id=out_id, in_transaction_id=in_id, status=status)
    session.add(row)
    session.flush()
    return to_transfer_pair(row)


def reject_transfer(session: Session, out_id: int, in_id: int) -> None:
    """Record that two transactions are not a transfer, unpairing them. The caller commits."""
    _check_transfer(session, out_id, in_id)
    session.execute(
        delete(TransferPairRow).where(
            TransferPairRow.out_transaction_id == out_id,
            TransferPairRow.in_transaction_id == in_id,
        )
    )
    _store_rejection(session, out_id, in_id)


def unpair_transfer(session: Session, pair_id: int) -> TransferPair:
    """Delete a pair and record it as rejected; return the pair. The caller commits."""
    row = session.get(TransferPairRow, pair_id)
    if row is None:
        raise ValueError("transfer not found")
    pair = to_transfer_pair(row)
    session.delete(row)
    session.flush()
    _store_rejection(session, pair.out_transaction_id, pair.in_transaction_id)
    return pair
