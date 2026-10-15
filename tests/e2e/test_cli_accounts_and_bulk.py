from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, list_categories, list_category_assignments
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, run, table_rows

LINE = "Categorized 4 transactions: {} changed, {} without a category."


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    """Card: 1 and 2 coffee, 3 groceries; checking: 4 a paycheck. Rule 1 ACME COFFEE to
    Coffee & Dessert, rule 2 FOOBAR to Groceries; 4 is set to Dining by hand."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        for number, (account, cents, description) in enumerate(
            (
                (card, -450, "SQ *ACME COFFEE"),
                (card, -500, "ACME COFFEE #12"),
                (card, -2599, "FOOBAR GROCERY #77"),
                (checking, 300000, "PAYCHECK EXAMPLE CORP"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, number),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    assert (
        run("rules", "add", "--pattern", "ACME COFFEE", "--category", "Coffee & Dessert").exit_code
        == 0
    )
    assert run("rules", "add", "--pattern", "FOOBAR", "--category", "Groceries").exit_code == 0
    assert run("transactions", "set-category", "--id", "4", "--category", "Dining").exit_code == 0
    return tmp_settings


def categories_of() -> dict[int, str]:
    """Each categorized transaction's category name."""
    engine = get_engine()
    with session_scope(engine) as session:
        names = {category.id: category.name for category in list_categories(session)}
        found = {
            transaction_id: names[assignment.category_id]
            for transaction_id, assignment in list_category_assignments(session).items()
        }
    engine.dispose()
    return found


@pytest.mark.parametrize(
    "args",
    [
        ("accounts", "rename", "--account", "Test Card", "--to", "Family Card"),
        ("accounts", "deactivate", "--account", "Test Card"),
        ("accounts", "activate", "--account", "Test Card"),
    ],
)
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run(*args)
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


# Accounts


def test_rename_close_and_reopen_an_account(money: Settings) -> None:
    result = run("accounts", "rename", "--account", "test card", "--to", " Family Card ")
    assert (result.exit_code, result.stdout) == (
        0,
        'Renamed account "Test Card" to "Family Card".\n',
    )
    assert run("accounts", "deactivate", "--account", "family card").stdout == (
        'Account "Family Card" is closed.\n'
    )
    assert [row[0] for row in table_rows(run("accounts", "list").stdout)[1:]] == ["Test Checking"]
    assert run("accounts", "activate", "--account", "Family Card").stdout == (
        'Account "Family Card" is open again.\n'
    )
    assert [row[0] for row in table_rows(run("accounts", "list").stdout)[1:]] == [
        "Family Card",
        "Test Checking",
    ]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("rename", "--account", "Nope", "--to", "Other"), "account not found"),
        (
            ("rename", "--account", "Test Card", "--to", "test checking"),
            "an account with this name already exists",
        ),
        (("rename", "--account", "Test Card", "--to", "  "), "account name must not be empty"),
        (
            ("rename", "--account", "Test Card", "--to", "N" * 101),
            "account name must be at most 100 characters",
        ),
        (("deactivate", "--account", "Nope"), "account not found"),
        (("activate", "--account", "Nope"), "account not found"),
    ],
)
def test_a_refused_account_change(money: Settings, args, message: str) -> None:
    assert failed_cleanly(run("accounts", *args), message)


# Several transactions at once


def test_set_and_clear_several_transactions(money: Settings) -> None:
    result = run(
        "transactions",
        "set-category",
        "--id",
        "1",
        "--id",
        "3",
        "--id",
        "1",
        "--category",
        "dining",
    )
    assert (result.exit_code, result.stdout) == (0, "2 transactions: Dining, set by hand.\n")
    assert categories_of() == {1: "Dining", 2: "Coffee & Dessert", 3: "Dining", 4: "Dining"}
    result = run("transactions", "set-category", "--id", "1", "--id", "3", "--clear")
    assert (
        result.stdout == "2 transactions: category left to the rules.\n" + LINE.format(2, 0) + "\n"
    )
    assert categories_of() == {
        1: "Coffee & Dessert",
        2: "Coffee & Dessert",
        3: "Groceries",
        4: "Dining",
    }


def test_an_unknown_id_changes_none_of_them(money: Settings) -> None:
    result = run("transactions", "set-category", "--id", "99", "--id", "1", "--category", "Dining")
    assert failed_cleanly(result, "transaction not found")
    assert categories_of()[1] == "Coffee & Dessert"
