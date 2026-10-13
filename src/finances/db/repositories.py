"""Database reads and writes. Functions take a Session and return domain objects."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finances.db.orm import AccountRow, to_account
from finances.domain.models import Account, AccountType, validate_last4


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
