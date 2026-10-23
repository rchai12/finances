"""SimpleFIN mappings, waiting counts, and setup offers as data."""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from finances.db.repositories import (
    account_names,
    latest_feed_pull,
    list_accounts,
    list_feed_accounts,
    list_new_feed_accounts,
    list_people,
)
from finances.domain.feed_setup import AccountGuess, guess_account, guess_owner, suggest_existing
from finances.domain.models import Account, FeedPull
from finances.sync.runner import LinkRun


@dataclass(frozen=True)
class MappingStatus:
    link: str
    account: str
    feed_account: str
    keychain: str
    last_pull: FeedPull | None
    balanced: FeedPull | None


@dataclass(frozen=True)
class SetupOffer:
    link: str
    feed_account: str
    name: str
    institution: str
    guess: AccountGuess
    owner: str | None
    suggestion: str | None


def mapping_status(session: Session, keychain: Callable[[str], str]) -> list[MappingStatus]:
    names = account_names(session)
    states: dict[str, str] = {}
    statuses = []
    for item in list_feed_accounts(session):
        if item.link not in states:
            states[item.link] = keychain(item.link)
        statuses.append(
            MappingStatus(
                item.link,
                names[item.account_id],
                item.provider_account_id,
                states[item.link],
                latest_feed_pull(session, item.account_id),
                latest_feed_pull(session, item.account_id, with_balance=True),
            )
        )
    return statuses


def waiting_counts(session: Session, runs: list[LinkRun]) -> list[tuple[str, int]]:
    """How many new SimpleFIN accounts each link that ran has, leaving out links with none."""
    counts = [
        (run.link, len(list_new_feed_accounts(session, run.link)))
        for run in runs
        if run.report is not None
    ]
    return [(link, count) for link, count in counts if count]


def unmapped_accounts(session: Session) -> list[Account]:
    """The active accounts that no SimpleFIN account feeds, under any link."""
    mapped = {item.account_id for item in list_feed_accounts(session)}
    return [account for account in list_accounts(session) if account.id not in mapped]


def setup_offers(session: Session) -> list[SetupOffer]:
    """For each new SimpleFIN account, the guesses that pre-fill its setup."""
    people = [person.name for person in list_people(session)]
    candidates = [(account.name, account.last4) for account in unmapped_accounts(session)]
    offers = []
    for item in list_new_feed_accounts(session):
        guess = guess_account(item.name, item.institution)
        offers.append(
            SetupOffer(
                item.link,
                item.provider_account_id,
                item.name,
                item.institution,
                guess,
                guess_owner(item.link, people),
                suggest_existing(guess, candidates),
            )
        )
    return offers
