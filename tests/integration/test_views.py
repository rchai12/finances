from dataclasses import astuple, fields
from datetime import UTC, date, datetime

import keyring
import keyring.backend
import keyring.errors
import pytest
from sqlalchemy import Engine

from finances.analysis.listings import account_listing, people_listing
from finances.analysis.simplefin import (
    SetupOffer,
    mapping_status,
    setup_offers,
    unmapped_accounts,
    waiting_counts,
)
from finances.db.engine import session_scope
from finances.db.orm import AccountRow as AccountTable
from finances.db.repositories import (
    account_names,
    create_account,
    create_feed_pull,
    create_person,
    map_feed_account,
    record_seen_feed_account,
    set_account_owner,
    set_cardholder_alias,
    set_feed_account_ignored,
)
from finances.domain.feed_setup import AccountGuess
from finances.domain.models import AccountType, DataSource, FeedPull, Transaction
from finances.sync.links import keychain_state
from finances.sync.runner import AccountSync, LinkRun, SyncReport
from finances.views.accounts import AccountRow, account_rows
from finances.views.format import (
    BULLETS,
    balance_date_text,
    drift_text,
    last_pull_text,
    mask_last4,
)
from finances.views.people import PersonRow, people_rows
from finances.views.sync import RunRow, StatusRow, run_rows, simplefin_messages, status_rows
from finances.views.transactions import TransactionRow, transaction_row

SERVICE = "finances-simplefin"
DAY = date(2026, 5, 9)
NOON = datetime(2026, 5, 9, 12, 30, tzinfo=UTC)


class BrokenKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringError("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.KeyringError("locked")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.KeyringError("locked")


def pull(**changes: object) -> FeedPull:
    values = {
        "id": 1,
        "account_id": 1,
        "inserted": 3,
        "updated": 1,
        "removed": 0,
        "unchanged": 7,
        "feed_total_cents": -100,
        "balance_cents": -100,
        "balance_date": date(2026, 5, 8),
        "drift_cents": -250,
        "pulled_at": NOON,
    }
    return FeedPull(**{**values, **changes})


@pytest.fixture
def household(db_engine: Engine) -> Engine:
    """Card (Alex), Checking (Joint), Savings (no owner, closed), Old Card (Sam, closed)."""
    with session_scope(db_engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        savings = create_account(session, "Test Savings", "Test Bank", "savings", last4="3333")
        old = create_account(session, "Test Old Card", "Test Bank", "credit_card", last4="4444")
        alex = create_person(session, "Alex")
        sam = create_person(session, "Sam")
        set_account_owner(session, card.id, alex.id)
        set_account_owner(session, checking.id, None)
        set_account_owner(session, old.id, sam.id)
        set_cardholder_alias(session, "SAM DOE", sam.id)
        set_cardholder_alias(session, "S DOE", sam.id)
        session.get(AccountTable, savings.id).is_active = False
        session.get(AccountTable, old.id).is_active = False
    return db_engine


# Formatting


def test_the_mask() -> None:
    assert BULLETS == "••"
    assert (mask_last4("1234"), mask_last4(None), mask_last4("")) == ("••1234", "", "")


def test_pull_texts() -> None:
    assert (drift_text(pull()), drift_text(pull(drift_cents=None)), drift_text(None)) == (
        "-$2.50",
        "",
        "",
    )
    assert (balance_date_text(pull()), balance_date_text(pull(balance_date=None))) == (
        "2026-05-08",
        "",
    )
    assert balance_date_text(None) == ""
    assert (last_pull_text(pull()), last_pull_text(None)) == ("2026-05-09 12:30 UTC", "never")


# Accounts and people


def test_account_rows(household: Engine) -> None:
    with session_scope(household) as session:
        assert account_rows(account_listing(session)) == [
            AccountRow("Test Card", "Test Bank", "credit_card", "••1111", "yes", "Alex"),
            AccountRow("Test Checking", "Test Bank", "checking", "", "yes", "Joint"),
        ]
        every = account_rows(account_listing(session, include_inactive=True))
    assert [row.name for row in every] == [
        "Test Card",
        "Test Checking",
        "Test Old Card",
        "Test Savings",
    ]
    assert every[2:] == [
        AccountRow("Test Old Card", "Test Bank", "credit_card", "••4444", "no", "Sam"),
        AccountRow("Test Savings", "Test Bank", "savings", "••3333", "no", ""),
    ]


def test_an_account_row_lists_its_cells_in_column_order() -> None:
    names = [item.name for item in fields(AccountRow)]
    assert names == ["name", "institution", "type", "last4", "active", "owner"]
    assert astuple(AccountRow("a", "b", "c", "d", "e", "f")) == ("a", "b", "c", "d", "e", "f")


def test_people_rows(household: Engine) -> None:
    with session_scope(household) as session:
        assert people_rows(people_listing(session)) == [
            PersonRow("Alex", "Test Card", ""),
            PersonRow("Sam", "Test Old Card", "S DOE, SAM DOE"),
        ]
    assert [item.name for item in fields(PersonRow)] == ["name", "owns", "cardholders"]


def test_account_names_include_closed_accounts(household: Engine) -> None:
    with session_scope(household) as session:
        assert account_names(session) == {
            1: "Test Card",
            2: "Test Checking",
            3: "Test Savings",
            4: "Test Old Card",
        }


def test_no_people_or_accounts(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        assert (
            account_rows(account_listing(session)),
            people_rows(people_listing(session)),
            account_names(session),
        ) == (
            [],
            [],
            {},
        )


# Transactions


def transaction(**changes: object) -> Transaction:
    values = {
        "id": 1,
        "account_id": 2,
        "statement_id": None,
        "posted_date": date(2026, 5, 3),
        "transaction_date": None,
        "amount_cents": -450,
        "description": "ACME COFFEE",
        "section": "purchases",
        "card_last4": "2222",
        "cardholder": None,
        "external_id": None,
        "source": DataSource.STATEMENT,
        "is_pending": False,
        "fingerprint": "f" * 64,
        "created_at": NOON,
    }
    return Transaction(**{**values, **changes})


def test_transaction_row() -> None:
    names = {2: "Test Checking"}
    assert transaction_row(transaction(), "Sam", names) == TransactionRow(
        "2026-05-03", "Test Checking", "ACME COFFEE", "-$4.50", "••2222", "purchases", "Sam"
    )
    assert transaction_row(transaction(card_last4=None, section=None), None, names) == (
        TransactionRow("2026-05-03", "Test Checking", "ACME COFFEE", "-$4.50", "", "", "")
    )
    assert [item.name for item in fields(TransactionRow)] == [
        "date",
        "account",
        "description",
        "amount",
        "card",
        "section",
        "person",
    ]


# SimpleFIN status


def test_keychain_state(keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = "https://u:p@bridge.simplefin.org/x"
    assert (keychain_state("alex"), keychain_state("sam")) == ("yes", "no")


def test_keychain_state_when_the_keychain_fails() -> None:
    previous = keyring.get_keyring()
    keyring.set_keyring(BrokenKeyring())
    try:
        assert keychain_state("alex") == "unknown"
    finally:
        keyring.set_keyring(previous)


def test_status_rows(household: Engine, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = "https://u:p@bridge.simplefin.org/x"
    with session_scope(household) as session:
        map_feed_account(session, 1, "ACT-1", "alex")
        map_feed_account(session, 2, "ACT-2", "sam")
        create_feed_pull(
            session,
            account_id=1,
            inserted=1,
            updated=0,
            removed=0,
            unchanged=0,
            feed_total_cents=-100,
            balance_cents=-100,
            balance_date=date(2026, 5, 9),
            drift_cents=-250,
        )
        create_feed_pull(
            session,
            account_id=1,
            inserted=0,
            updated=0,
            removed=0,
            unchanged=1,
            feed_total_cents=-100,
            balance_cents=None,
            balance_date=None,
            drift_cents=None,
        )
    with session_scope(household) as session:
        rows = status_rows(mapping_status(session, keychain_state))
    assert [astuple(row)[:4] for row in rows] == [
        ("alex", "Test Card", "ACT-1", "yes"),
        ("sam", "Test Checking", "ACT-2", "no"),
    ]
    assert rows[0].last_pull.endswith(" UTC") and len(rows[0].last_pull) == 20
    assert (rows[0].balance_date, rows[0].drift) == ("2026-05-09", "-$2.50")
    assert rows[1] == StatusRow("sam", "Test Checking", "ACT-2", "no", "never", "", "")


def test_no_status_rows_without_mappings(household: Engine) -> None:
    with session_scope(household) as session:
        assert status_rows(mapping_status(session, keychain_state)) == []


# Sync now and fin sync run


def test_run_rows_messages_and_failures() -> None:
    report = SyncReport(
        [
            AccountSync("ACT-1", 1, pull(), None),
            AccountSync("ACT-9", None, None, "not mapped"),
            AccountSync("ACT-2", 2, None, "currency is not USD"),
        ],
        ["Probe note"],
    )
    runs = [
        LinkRun("alex", report, None),
        LinkRun("bob", None, "link bob is not set up"),
        LinkRun("sam", SyncReport([], ["Sam note", "Other note"]), None),
    ]
    assert run_rows(runs, {1: "Test Card", 2: "Test Checking"}) == [
        RunRow("alex", "Test Card", "ACT-1", "3", "1", "0", "7", "-$2.50", ""),
        RunRow("alex", "", "ACT-9", "", "", "", "", "", "not mapped"),
        RunRow("alex", "Test Checking", "ACT-2", "", "", "", "", "", "currency is not USD"),
    ]
    assert simplefin_messages(runs) == [
        ("alex", "Probe note"),
        ("sam", "Sam note"),
        ("sam", "Other note"),
    ]
    assert [item.name for item in fields(RunRow)] == [
        "link",
        "account",
        "feed_account",
        "new",
        "changed",
        "removed",
        "same",
        "drift",
        "problem",
    ]


def test_waiting_counts_only_links_that_ran(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        for link, feed_id in (("sam", "S-1"), ("alex", "A-1"), ("alex", "A-2"), ("bob", "B-1")):
            record_seen_feed_account(session, link, feed_id, "Probe", "Probe Bank", DAY)
        record_seen_feed_account(session, "kim", "K-1", "Probe", "Probe Bank", DAY)
        set_feed_account_ignored(session, "kim", "K-1", True)
    runs = [
        LinkRun("sam", SyncReport([], []), None),
        LinkRun("bob", None, "link bob is not set up"),
        LinkRun("kim", SyncReport([], []), None),
        LinkRun("alex", SyncReport([], []), None),
    ]
    with session_scope(db_engine) as session:
        assert waiting_counts(session, runs) == [("sam", 1), ("alex", 2)]


# Setting up new SimpleFIN accounts


def test_unmapped_accounts_are_open_and_have_no_mapping(household: Engine) -> None:
    with session_scope(household) as session:
        map_feed_account(session, 1, "ACT-1", "alex")
        assert [item.name for item in unmapped_accounts(session)] == ["Test Checking"]


def test_setup_offers(household: Engine) -> None:
    with session_scope(household) as session:
        create_account(session, "Probe Savings", "Probe Bank", "savings", last4="4321")
        create_person(session, "Kim")
        record_seen_feed_account(
            session, "kim", "K-1", "High Yield Savings 4321", "Probe Bank", DAY
        )
        record_seen_feed_account(session, "kim", "K-2", "Brokerage", "", DAY)
        record_seen_feed_account(session, "kim", "K-3", "Ignored", "Probe Bank", DAY)
        set_feed_account_ignored(session, "kim", "K-3", True)
    with session_scope(household) as session:
        offers = setup_offers(session)
    assert offers == [
        SetupOffer(
            "kim",
            "K-1",
            "High Yield Savings 4321",
            "Probe Bank",
            AccountGuess("High Yield Savings 4321", "Probe Bank", AccountType.SAVINGS, "4321"),
            "Kim",
            "Probe Savings",
        ),
        SetupOffer(
            "kim",
            "K-2",
            "Brokerage",
            "",
            AccountGuess("Brokerage", "", AccountType.OTHER, None),
            "Kim",
            None,
        ),
    ]


def test_no_offers_without_seen_accounts(household: Engine) -> None:
    with session_scope(household) as session:
        assert setup_offers(session) == []
