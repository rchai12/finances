from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from tests.support import failed_cleanly, plain_lines, run, table_rows

HEADINGS = ["ID", "Date", "Account", "Merchant", "Amount", "Now"]


@pytest.fixture
def card(tmp_settings: Settings) -> Settings:
    """Eleven ACME CAFE purchases (1 to 11, May 1 to 11) and FOOBAR GROCERY (12, May 12) on a
    card. No rules."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [(-450, "ACME CAFE")] * 11 + [(-3000, "FOOBAR GROCERY")]
        for number, (cents, description) in enumerate(rows, start=1):
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


def test_a_preview_shows_the_ten_newest(card: Settings) -> None:
    result = run("rules", "preview", "--pattern", "acme", "--category", "Dining")
    assert result.exit_code == 0
    assert plain_lines(result.stdout) == [
        "This rule would put 11 transactions in Dining.",
        "Showing the 10 newest.",
    ]
    assert table_rows(result.stdout) == [
        HEADINGS,
        ["11", "2026-05-11", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["10", "2026-05-10", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["9", "2026-05-09", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["8", "2026-05-08", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["7", "2026-05-07", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["6", "2026-05-06", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["5", "2026-05-05", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["4", "2026-05-04", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["3", "2026-05-03", "Test Card", "ACME CAFE", "-$4.50", ""],
        ["2", "2026-05-02", "Test Card", "ACME CAFE", "-$4.50", ""],
    ]
    assert run("rules", "list").stdout == "No rules.\n"


def test_one_transaction(card: Settings) -> None:
    result = run(
        "rules",
        "preview",
        "--pattern",
        "foobar grocery",
        "--match",
        "equals",
        "--category",
        "Groceries",
    )
    assert plain_lines(result.stdout) == ["This rule would put 1 transaction in Groceries."]
    assert table_rows(result.stdout) == [
        HEADINGS,
        ["12", "2026-05-12", "Test Card", "FOOBAR GROCERY", "-$30.00", ""],
    ]


def test_no_transactions(card: Settings) -> None:
    result = run("rules", "preview", "--pattern", "TEA", "--category", "dining")
    assert (result.exit_code, result.stdout) == (
        0,
        "This rule would put no transactions in Dining.\n",
    )


def test_a_refused_preview(card: Settings) -> None:
    result = run("rules", "preview", "--pattern", "acme", "--match", "like", "--category", "Dining")
    assert failed_cleanly(result, "match must be one of: contains, starts_with, equals")
