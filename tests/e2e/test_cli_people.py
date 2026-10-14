from datetime import date

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, TransactionRow

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
ACCOUNT_HEADINGS = ["Name", "Institution", "Type", "Last 4", "Active", "Owner"]
TRANSACTION_HEADINGS = ["Date", "Account", "Description", "Amount", "Card", "Section", "Person"]
PEOPLE_HEADINGS = ["Name", "Owns", "Cardholder names"]


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def failed_cleanly(result, message: str) -> bool:
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    """Three accounts (Test Card, Test Checking, Test Savings), and no people yet."""
    assert run("db", "upgrade").exit_code == 0
    for name, kind in (
        ("Test Card", "credit_card"),
        ("Test Checking", "checking"),
        ("Test Savings", "savings"),
    ):
        assert (
            run(
                "accounts", "add", "--name", name, "--institution", "Test Bank", "--type", kind
            ).exit_code
            == 0
        )
    return tmp_settings


@pytest.fixture
def household(migrated: Settings) -> Settings:
    """Alex owns the card, the checking account is joint, and SAM DOE on statements is Sam."""
    assert run("people", "add", "--name", "Alex").exit_code == 0
    assert run("people", "add", "--name", "Sam").exit_code == 0
    assert run("accounts", "set-owner", "--account", "Test Card", "--owner", "Alex").exit_code == 0
    assert (
        run("accounts", "set-owner", "--account", "Test Checking", "--owner", "joint").exit_code
        == 0
    )
    assert run("people", "alias", "--person", "Sam", "--cardholder", "Sam Doe").exit_code == 0
    engine = get_engine(migrated.effective_database_url)
    with session_scope(engine) as session:
        for account_id, day, cents, cardholder in (
            (3, 9, 1000, None),
            (1, 8, -800, "SAM DOE"),
            (2, 7, -700, None),
            (1, 6, -600, "PAT DOE"),
        ):
            session.add(
                TransactionRow(
                    account_id=account_id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=f"ACME {day}",
                    cardholder=cardholder,
                    source="statement",
                    fingerprint=f"{day}".ljust(64, "x"),
                )
            )
    engine.dispose()
    return migrated


# ----- fin people -----


def test_add_people(migrated: Settings) -> None:
    result = run("people", "add", "--name", "  Alex ")
    assert (result.exit_code, result.stdout) == (0, 'Added person "Alex" (id 1)\n')
    assert run("people", "add", "--name", "Sam").stdout == 'Added person "Sam" (id 2)\n'


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("alex", "a person with this name already exists"),
        ("Joint", "joint and unassigned are reserved names"),
        ("unassigned", "joint and unassigned are reserved names"),
        ("   ", "a person's name must be 1 to 100 characters"),
        ("x" * 101, "a person's name must be 1 to 100 characters"),
    ],
)
def test_names_that_cannot_be_added(migrated: Settings, name: str, message: str) -> None:
    assert run("people", "add", "--name", "Alex").exit_code == 0
    assert failed_cleanly(run("people", "add", "--name", name), message)


def test_people_list(household: Settings) -> None:
    assert run("people", "alias", "--person", "sam", "--cardholder", "S DOE").exit_code == 0
    assert (
        run("accounts", "set-owner", "--account", "Test Savings", "--owner", "Alex").exit_code == 0
    )
    result = run("people", "list")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        PEOPLE_HEADINGS,
        ["Alex", "Test Card, Test Savings", ""],
        ["Sam", "", "S DOE, SAM DOE"],
    ]


def test_people_list_includes_closed_accounts(household: Settings) -> None:
    engine = get_engine(household.effective_database_url)
    with session_scope(engine) as session:
        session.scalars(
            select(AccountRow).where(AccountRow.name == "Test Card")
        ).one().is_active = False
    engine.dispose()
    assert table_rows(run("people", "list").stdout)[1] == ["Alex", "Test Card", ""]


def test_people_list_with_nobody(migrated: Settings) -> None:
    assert run("people", "list").stdout == "No people.\n"


def test_alias(migrated: Settings) -> None:
    assert run("people", "add", "--name", "Sam").exit_code == 0
    result = run("people", "alias", "--person", " SAM ", "--cardholder", "  sam   q doe ")
    assert (result.exit_code, result.stdout) == (0, 'Cardholder "SAM Q DOE" is Sam.\n')
    assert run("people", "add", "--name", "Pat").exit_code == 0
    moved = run("people", "alias", "--person", "Pat", "--cardholder", "SAM Q DOE")
    assert moved.stdout == 'Cardholder "SAM Q DOE" is Pat.\n'
    assert table_rows(run("people", "list").stdout)[1:] == [
        ["Pat", "", "SAM Q DOE"],
        ["Sam", "", ""],
    ]


