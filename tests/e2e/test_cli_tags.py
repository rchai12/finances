from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, note_of
from tests.support import failed_cleanly, run, table_rows


@pytest.fixture
def card(tmp_settings: Settings) -> Settings:
    """Three card purchases: 1 ACME COFFEE, 2 FOOBAR GROCERY, 3 BAZ CAFE."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-450, "ACME COFFEE"), (-2599, "FOOBAR GROCERY"), (-500, "BAZ CAFE")), start=1
        ):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, number),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    return tmp_settings


def stored_note(transaction_id: int) -> str | None:
    engine = get_engine()
    with session_scope(engine) as session:
        found = note_of(session, transaction_id)
    engine.dispose()
    return found


def test_tagging(card: Settings) -> None:
    many = run("transactions", "tag", "--id", "1", "--id", "2", "--tag", "  Work   Trip ")
    assert (many.exit_code, many.stdout) == (0, '2 transactions: tagged "work trip".\n')
    one = run("transactions", "tag", "--id", "1", "--tag", "Tax")
    assert (one.exit_code, one.stdout) == (0, 'Transaction 1: tagged "tax".\n')
    assert table_rows(run("transactions", "tags").stdout) == [
        ["Tag", "Transactions"],
        ["tax", "1"],
        ["work trip", "2"],
    ]


def test_untagging(card: Settings) -> None:
    run("transactions", "tag", "--id", "1", "--id", "2", "--tag", "trip")
    removed = run("transactions", "untag", "--id", "2", "--tag", "TRIP")
    assert (removed.exit_code, removed.stdout) == (0, 'Transaction 2: "trip" removed.\n')
    assert table_rows(run("transactions", "tags").stdout) == [
        ["Tag", "Transactions"],
        ["trip", "1"],
    ]


def test_no_tags(card: Settings) -> None:
    assert run("transactions", "tags").stdout == "No tags.\n"


def test_a_note(card: Settings) -> None:
    saved = run("transactions", "note", "--id", "3", "--text", "  split with a friend ")
    assert (saved.exit_code, saved.stdout) == (0, "Transaction 3: note saved.\n")
    assert stored_note(3) == "split with a friend"
    removed = run("transactions", "note", "--id", "3", "--text", "")
    assert (removed.exit_code, removed.stdout) == (0, "Transaction 3: note removed.\n")
    assert stored_note(3) is None


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("tag", "--id", "9", "--tag", "trip"), "transaction not found"),
        (("tag", "--id", "1", "--tag", "   "), "a tag must be 1 to 30 characters"),
        (("tag", "--id", "9", "--tag", "   "), "transaction not found"),
        (("untag", "--id", "1", "--tag", "x" * 31), "a tag must be 1 to 30 characters"),
        (("note", "--id", "1", "--text", "x" * 501), "a note is at most 500 characters"),
        (("note", "--id", "9", "--text", "hi"), "transaction not found"),
    ],
)
def test_refused(card: Settings, args: tuple[str, ...], message: str) -> None:
    assert failed_cleanly(run("transactions", *args), message)
