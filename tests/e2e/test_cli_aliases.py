from datetime import date

import pytest

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule
from tests.support import failed_cleanly, run, table_rows


@pytest.fixture
def card(tmp_settings: Settings) -> Settings:
    """ACME CAFE (1) and ACME COFFEE (2) on a card; a rule puts ACME COFFEE in Dining, so 2
    is categorized and 1 is not."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-450, "ACME CAFE"), (-500, "ACME COFFEE")), start=1
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
        create_rule(session, "ACME COFFEE", "Dining")
        categorize(session)
    engine.dispose()
    return tmp_settings


def test_merging_a_merchant(card: Settings) -> None:
    added = run("aliases", "add", "--from", "  acme   cafe ", "--to", "Acme Coffee")
    assert (added.exit_code, added.stdout) == (
        0,
        'Merged "ACME CAFE" into "ACME COFFEE".\n'
        "Categorized 2 transactions: 1 changed, 0 without a category.\n",
    )
    assert table_rows(run("aliases", "list").stdout) == [
        ["From", "To"],
        ["ACME CAFE", "ACME COFFEE"],
    ]


def test_removing_it(card: Settings) -> None:
    run("aliases", "add", "--from", "ACME CAFE", "--to", "ACME COFFEE")
    removed = run("aliases", "delete", "--from", "acme cafe")
    assert (removed.exit_code, removed.stdout) == (
        0,
        'Removed the alias for "ACME CAFE".\n'
        "Categorized 2 transactions: 1 changed, 1 without a category.\n",
    )
    assert run("aliases", "list").stdout == "No aliases.\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("add", "--from", " ", "--to", "BAZ CAFE"), "a merchant name must be 1 to 100 characters"),
        (
            ("add", "--from", "acme cafe", "--to", "Acme Cafe"),
            "a merchant cannot be merged into itself",
        ),
        (
            ("add", "--from", "acme cafe", "--to", "BAZ CAFE"),
            "this merchant is already merged into another",
        ),
        (
            ("add", "--from", "BAZ CAFE", "--to", "ACME CAFE"),
            "the merchant to merge into is itself merged into another",
        ),
        (
            ("add", "--from", "ACME COFFEE", "--to", "BAZ CAFE"),
            "other merchants are merged into this one",
        ),
        (("delete", "--from", "BAZ CAFE"), "alias not found"),
    ],
)
def test_refused(card: Settings, args: tuple[str, ...], message: str) -> None:
    run("aliases", "add", "--from", "ACME CAFE", "--to", "ACME COFFEE")
    assert failed_cleanly(run("aliases", *args), message)
