"""Account and people listings as data, before any view formats them."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from finances.analysis.people import load_attribution
from finances.db.repositories import (
    list_account_owners,
    list_accounts,
    list_cardholder_aliases,
    list_people,
)
from finances.domain.models import Account


@dataclass(frozen=True)
class AccountListing:
    account: Account
    owner: str | None


@dataclass(frozen=True)
class PersonListing:
    name: str
    owns: list[str]
    cardholders: list[str]


def account_listing(session: Session, *, include_inactive: bool = False) -> list[AccountListing]:
    attribution = load_attribution(session)
    return [
        AccountListing(account, attribution.owner(account.id))
        for account in list_accounts(session, include_inactive=include_inactive)
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
