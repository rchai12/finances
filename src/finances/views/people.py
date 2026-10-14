"""The people list, as `fin people list` and the People page show it."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from finances.db.repositories import (
    list_account_owners,
    list_accounts,
    list_cardholder_aliases,
    list_people,
)


@dataclass(frozen=True)
class PersonRow:
    name: str
    owns: str
    cardholders: str


def people_rows(session: Session) -> list[PersonRow]:
    accounts = list_accounts(session, include_inactive=True)
    owners = list_account_owners(session)
    aliases = list_cardholder_aliases(session)
    return [
        PersonRow(
            person.name,
            ", ".join(account.name for account in accounts if owners.get(account.id) == person.id),
            ", ".join(sorted(name for name, owner in aliases.items() if owner == person.id)),
        )
        for person in list_people(session)
    ]
