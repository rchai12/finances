from datetime import date

from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from finances.db.orm import (
    AccountRow,
    BalanceSnapshotRow,
    FeedPullRow,
    StatementRow,
    TransactionRow,
    to_account,
    to_balance_snapshot,
    to_feed_pull,
)
from finances.domain.models import (
    Account,
    AccountType,
    BalanceSnapshot,
    DataSource,
    validate_currency,
    validate_last4,
)
from finances.domain.text import NAME_LIMIT


class AccountExistsError(Exception):
    """Raised when an account with the same name already exists."""


_ACCOUNT_TYPES = tuple(item.value for item in AccountType)


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


def get_account(session: Session, account_id: int) -> Account | None:
    """Return the account with this id, or None."""
    row = session.get(AccountRow, account_id)
    return to_account(row) if row is not None else None


def rename_account(session: Session, account_id: int, new_name: str) -> Account:
    """Rename an account and return it. The caller commits."""
    row = session.get(AccountRow, account_id)
    if row is None:
        raise ValueError("account not found")
    clean = new_name.strip()
    if not clean:
        raise ValueError("account name must not be empty")
    if len(clean) > NAME_LIMIT:
        raise ValueError(f"account name must be at most {NAME_LIMIT} characters")
    other = session.scalars(
        select(AccountRow).where(func.lower(AccountRow.name) == clean.lower())
    ).first()
    if other is not None and other.id != account_id:
        raise AccountExistsError("an account with this name already exists")
    row.name = clean
    session.flush()
    return to_account(row)


def set_account_active(session: Session, account_id: int, active: bool) -> Account:
    """Open or close an account and return it. The caller commits."""
    row = session.get(AccountRow, account_id)
    if row is None:
        raise ValueError("account not found")
    row.is_active = active
    session.flush()
    return to_account(row)


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


def list_balance_snapshots(session: Session, account_id: int) -> list[BalanceSnapshot]:
    """Return the account's snapshots, latest as_of_date first, then highest id."""
    stmt = (
        select(BalanceSnapshotRow)
        .where(BalanceSnapshotRow.account_id == account_id)
        .order_by(BalanceSnapshotRow.as_of_date.desc(), BalanceSnapshotRow.id.desc())
    )
    return [to_balance_snapshot(row) for row in session.scalars(stmt).all()]


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


def account_data_span(session: Session, account_id: int) -> tuple[date, date] | None:
    """The earliest and latest day of the account's statements, posted transactions, and pulls."""
    statements = session.execute(
        select(func.min(StatementRow.period_start), func.max(StatementRow.period_end)).where(
            StatementRow.account_id == account_id
        )
    ).one()
    day = func.coalesce(TransactionRow.transaction_date, TransactionRow.posted_date)
    transactions = session.execute(
        select(func.min(day), func.max(day)).where(
            TransactionRow.account_id == account_id, TransactionRow.is_pending.is_(False)
        )
    ).one()
    pulls = select(FeedPullRow).where(FeedPullRow.account_id == account_id).limit(1)
    first = session.scalars(pulls.order_by(FeedPullRow.pulled_at, FeedPullRow.id)).first()
    last = session.scalars(
        pulls.order_by(FeedPullRow.pulled_at.desc(), FeedPullRow.id.desc())
    ).first()
    days = [found for found in (*statements, *transactions) if found is not None]
    days += [to_feed_pull(row).pulled_at.date() for row in (first, last) if row is not None]
    if not days:
        return None
    return min(days), max(days)
