from datetime import date

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_person, set_account_owner

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
MAY = ("--month", "2026-05")


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def plain_lines(output: str) -> list[str]:
    return [
        line
        for line in output.splitlines()
        if line and not line.startswith(("│", "┃", "┏", "┡", "└"))
    ]


def failed_cleanly(result, message: str) -> bool:
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    return tmp_settings


@pytest.fixture
def money(migrated: Settings) -> Settings:
    """A month of synthetic money; see each row's note. Rules and pairing run through the CLI."""
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Example Card Co", "credit_card")
        pat = create_person(session, "Pat Example")
        set_account_owner(session, card.id, pat.id)
        rows = (
            # account, posted, transaction date, cents, description, card, pending
            (card, 2, None, -450, "SQ *ACME COFFEE", "1111", False),
            (card, 3, None, -2599, "FOOBAR GROCERY #77", "1111", False),
            (card, 10, None, 599, "FOOBAR GROCERY #77", "1111", False),  # a refund
            (card, 32, 31, -1250, "ACME COFFEE #12", None, False),  # posted 1 June, bought 31 May
            (card, 1, 0, -800, "BAZ BOOKS", None, False),  # posted 1 May, bought 30 April
            (checking, 20, None, -50000, "PAYMENT TO TEST CARD", None, False),  # a transfer
            (card, 21, None, 50000, "PAYMENT THANK YOU", None, False),  # its other side
            (checking, 15, None, 300000, "PAYCHECK EXAMPLE CORP", None, False),  # income
            (checking, 16, None, 2500, "VENMO CASHOUT", None, False),  # money in, no category
            (card, 18, None, -999, "QUUX STREAMING", None, True),  # pending
            (checking, 25, None, -12000, "ACME UTILITY", None, False),
            (card, 12, None, -1500, "BAZ BOOKS", None, False),  # spending, no category
        )
        for number, (account, posted, bought, cents, description, last4, pending) in enumerate(
            rows, start=1
        ):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=_day(posted),
                    transaction_date=None if bought is None else _day(bought),
                    amount_cents=cents,
                    description=description,
                    card_last4=last4,
                    is_pending=pending,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    for pattern, category in (
        ("ACME COFFEE", "Coffee & Dessert"),
        ("FOOBAR GROCERY", "Groceries"),
        ("PAYCHECK", "Paycheck"),
        ("ACME UTILITY", "Utilities & Internet"),
    ):
        assert run("rules", "add", "--pattern", pattern, "--category", category).exit_code == 0
    return migrated


def _day(number: int) -> date:
    """Day numbers count from 1 May 2026: 0 is 30 April, 32 is 1 June."""
    return date.fromordinal(date(2026, 4, 30).toordinal() + number)


@pytest.mark.parametrize("args", [(), MAY, ("--by", "merchant")])
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run("spending", *args)
    assert (result.exit_code, result.stderr) == (1, NOT_MIGRATED)


def test_a_month_by_category(money: Settings) -> None:
    result = run("spending", *MAY)
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        ["Category", "Spent", "Count"],
        ["Utilities & Internet", "$120.00", "1"],
        ["Groceries", "$20.00", "2"],
        ["Coffee & Dessert", "$17.00", "2"],
        ["Uncategorized", "$15.00", "1"],
    ]
    assert plain_lines(result.stdout) == [
        "Spending from 2026-05-01 to 2026-05-31, by category.",
        "Spent: $172.00. Income: $3,000.00.",
        "Transfers left out: 2.",
        "Money in without a category: $25.00 (count: 1).",
    ]


@pytest.mark.parametrize(
    ("by", "rows"),
    [
        (
            "group",
            [
                ["Group", "Spent", "Count"],
                ["Home", "$120.00", "1"],
                ["Food", "$37.00", "4"],
                ["Uncategorized", "$15.00", "1"],
            ],
        ),
        (
            "merchant",
            [
                ["Merchant", "Spent", "Count"],
                ["ACME UTILITY", "$120.00", "1"],
                ["FOOBAR GROCERY", "$20.00", "2"],
                ["ACME COFFEE", "$17.00", "2"],
                ["BAZ BOOKS", "$15.00", "1"],
            ],
        ),
        (
            "person",
            [
                ["Person", "Spent", "Count"],
                ["Unassigned", "$120.00", "1"],
                ["Pat Example", "$52.00", "5"],
            ],
        ),
        (
            "account",
            [
                ["Account", "Spent", "Count"],
                ["Test Checking", "$120.00", "1"],
                ["Test Card", "$52.00", "5"],
            ],
        ),
        (
            "bank",
            [
                ["Bank", "Spent", "Count"],
                ["Test Bank", "$120.00", "1"],
                ["Example Card Co", "$52.00", "5"],
            ],
        ),
        (
            "card",
            [
                ["Card", "Spent", "Count"],
                ["No card", "$147.50", "3"],
                ["1111", "$24.50", "3"],
            ],
        ),
    ],
)
def test_a_month_by_another_field(money: Settings, by: str, rows: list[list[str]]) -> None:
    result = run("spending", *MAY, "--by", by)
    assert table_rows(result.stdout) == rows
    assert plain_lines(result.stdout)[0] == f"Spending from 2026-05-01 to 2026-05-31, by {by}."


def test_the_day_bought_decides_the_month(money: Settings) -> None:
    result = run("spending", "--month", "2026-04")
    assert table_rows(result.stdout) == [
        ["Category", "Spent", "Count"],
        ["Uncategorized", "$8.00", "1"],
    ]
    assert plain_lines(result.stdout) == [
        "Spending from 2026-04-01 to 2026-04-30, by category.",
        "Spent: $8.00. Income: $0.00.",
        "Transfers left out: 0.",
    ]
    result = run("spending", "--month", "2026-06")
    assert result.stdout == (
        "Spending from 2026-06-01 to 2026-06-30, by category.\n"
        "No spending.\n"
        "Spent: $0.00. Income: $0.00.\n"
        "Transfers left out: 0.\n"
    )


def test_a_range_where_refunds_win(money: Settings) -> None:
    result = run("spending", "--from", "2026-05-10", "--to", "2026-05-20")
    assert table_rows(result.stdout) == [
        ["Category", "Spent", "Count"],
        ["Uncategorized", "$15.00", "1"],
        ["Groceries", "-$5.99", "1"],
    ]
    assert plain_lines(result.stdout) == [
        "Spending from 2026-05-10 to 2026-05-20, by category.",
        "Spent: $9.01. Income: $3,000.00.",
        "Transfers left out: 1.",
        "Money in without a category: $25.00 (count: 1).",
    ]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--month", "2026-13"), "month must be a year and month, like 2026-05"),
        (
            ("--month", "2026-05", "--from", "2026-05-01"),
            "give --month, or --from and --to, not both",
        ),
        (("--from", "2026-05-01"), "give both --from and --to"),
        (("--to", "2026-05-01"), "give both --from and --to"),
        (("--from", "2026-05-20", "--to", "2026-05-10"), "the start date is after the end date"),
        (
            ("--month", "2026-05", "--by", "vendor"),
            "by must be one of: category, group, merchant, person, account, bank, card",
        ),
    ],
)
def test_a_refused_report(money: Settings, args, message: str) -> None:
    assert failed_cleanly(run("spending", *args), message)
