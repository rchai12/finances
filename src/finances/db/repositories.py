"""Database reads and writes. Functions take a Session and return domain objects."""

from collections.abc import Iterable
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finances.db.orm import (
    AccountRow,
    BalanceSnapshotRow,
    StatementRow,
    TransactionRow,
    to_account,
    to_balance_snapshot,
    to_statement,
    to_transaction,
)
from finances.domain.models import (
    Account,
    AccountType,
    BalanceSnapshot,
    DataSource,
    NewTransaction,
    Statement,
    Transaction,
    validate_last4,
)

_FINGERPRINT_CHUNK = 500


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
    # Clean the name and institution by removing outer spaces
    clean_name = name.strip()
    clean_institution = institution.strip()

    # Validate that name and institution are not empty after cleaning
    if not clean_name:
        raise ValueError("account name must not be empty")
    if not clean_institution:
        raise ValueError("institution must not be empty")

    # Check if an account with this name already exists (case-insensitive comparison)
    stmt = select(AccountRow).where(func.lower(AccountRow.name) == clean_name.lower())
    existing_account = session.scalars(stmt).first()

    if existing_account is not None:
        raise AccountExistsError("an account with this name already exists")

    # Validate last4 if provided
    if last4 is not None:
        validate_last4(last4)

    # Determine the type value to store (either from AccountType enum or string)
    if isinstance(account_type, AccountType):
        type_value = account_type.value
    else:
        # Validate that account_type is a valid one, this will raise ValueError if invalid
        validated_type = AccountType(account_type)
        type_value = validated_type.value

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
