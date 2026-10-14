from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, TransactionRow

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
STATEMENT_HEADINGS = ["Account", "File", "Parser", "Period", "Opening", "Closing", "Lines", "New"]
TRANSACTION_HEADINGS = ["Date", "Account", "Description", "Amount", "Card", "Section"]
BULLETS = "••"
CARD_STATEMENT = [
    "Test Card",
    "january.pdf",
    "fake_bank",
    "2026-01-01 to 2026-01-31",
    "-$100.00",
    "-$84.99",
    "4",
    "4",
]
CHECKING_STATEMENT = [
    "Test Checking",
    "checking.pdf",
    "fake_bank",
    "2026-02-01 to 2026-02-28",
    "$1,000.00",
    "$900.00",
    "1",
    "1",
]
RENT = ["2026-02-10", "Test Checking", "ACME RENT", "-$100.00", "", "withdrawals"]
PAYMENT = ["2026-01-20", "Test Card", "PAYMENT THANK YOU", "$50.00", "", "payments_credits"]
GROCERY = ["2026-01-06", "Test Card", "FOOBAR GROCERY", "-$25.99", BULLETS + "2222", "purchases"]
COFFEE = ["2026-01-05", "Test Card", "ACME COFFEE #12", "-$4.50", BULLETS + "2222", "purchases"]


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    """The cells of one row of a Rich table."""
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    """Every row of a Rich table, heading first."""
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def transaction_rows(output: str) -> list[list[str]]:
    """The first six cells of every row of the transactions table; later phases add columns."""
    return [row[:6] for row in table_rows(output)]


def failed_cleanly(result, message: str) -> bool:
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


@pytest.fixture
def migrated(tmp_settings: Settings, fake_bank) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    card = ["--name", "Test Card", "--institution", "Fake Bank", "--type", "credit_card"]
    checking = ["--name", "Test Checking", "--institution", "Fake Bank", "--type", "checking"]
    assert run("accounts", "add", *card, "--last4", "1111").exit_code == 0
    assert run("accounts", "add", *checking, "--last4", "2222").exit_code == 0
    return tmp_settings


@pytest.fixture
def imported(migrated: Settings, tmp_path: Path, fake_statement_pdf) -> Settings:
    january = tmp_path / "january.pdf"
    january.write_bytes(fake_statement_pdf())
    checking = tmp_path / "checking.pdf"
    checking.write_bytes(
        fake_statement_pdf(
            last4="2222",
            account_type="checking",
            start="2026-02-01",
            end="2026-02-28",
            opening="1000.00",
            closing="900.00",
            rows=("2026-02-10|-|withdrawals|-100.00|-|-|ACME RENT",),
        )
    )
    assert run("import", "statement", january).exit_code == 0
    assert run("import", "statement", checking).exit_code == 0
    return migrated


def test_statements_list_newest_period_first(imported: Settings) -> None:
    result = run("statements", "list")
    assert result.exit_code == 0
    assert result.stderr == ""
    assert table_rows(result.stdout) == [STATEMENT_HEADINGS, CHECKING_STATEMENT, CARD_STATEMENT]


def test_statements_list_for_one_account(imported: Settings) -> None:
    result = run("statements", "list", "--account", " test card ")
    assert table_rows(result.stdout) == [STATEMENT_HEADINGS, CARD_STATEMENT]


def test_statements_list_when_there_are_none(migrated: Settings) -> None:
    result = run("statements", "list")
    assert result.exit_code == 0
    assert result.stdout == "No statements.\n"
    assert run("statements", "list", "--account", "Test Card").stdout == "No statements.\n"


def test_transactions_list_newest_first(imported: Settings) -> None:
    result = run("transactions", "list")
    assert result.exit_code == 0
    assert result.stderr == ""
    assert transaction_rows(result.stdout) == [
        TRANSACTION_HEADINGS,
        RENT,
        PAYMENT,
        GROCERY,
        COFFEE,
        COFFEE,
    ]


def test_transactions_list_for_one_account(imported: Settings) -> None:
    result = run("transactions", "list", "--account", "TEST CHECKING")
    assert transaction_rows(result.stdout) == [TRANSACTION_HEADINGS, RENT]


