from datetime import date

import pytest

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule
from tests.support import failed_cleanly, run, table_rows

PARTS = ("--part", "12.00 groceries", "--part", "$8 Home & Garden")


@pytest.fixture
def card(tmp_settings: Settings) -> Settings:
    """-$20.00 at FOOBAR GROCERY (1) with no category; -$5.00 at ACME COFFEE (2) put in
    Coffee & Dessert by a rule."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-2000, "FOOBAR GROCERY"), (-500, "ACME COFFEE")), start=1
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
        session.flush()
        create_rule(session, "ACME", "Coffee & Dessert")
        categorize(session)
    engine.dispose()
    return tmp_settings


def test_splitting(card: Settings) -> None:
    result = run("transactions", "split", "--id", "1", *PARTS)
    assert (result.exit_code, result.stdout) == (0, "Transaction 1: split into 2 parts.\n")
    assert table_rows(run("transactions", "parts", "--id", "1").stdout) == [
        ["Part", "Amount", "Category"],
        ["1", "-$12.00", "Groceries"],
        ["2", "-$8.00", "Home & Garden"],
    ]


def test_unsplitting(card: Settings) -> None:
    run("transactions", "split", "--id", "1", *PARTS)
    result = run("transactions", "unsplit", "--id", "1")
    assert (result.exit_code, result.stdout) == (
        0,
        "Transaction 1: split removed.\n"
        "Categorized 2 transactions: 0 changed, 1 without a category.\n",
    )
    assert run("transactions", "parts", "--id", "1").stdout == "Transaction 1 is not split.\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ("split", "--id", "1", "--part", "12.00 Groceries", "--part", "9.00 Dining"),
            "the parts must add up to the transaction",
        ),
        (
            ("split", "--id", "1", "--part", "12.00", "--part", "8.00 Dining"),
            "a part is a size and a category, such as 12.00 Groceries",
        ),
        (
            ("split", "--id", "1", "--part", "twelve Groceries", "--part", "8.00 Dining"),
            "invalid money text",
        ),
        (
            ("split", "--id", "1", "--part", "-12.00 Groceries", "--part", "8.00 Dining"),
            "each part's size must be more than zero",
        ),
        (("split", "--id", "9", *PARTS), "transaction not found"),
        (("unsplit", "--id", "2"), "the transaction is not split"),
        (("parts", "--id", "9"), "transaction not found"),
    ],
)
def test_refused(card: Settings, args: tuple[str, ...], message: str) -> None:
    assert failed_cleanly(run("transactions", *args), message)
