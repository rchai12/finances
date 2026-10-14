import pytest

from finances.domain.feed_setup import (
    NO_NAME,
    TEXT_LIMIT,
    AccountGuess,
    guess_account,
    guess_owner,
    new_accounts,
    suggest_existing,
)
from finances.domain.models import AccountType

CHECKING, SAVINGS, CARD, OTHER = (
    AccountType.CHECKING,
    AccountType.SAVINGS,
    AccountType.CREDIT_CARD,
    AccountType.OTHER,
)


def test_the_limits() -> None:
    assert (TEXT_LIMIT, NO_NAME) == (100, "New account")


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("Everyday Checking", CHECKING),
        ("PROBE CHK 0001", CHECKING),
        ("High Yield Savings", SAVINGS),
        ("Online Saving", SAVINGS),
        ("Money Market Account", SAVINGS),
        ("Probe Visa Signature", CARD),
        ("Cash Rewards Mastercard", CARD),
        ("Platinum Card", CARD),
        ("AMEX Gold", CARD),
        ("American Express Blue", CARD),
        ("Discover It", CARD),
        ("Probe Credit Card", CARD),
        ("Credit Union Checking", CHECKING),
        ("Savings Card Plus", SAVINGS),
        ("Brokerage", OTHER),
        ("Cardinal Fund", OTHER),
        ("Checkingplus", OTHER),
        ("Visas", OTHER),
        ("", OTHER),
    ],
)
def test_the_type_comes_from_words_in_the_name(name: str, kind: AccountType) -> None:
    assert guess_account(name, "Probe Bank").type == kind


@pytest.mark.parametrize(
    ("name", "last4"),
    [
        ("Probe Visa ...1234", "1234"),
        ("Probe Visa (5678)", "5678"),
        ("Card ending in 0042", "0042"),
        ("Card 4400 0000 0000 5555", "5555"),
        ("Checking 0001234567", None),
        ("Savings 123", None),
        ("Card 1234 x", "1234"),
        ("Account 2024 Plan 77", None),
        ("No digits", None),
        ("Card ١٢٣٤", None),
    ],
)
def test_the_last_four_digits_come_from_the_last_run_of_digits(
    name: str, last4: str | None
) -> None:
    assert guess_account(name, "Probe Bank").last4 == last4


def test_the_name_and_institution_are_tidied_and_cut() -> None:
    guess = guess_account("  Probe   Visa\tSignature  ", "  Probe\n Bank ")
    assert guess == AccountGuess("Probe Visa Signature", "Probe Bank", CARD, None)
    long = guess_account("N" * 99 + " MORE", "I" * 150)
    assert (long.name, long.institution) == ("N" * 99, "I" * 100)


def test_a_missing_name_gets_a_placeholder() -> None:
    assert guess_account("   ", "").name == NO_NAME
    assert guess_account("", "").institution == ""


@pytest.mark.parametrize(
    ("link", "people", "owner"),
    [
        ("kim", ["Alex", "Kim"], "Kim"),
        ("KIM", ["kim"], "kim"),
        ("alex", ["Kim"], None),
        ("default", [], None),
        ("kim", [" Kim "], " Kim "),
    ],
)
def test_the_owner_is_the_person_named_like_the_link(
    link: str, people: list[str], owner: str | None
) -> None:
    assert guess_owner(link, people) == owner


def guess(name: str = "Probe Visa", last4: str | None = "1234") -> AccountGuess:
    return AccountGuess(name, "Probe Bank", CARD, last4)


def test_an_account_with_the_same_last_four_digits_is_suggested() -> None:
    candidates = [("Old Card", "9999"), ("Statement Card", "1234"), ("Probe Visa", None)]
    assert suggest_existing(guess(), candidates) == "Statement Card"


def test_two_with_the_same_digits_fall_back_to_the_name() -> None:
    candidates = [("A", "1234"), ("probe visa", "1234")]
    assert suggest_existing(guess(), candidates) == "probe visa"
    assert suggest_existing(guess(), [("A", "1234"), ("B", "1234")]) is None


def test_without_digits_the_name_decides() -> None:
    assert suggest_existing(guess(last4=None), [("PROBE VISA", "1234")]) == "PROBE VISA"
    assert suggest_existing(guess(last4=None), [("Other", None)]) is None
    assert suggest_existing(guess(), []) is None


@pytest.mark.parametrize(
    ("count", "text"), [(1, "1 new account"), (2, "2 new accounts"), (0, "0 new accounts")]
)
def test_counting_new_accounts(count: int, text: str) -> None:
    assert new_accounts(count) == text