def test_transactions_list_between_two_dates(imported: Settings) -> None:
    result = run("transactions", "list", "--from", "2026-01-06", "--to", "2026-01-20")
    assert transaction_rows(result.stdout) == [TRANSACTION_HEADINGS, PAYMENT, GROCERY]


def test_transactions_list_from_or_to_alone(imported: Settings) -> None:
    after = run("transactions", "list", "--from", "2026-01-20")
    assert transaction_rows(after.stdout) == [TRANSACTION_HEADINGS, RENT, PAYMENT]
    before = run("transactions", "list", "--to", "2026-01-05")
    assert transaction_rows(before.stdout) == [TRANSACTION_HEADINGS, COFFEE, COFFEE]


def test_transactions_list_limit(imported: Settings) -> None:
    result = run("transactions", "list", "--limit", "2")
    assert transaction_rows(result.stdout) == [TRANSACTION_HEADINGS, RENT, PAYMENT]


def test_transactions_list_shows_fifty_by_default(
    migrated: Settings, tmp_path: Path, fake_statement_pdf
) -> None:
    rows = tuple(f"2026-01-{1 + n % 28:02d}|-|purchases|-1.00|-|-|ACME ITEM {n}" for n in range(60))
    path = tmp_path / "many.pdf"
    path.write_bytes(fake_statement_pdf(closing="-160.00", rows=rows))
    assert run("import", "statement", path).exit_code == 0
    assert len(table_rows(run("transactions", "list").stdout)) == 51
    assert len(table_rows(run("transactions", "list", "--limit", "60").stdout)) == 61


def test_transactions_list_when_there_are_none(imported: Settings) -> None:
    result = run("transactions", "list", "--from", "2027-01-01")
    assert result.exit_code == 0
    assert result.stdout == "No transactions.\n"


def test_lists_still_name_an_account_that_was_closed(imported: Settings) -> None:
    engine = get_engine(imported.effective_database_url)
    with session_scope(engine) as session:
        session.scalars(
            select(AccountRow).where(AccountRow.name == "Test Card")
        ).one().is_active = False
    engine.dispose()
    assert table_rows(run("statements", "list").stdout)[2] == CARD_STATEMENT
    assert transaction_rows(run("transactions", "list").stdout)[2] == PAYMENT


def test_transactions_list_leaves_a_missing_card_and_section_empty(imported: Settings) -> None:
    engine = get_engine(imported.effective_database_url)
    with session_scope(engine) as session:
        session.add(
            TransactionRow(
                account_id=2,
                posted_date=date(2026, 3, 1),
                amount_cents=123456,
                description="ACME PAYROLL",
                source="aggregator",
                fingerprint="f" * 64,
            )
        )
    engine.dispose()
    rows = transaction_rows(run("transactions", "list", "--limit", "1").stdout)
    assert rows[1] == ["2026-03-01", "Test Checking", "ACME PAYROLL", "$1,234.56", "", ""]


@pytest.mark.parametrize("command", ["statements", "transactions"])
def test_an_unknown_account_is_an_error(imported: Settings, command: str) -> None:
    assert failed_cleanly(run(command, "list", "--account", "Nobody"), "account not found")


@pytest.mark.parametrize(
    "options",
    [
        ["--limit", "0"],
        ["--limit", "-3"],
        ["--limit", "ten"],
        ["--from", "01/06/2026"],
        ["--to", "soon"],
    ],
)
def test_transactions_list_rejects_bad_options(imported: Settings, options: list[str]) -> None:
    assert run("transactions", "list", *options).exit_code == 2


@pytest.mark.parametrize("command", ["statements", "transactions"])
def test_list_commands_need_a_migrated_database(tmp_settings: Settings, command: str) -> None:
    result = run(command, "list")
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.stderr == NOT_MIGRATED
    assert result.stdout == ""


def test_the_program_lists_the_new_command_groups() -> None:
    output = run("--help").stdout
    for name in ("import", "statements", "transactions"):
        assert name in output
