"""Account and people listings as data, before any view formats them."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from finances.db.repositories import (
    list_account_owners,
    list_accounts,
    list_cardholder_aliases,
    list_people,
)
from finances.domain.models import Account
from finances.domain.people import JOINT


@dataclass(frozen=True)
class AccountListing:
    account: Account
    owner: str | None
    joint: bool = False


@dataclass(frozen=True)
class PersonListing:
    name: str
    owns: list[str]
    cardholders: list[str]


def account_listing(session: Session, *, include_inactive: bool = False) -> list[AccountListing]:
    accounts = list_accounts(session, include_inactive=include_inactive)
    people = {person.id: person.name for person in list_people(session)}
    owners = list_account_owners(session)
    return [
        AccountListing(
            account,
            None
            if account.id not in owners
            else (JOINT if owners[account.id] is None else people[owners[account.id]]),
            account.id in owners and owners[account.id] is None,
        )
        for account in accounts
    ]


def people_listing(session: Session) -> list[PersonListing]:
    accounts = list_accounts(session, include_inactive=True)
    owners = list_account_owners(session)
    aliases = list_cardholder_aliases(session)
    return [
        PersonListing(
            person.name,
            [account.name for account in accounts if owners.get(account.id) == person.id],
            sorted(name for name, owner in aliases.items() if owner == person.id),
        )
        for person in list_people(session)
    ]
