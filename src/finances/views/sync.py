"""SimpleFIN status, sync results, and the setup offers for new SimpleFIN accounts."""

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
from finances.domain.models import Account
from finances.sync.links import load_access_url
from finances.sync.runner import LinkRun
from finances.sync.simplefin import SyncError
from finances.views.format import balance_date_text, drift_text, last_pull_text


@dataclass(frozen=True)
class StatusRow:
    link: str
    account: str
    feed_account: str
    keychain: str
    last_pull: str
    balance_date: str
    drift: str


@dataclass(frozen=True)
class RunRow:
    link: str
    account: str
    feed_account: str
    new: str
    changed: str
    removed: str
    same: str
    drift: str
    problem: str


@dataclass(frozen=True)
class SetupOffer:
    link: str
    feed_account: str
    name: str
    institution: str
    guess: AccountGuess
    owner: str | None
    suggestion: str | None


def keychain_state(link: str) -> str:
    try:
        return "no" if load_access_url(link) is None else "yes"
    except SyncError:
        return "unknown"


def status_rows(session: Session) -> list[StatusRow]:
    """One row per mapping: its keychain state, last pull, and last balance drift."""
    names = account_names(session)
    keychain: dict[str, str] = {}
    rows = []
    for item in list_feed_accounts(session):
        if item.link not in keychain:
            keychain[item.link] = keychain_state(item.link)
        balanced = latest_feed_pull(session, item.account_id, with_balance=True)
        rows.append(
            StatusRow(
                item.link,
                names[item.account_id],
                item.provider_account_id,
                keychain[item.link],
                last_pull_text(latest_feed_pull(session, item.account_id)),
                balance_date_text(balanced),
                drift_text(balanced),
            )
        )
    return rows


def run_rows(runs: list[LinkRun], names: dict[int, str]) -> list[RunRow]:
    """One row per account of each link that ran."""
    rows = []
    for run in runs:
        if run.report is None:
            continue
        for item in run.report.accounts:
            pull = item.pull
            counts = (
                ("", "", "", "")
                if pull is None
                else (str(pull.inserted), str(pull.updated), str(pull.removed), str(pull.unchanged))
            )
            rows.append(
                RunRow(
                    run.link,
                    "" if item.account_id is None else names[item.account_id],
                    item.provider_account_id,
                    *counts,
                    drift_text(pull),
                    item.problem or "",
                )
            )
    return rows


def waiting_counts(session: Session, runs: list[LinkRun]) -> list[tuple[str, int]]:
    """How many new SimpleFIN accounts each link that ran has, leaving out links with none."""
    counts = [
        (run.link, len(list_new_feed_accounts(session, run.link)))
        for run in runs
        if run.report is not None
    ]
    return [(link, count) for link, count in counts if count]


def simplefin_messages(runs: list[LinkRun]) -> list[tuple[str, str]]:
    return [
        (run.link, message)
        for run in runs
        if run.report is not None
        for message in run.report.messages
    ]


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
