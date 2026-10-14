"""Whose money each transaction is."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from finances.db.repositories import (
    get_person_by_name,
    list_account_owners,
    list_cardholder_aliases,
    list_people,
    list_transactions,
)
from finances.domain.models import Transaction
from finances.domain.people import JOINT, person_for

JOINT_FILTER = "joint"
UNASSIGNED_FILTER = "unassigned"


@dataclass(frozen=True)
class Attribution:
    """Who owns each account and who each statement cardholder name is."""

    owners: dict[int, str]
    aliases: dict[str, str]

    def owner(self, account_id: int) -> str | None:
        return self.owners.get(account_id)

    def person(self, transaction: Transaction) -> str | None:
        return person_for(transaction.cardholder, self.owner(transaction.account_id), self.aliases)


def load_attribution(session: Session) -> Attribution:
    names = {person.id: person.name for person in list_people(session)}
    owners = {
        account_id: JOINT if person_id is None else names[person_id]
        for account_id, person_id in list_account_owners(session).items()
    }
    aliases = {
        cardholder: names[person_id]
        for cardholder, person_id in list_cardholder_aliases(session).items()
    }
    return Attribution(owners=owners, aliases=aliases)


def _wanted(session: Session, person: str) -> str | None:
    """Return the attribution that a --person value keeps: a name, JOINT, or None."""
    clean = person.strip()
    if clean.lower() == JOINT_FILTER:
        return JOINT
    if clean.lower() == UNASSIGNED_FILTER:
        return None
    found = get_person_by_name(session, clean)
    if found is None:
        raise ValueError("person not found")
    return found.name


def list_transactions_with_people(
    session: Session,
    account_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = 100,
    person: str | None = None,
) -> list[tuple[Transaction, str | None]]:
    """Return transactions, newest first, each with its person; the limit counts kept rows."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    attribution = load_attribution(session)
    if person is None:
        found = list_transactions(session, account_id, start, end, limit)
        return [(row, attribution.person(row)) for row in found]
    wanted = _wanted(session, person)
    fetch = limit
    while True:
        found = list_transactions(session, account_id, start, end, fetch)
        kept = [(row, who) for row in found if (who := attribution.person(row)) == wanted]
        if len(kept) >= limit or len(found) < fetch:
            return kept[:limit]
        fetch *= 2
