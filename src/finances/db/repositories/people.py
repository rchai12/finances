from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from finances.db.orm import (
    AccountOwnerRow,
    CardholderAliasRow,
    PersonRow,
    to_person,
)
from finances.domain.models import Person
from finances.domain.people import (
    JOINT,
    normalize_cardholder,
    validate_person_name,
)
from finances.domain.text import NAME_LIMIT


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
