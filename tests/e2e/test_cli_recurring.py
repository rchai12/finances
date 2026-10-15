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
HEADINGS = ["Merchant", "Every", "Amount", "Monthly", "Count", "Last", "Next", "Active"]
STREAMING = ["QUUX STREAMING", "month", "$15.99", "$15.99", "4", "2026-04-05", "2026-05-05", "yes"]
APPS_999 = ["FOOBAR APPS", "month", "$9.99", "$9.99", "4", "2026-04-20", "2026-05-20", "yes"]
APPS_299 = ["FOOBAR APPS", "month", "$2.99", "$2.99", "4", "2026-04-03", "2026-05-03", "yes"]
OLD_GYM = ["OLD GYM", "month", "$25.00", "$25.00", "3", "2025-12-01", "2026-01-01", "no"]


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def plain_lines(output: str) -> list[str]:
    tables = ("│", "┃", "┏", "┡", "└")
    return [line for line in output.splitlines() if line and not line.startswith(tables)]


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    return tmp_settings


@pytest.fixture
def money(migrated: Settings) -> Settings:
    """Three subscriptions on the card, one that stopped, coffee at no set rhythm, and a monthly
    card payment from checking that is a transfer, not a subscription."""
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Example Card Co", "credit_card")
        rows = []
        for month in (1, 2, 3, 4):
            rows.append((card, date(2026, month, 5), -1599, "QUUX STREAMING"))
            rows.append((card, date(2026, month, 3), -299, "FOOBAR APPS"))
            rows.append((card, date(2026, month, 20), -999, "FOOBAR APPS"))
        for month in (1, 2, 3):
            rows.append((checking, date(2026, month, 20), -50000, "PAYMENT TO TEST CARD"))
            rows.append((card, date(2026, month, 21), 50000, "PAYMENT THANK YOU"))
        for year, month in ((2025, 10), (2025, 11), (2025, 12)):
            rows.append((card, date(year, month, 1), -2500, "OLD GYM"))
        for day in (2, 9, 30):
            rows.append((card, date(2026, 1, day), -450, "ACME COFFEE"))
        for number, (account, day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    assert run("transfers", "find").stdout == "Transfers: 3 paired, 0 waiting for review.\n"
    return migrated


@pytest.mark.parametrize("args", [(), ("--all",), ("--as-of", "2026-05-01")])
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run("recurring", *args)
    assert (result.exit_code, result.stderr) == (1, NOT_MIGRATED)


def test_nothing_recurring(migrated: Settings) -> None:
    result = run("recurring", "--as-of", "2026-05-01")
    assert (result.exit_code, result.stdout) == (
        0,
        "No recurring charges.\nRecurring: 0 active, $0.00 a month.\n",
    )


def test_the_active_subscriptions(money: Settings) -> None:
    result = run("recurring", "--as-of", "2026-05-01")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [HEADINGS, STREAMING, APPS_999, APPS_299]
    assert plain_lines(result.stdout) == ["Recurring: 3 active, $28.97 a month."]


def test_all_includes_the_ones_that_stopped(money: Settings) -> None:
    result = run("recurring", "--as-of", "2026-05-01", "--all")
    assert table_rows(result.stdout) == [HEADINGS, STREAMING, APPS_999, APPS_299, OLD_GYM]
    assert plain_lines(result.stdout) == ["Recurring: 3 active, $28.97 a month."]


def test_only_what_happened_by_the_day_counts(money: Settings) -> None:
    result = run("recurring", "--as-of", "2026-02-10")
    assert result.stdout == "No recurring charges.\nRecurring: 0 active, $0.00 a month.\n"
    result = run("recurring", "--as-of", "2026-02-10", "--all")
    assert table_rows(result.stdout) == [HEADINGS, OLD_GYM]


def test_a_day_that_is_not_one(money: Settings) -> None:
    result = run("recurring", "--as-of", "2026-02-30")
    assert result.exit_code == 2
    assert "'--as-of'" in result.stderr
