from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_person, set_account_owner
from finances.domain.shared import SIZE
from tests.support import failed_cleanly, run, table_rows

SETTLE = ("--from", "Alex", "--to", "Sam", "--amount", "4.00", "--date", "2026-05-20")


@pytest.fixture
def card(tmp_settings: Settings) -> Settings:
    """Sam and Alex; a card owned by Sam with a purchase of -$20.01 (1) and a refund of
    $6.00 (2)."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        sam = create_person(session, "Sam")
        create_person(session, "Alex")
        account = create_account(session, "Test Card", "Test Bank", "credit_card")
        set_account_owner(session, account.id, sam.id)
        for number, (day, cents) in enumerate(((1, -2001), (3, 600)), start=1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description="FOOBAR GROCERY",
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    return tmp_settings


def test_sharing(card: Settings) -> None:
    half = run("shared", "add", "--id", "1", "--with", "alex")
    assert (half.exit_code, half.stdout) == (0, "Transaction 1: Alex owes Sam $10.00.\n")
    refund = run("shared", "add", "--id", "2", "--with", "Alex", "--share", "2.00")
    assert (refund.exit_code, refund.stdout) == (0, "Transaction 2: Sam owes Alex $2.00.\n")
    assert table_rows(run("shared", "list").stdout) == [
        ["ID", "Paid by", "Owes", "Owed"],
        ["1", "Sam", "Alex", "$10.00"],
        ["2", "Sam", "Alex", "-$2.00"],
    ]
    assert run("shared", "owed").stdout == "Alex owes Sam $8.00.\n"


def test_settling(card: Settings) -> None:
    run("shared", "add", "--id", "1", "--with", "Alex")
    settled = run("shared", "settle", *SETTLE)
    assert (settled.exit_code, settled.stdout) == (0, "Alex paid Sam $4.00 on 2026-05-20.\n")
    assert table_rows(run("shared", "settlements").stdout) == [
        ["ID", "Date", "From", "To", "Amount"],
        ["1", "2026-05-20", "Alex", "Sam", "$4.00"],
    ]
    assert run("shared", "owed").stdout == "Alex owes Sam $6.00.\n"
    deleted = run("shared", "delete-settlement", "--id", "1")
    assert (deleted.exit_code, deleted.stdout) == (
        0,
        "Deleted settlement 1: Alex paid Sam $4.00 on 2026-05-20.\n",
    )
    assert run("shared", "settlements").stdout == "No settlements.\n"


def test_a_settlement_today(card: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 6, 1))
    settled = run("shared", "settle", "--from", "Alex", "--to", "Sam", "--amount", "1")
    assert settled.stdout == "Alex paid Sam $1.00 on 2026-06-01.\n"


def test_unsharing(card: Settings) -> None:
    run("shared", "add", "--id", "1", "--with", "Alex")
    removed = run("shared", "remove", "--id", "1")
    assert (removed.exit_code, removed.stdout) == (0, "Transaction 1: no longer shared.\n")
    assert run("shared", "list").stdout == "No shared transactions.\n"
    assert run("shared", "owed").stdout == "Nobody owes anybody.\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("add", "--id", "9", "--with", "Alex"), "transaction not found"),
        (("add", "--id", "1", "--with", "Kai"), "person not found"),
        (("add", "--id", "1", "--with", "Sam"), "a person cannot owe themselves"),
        (("add", "--id", "1", "--with", "Alex", "--share", "30.00"), SIZE),
        (("add", "--id", "1", "--with", "Alex", "--share", "ten"), "invalid money text"),
        (("remove", "--id", "1"), "the transaction is not shared"),
        (
            ("settle", "--from", "Alex", "--to", "alex", "--amount", "1"),
            "a person cannot pay themselves",
        ),
        (
            ("settle", "--from", "Alex", "--to", "Sam", "--amount", "0"),
            "a settlement must be more than zero",
        ),
        (("settle", "--from", "Alex", "--to", "Sam", "--amount", "x"), "invalid money text"),
        (("delete-settlement", "--id", "9"), "settlement not found"),
    ],
)
def test_refused(card: Settings, args: tuple[str, ...], message: str) -> None:
    assert failed_cleanly(run("shared", *args), message)