def test_alias_refusals(migrated: Settings) -> None:
    assert failed_cleanly(
        run("people", "alias", "--person", "Nobody", "--cardholder", "X"), "person not found"
    )
    assert run("people", "add", "--name", "Sam").exit_code == 0
    assert failed_cleanly(
        run("people", "alias", "--person", "Sam", "--cardholder", "   "),
        "a cardholder name must be 1 to 100 characters",
    )
    assert failed_cleanly(
        run("people", "alias", "--person", "Sam", "--cardholder", "X" * 101),
        "a cardholder name must be 1 to 100 characters",
    )


# ----- fin accounts -----


def test_set_owner_and_list_accounts(household: Settings) -> None:
    result = run("accounts", "list")
    assert table_rows(result.stdout) == [
        ACCOUNT_HEADINGS,
        ["Test Card", "Test Bank", "credit_card", "", "yes", "Alex"],
        ["Test Checking", "Test Bank", "checking", "", "yes", "Joint"],
        ["Test Savings", "Test Bank", "savings", "", "yes", ""],
    ]
    changed = run("accounts", "set-owner", "--account", "test card", "--owner", "JOINT")
    assert (changed.exit_code, changed.stdout) == (0, 'Owner of "Test Card" is Joint.\n')
    changed = run("accounts", "set-owner", "--account", "Test Checking", "--owner", " sam ")
    assert changed.stdout == 'Owner of "Test Checking" is Sam.\n'
    assert [row[5] for row in table_rows(run("accounts", "list").stdout)[1:]] == [
        "Joint",
        "Sam",
        "",
    ]


def test_set_owner_refusals(household: Settings) -> None:
    assert failed_cleanly(
        run("accounts", "set-owner", "--account", "Nope", "--owner", "Alex"), "account not found"
    )
    assert failed_cleanly(
        run("accounts", "set-owner", "--account", "Test Card", "--owner", "Nobody"),
        "person not found",
    )


# ----- fin transactions -----


def test_transactions_show_their_person(household: Settings) -> None:
    result = run("transactions", "list")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        TRANSACTION_HEADINGS,
        ["2026-05-09", "Test Savings", "ACME 9", "$10.00", "", "", ""],
        ["2026-05-08", "Test Card", "ACME 8", "-$8.00", "", "", "Sam"],
        ["2026-05-07", "Test Checking", "ACME 7", "-$7.00", "", "", "Joint"],
        ["2026-05-06", "Test Card", "ACME 6", "-$6.00", "", "", "Alex"],
    ]


@pytest.mark.parametrize(
    ("person", "descriptions"),
    [
        ("alex", ["ACME 6"]),
        ("Sam", ["ACME 8"]),
        ("joint", ["ACME 7"]),
        ("unassigned", ["ACME 9"]),
    ],
)
def test_transactions_of_one_person(
    household: Settings, person: str, descriptions: list[str]
) -> None:
    result = run("transactions", "list", "--person", person)
    assert [row[2] for row in table_rows(result.stdout)[1:]] == descriptions


def test_the_limit_counts_the_persons_rows(household: Settings) -> None:
    result = run("transactions", "list", "--person", "unassigned", "--limit", "1")
    assert [row[2] for row in table_rows(result.stdout)[1:]] == ["ACME 9"]
    result = run("transactions", "list", "--account", "Test Card", "--person", "sam")
    assert [row[2] for row in table_rows(result.stdout)[1:]] == ["ACME 8"]


def test_transactions_of_someone_unknown_or_with_none(household: Settings) -> None:
    assert failed_cleanly(run("transactions", "list", "--person", "Nobody"), "person not found")
    assert run("people", "add", "--name", "Pat").exit_code == 0
    assert run("transactions", "list", "--person", "Pat").stdout == "No transactions.\n"


@pytest.mark.parametrize(
    "command",
    [
        ["people", "add", "--name", "A"],
        ["people", "list"],
        ["people", "alias", "--person", "A", "--cardholder", "B"],
        ["accounts", "set-owner", "--account", "A", "--owner", "B"],
    ],
)
def test_commands_need_a_migrated_database(tmp_settings: Settings, command: list[str]) -> None:
    result = run(*command)
    assert (result.exit_code, result.stderr, result.stdout) == (1, NOT_MIGRATED, "")
