from datetime import date

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
LIST = ["Pair", "Date", "From", "To", "Amount", "Out", "In", "How"]
REVIEW = ["Out", "Out date", "From", "In", "In date", "To", "Amount"]
TO_SAVINGS = ["3", "2026-05-05", "Test Checking", "{}", "2026-05-0{1}", "Test Savings", "$20.00"]


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


def to_savings(in_id: int) -> list[str]:
    return [cell.format(in_id, in_id + 1) for cell in TO_SAVINGS]


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    return tmp_settings


@pytest.fixture
def money(migrated: Settings) -> Settings:
    """1 and 2: a clear card payment. 3 with 4 or 5: unclear. 6 and 7: not transfers."""
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        for number, (account, day, cents, description) in enumerate(
            (
                (checking, 3, -50000, "PAYMENT TO TEST CARD"),
                (card, 4, 50000, "PAYMENT THANK YOU"),
                (checking, 5, -2000, "TRANSFER TO SAVINGS"),
                (savings, 5, 2000, "TRANSFER FROM CHECKING"),
                (savings, 6, 2000, "TRANSFER FROM CHECKING"),
                (card, 6, -1250, "SQ *ACME COFFEE"),
                (savings, 20, 50000, "DEPOSIT EXAMPLE"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number}".ljust(64, "0"),
                )
            )
    engine.dispose()
    return migrated


@pytest.mark.parametrize(
    "args",
    [
        ("list",),
        ("review",),
        ("find",),
        ("confirm", "--out", "1", "--in", "2"),
        ("reject", "--out", "1", "--in", "2"),
        ("unpair", "--pair", "1"),
    ],
)
def test_every_command_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run("transfers", *args)
    assert (result.exit_code, result.stderr) == (1, NOT_MIGRATED)


def test_nothing_yet(money: Settings) -> None:
    assert run("transfers", "list").stdout == "No transfers.\n"
    assert table_rows(run("transfers", "review").stdout) == [REVIEW, to_savings(4), to_savings(5)]


def test_find_pairs_the_clear_ones_and_leaves_the_rest(money: Settings) -> None:
    result = run("transfers", "find")
    assert (result.exit_code, result.stdout) == (0, "Transfers: 1 paired, 2 waiting for review.\n")
    assert table_rows(run("transfers", "list").stdout) == [
        LIST,
        ["1", "2026-05-03", "Test Checking", "Test Card", "$500.00", "1", "2", "auto"],
    ]
    assert table_rows(run("transfers", "review").stdout) == [REVIEW, to_savings(4), to_savings(5)]
    assert [row[0] for row in table_rows(run("uncategorized").stdout)[1:]] == [
        "7",
        "6",
        "5",
        "4",
        "3",
    ]
    assert run("transfers", "find").stdout == "Transfers: 0 paired, 2 waiting for review.\n"


def test_confirm_one_of_the_choices(money: Settings) -> None:
    run("transfers", "find")
    result = run("transfers", "confirm", "--out", "3", "--in", "5")
    assert (result.exit_code, result.stdout) == (0, "Transactions 3 and 5 are now a transfer.\n")
    assert run("transfers", "review").stdout == "No transfers wait for review.\n"
    assert table_rows(run("transfers", "list").stdout)[1:] == [
        ["2", "2026-05-05", "Test Checking", "Test Savings", "$20.00", "3", "5", "confirmed"],
        ["1", "2026-05-03", "Test Checking", "Test Card", "$500.00", "1", "2", "auto"],
    ]
    assert run("transfers", "find").stdout == "Transfers: 0 paired, 0 waiting for review.\n"


def test_a_rejected_choice_makes_the_other_clear(money: Settings) -> None:
    result = run("transfers", "reject", "--out", "3", "--in", "4")
    assert (result.exit_code, result.stdout) == (0, "Transactions 3 and 4 will not be paired.\n")
    assert run("transfers", "review").stdout == "No transfers wait for review.\n"
    assert run("transfers", "find").stdout == "Transfers: 2 paired, 0 waiting for review.\n"


def test_an_unpaired_transfer_is_not_paired_again(money: Settings) -> None:
    run("transfers", "find")
    result = run("transfers", "unpair", "--pair", "1")
    assert (result.exit_code, result.stdout) == (
        0,
        "Transfer 1 removed; transactions 1 and 2 will not be paired again.\n",
    )
    assert run("transfers", "list").stdout == "No transfers.\n"
    assert run("transfers", "find").stdout == "Transfers: 0 paired, 2 waiting for review.\n"
    assert run("transfers", "list").stdout == "No transfers.\n"


def test_rejecting_a_transfer_removes_it(money: Settings) -> None:
    run("transfers", "find")
    assert run("transfers", "reject", "--out", "1", "--in", "2").exit_code == 0
    assert run("transfers", "list").stdout == "No transfers.\n"
    assert run("transfers", "find").stdout == "Transfers: 0 paired, 2 waiting for review.\n"


def test_categorizing_also_pairs_quietly(money: Settings) -> None:
    result = run("categorize")
    assert result.stdout == "Categorized 7 transactions: 0 changed, 7 without a category.\n"
    assert [row[-1] for row in table_rows(run("transfers", "list").stdout)] == ["How", "auto"]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("confirm", "--out", "99", "--in", "2"), "transaction not found"),
        (("confirm", "--out", "1", "--in", "3"), "a transfer goes from one account to another"),
        (
            ("confirm", "--out", "2", "--in", "1"),
            "a transfer pairs money out with the same amount in",
        ),
        (
            ("confirm", "--out", "6", "--in", "4"),
            "a transfer pairs money out with the same amount in",
        ),
        (("confirm", "--out", "1", "--in", "7"), "transaction 1 is already in a transfer"),
        (("reject", "--out", "1", "--in", "99"), "transaction not found"),
        (("unpair", "--pair", "9"), "transfer not found"),
    ],
)
def test_a_refused_command(money: Settings, args, message: str) -> None:
    run("transfers", "find")
    assert failed_cleanly(run("transfers", *args), message)
