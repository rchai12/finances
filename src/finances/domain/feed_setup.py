"""Guesses that pre-fill the setup of a new aggregator account. Nothing here is stored."""

import re
from dataclasses import dataclass

from finances.domain.models import AccountType

TEXT_LIMIT = 100
NO_NAME = "New account"

_TYPE_WORDS = (
    (AccountType.CHECKING, re.compile(r"\b(?:checking|chk)\b", re.IGNORECASE)),
    (AccountType.SAVINGS, re.compile(r"\b(?:savings?|money market)\b", re.IGNORECASE)),
    (
        AccountType.CREDIT_CARD,
        re.compile(
            r"\b(?:card|credit card|visa|mastercard|amex|american express|discover)\b",
            re.IGNORECASE,
        ),
    ),
)
_DIGITS = re.compile(r"[0-9]+")


@dataclass(frozen=True)
class AccountGuess:
    """What the setup form is filled in with for a new aggregator account."""

    name: str
    institution: str
    type: AccountType
    last4: str | None


def _tidy(text: str) -> str:
    return " ".join(text.split())[:TEXT_LIMIT].rstrip()


def guess_account(name: str, institution: str) -> AccountGuess:
    """Guess an account's details from the aggregator's name and institution."""
    tidy_name = _tidy(name) or NO_NAME
    kind = next((kind for kind, words in _TYPE_WORDS if words.search(tidy_name)), AccountType.OTHER)
    runs = _DIGITS.findall(tidy_name)
    last4 = runs[-1] if runs and len(runs[-1]) == 4 else None
    return AccountGuess(tidy_name, _tidy(institution), kind, last4)


def guess_owner(link: str, people: list[str]) -> str | None:
    """Return the first person named like the link, ignoring case and outer spaces."""
    wanted = link.strip().lower()
    return next((person for person in people if person.strip().lower() == wanted), None)


def suggest_existing(guess: AccountGuess, candidates: list[tuple[str, str | None]]) -> str | None:
    """Return the name of an account that looks like the guess: by last4, then by name."""
    if guess.last4 is not None:
        same_digits = [name for name, last4 in candidates if last4 == guess.last4]
        if len(same_digits) == 1:
            return same_digits[0]
    wanted = guess.name.lower()
    return next((name for name, _ in candidates if name.lower() == wanted), None)


def new_accounts(count: int) -> str:
    return "1 new account" if count == 1 else f"{count} new accounts"
