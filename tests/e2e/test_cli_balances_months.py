from datetime import UTC, date, datetime

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import FeedPullRow, TransactionRow
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    create_statement,
    set_balance_snapshot,
)
from finances.domain.models import DataSource

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
BALANCES = ["Account", "Type", "Balance", "As of", "From"]
MONTHS = ["Month", "Spent", "Income", "Change", "Covered"]


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def plain_lines(output: str) -> list[str]:
    tables = ("│", "┃", "┏", "┡", "└")
    return [line for line in output.splitlines() if line and not line.startswith(tables)]


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


def statement(session, account, number: int, start: date, end: date, closing: int) -> None:
    create_statement(
        session,
        account_id=account.id,
        source_filename=f"statement-{number}.pdf",
        file_sha256=f"s{number:02d}".ljust(64, "0"),
        parser_name="test",
        period_start=start,
        period_end=end,
        opening_balance_cents=0,
        closing_balance_cents=closing,
        lines_parsed=0,
        rows_inserted=0,
        rows_duplicate=0,
    )
    add_balance_snapshot(session, account.id, end, closing, DataSource.STATEMENT)


@pytest.fixture
def money(migrated: Settings) -> Settings:
    """Checking: statements for March and April. Card: one statement from 5 March to 4 April,
    then a SimpleFIN pull on 20 May. Savings: a quarterly statement, March to May."""
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Example Card Co", "credit_card")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        statement(session, checking, 1, date(2026, 3, 1), date(2026, 3, 31), 250000)
        statement(session, checking, 2, date(2026, 4, 1), date(2026, 4, 30), 310000)
        statement(session, card, 3, date(2026, 3, 5), date(2026, 4, 4), -45000)
        statement(session, savings, 4, date(2026, 3, 1), date(2026, 5, 31), 1000000)
        set_balance_snapshot(session, card.id, date(2026, 5, 20), -61234, DataSource.AGGREGATOR)
        session.add(
            FeedPullRow(
                account_id=card.id,
                inserted=1,
                updated=0,
                removed=0,
                unchanged=0,
                feed_total_cents=-1500,
                balance_cents=-61234,
                balance_date=date(2026, 5, 20),
                drift_cents=None,
                pulled_at=datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
            )
        )
        for number, (account, day, cents, description) in enumerate(
            (
                (card, date(2026, 3, 10), -2000, "FOOBAR GROCERY"),
                (card, date(2026, 4, 12), -3000, "FOOBAR GROCERY"),
                (card, date(2026, 5, 3), -1500, "BAZ BOOKS"),
                (checking, date(2026, 3, 15), 300000, "PAYCHECK EXAMPLE CORP"),
                (checking, date(2026, 4, 15), 300000, "PAYCHECK EXAMPLE CORP"),
                (checking, date(2026, 4, 25), -12000, "ACME UTILITY"),
            ),
            start=1,
        ):
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
    assert run("rules", "add", "--pattern", "PAYCHECK", "--category", "Paycheck").exit_code == 0
    return migrated


@pytest.mark.parametrize("args", [("balances",), ("months",), ("months", "--to", "2026-05")])
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run(*args)
    assert (result.exit_code, result.stderr) == (1, NOT_MIGRATED)


# Balances


def test_no_accounts(migrated: Settings) -> None:
    assert run("balances").stdout == "No accounts.\n"


def test_balances_and_net_worth(money: Settings) -> None:
    result = run("balances")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        BALANCES,
        ["Test Card", "credit_card", "-$612.34", "2026-05-20", "SimpleFIN"],
        ["Test Checking", "checking", "$3,100.00", "2026-04-30", "statement"],
        ["Test Savings", "savings", "$10,000.00", "2026-05-31", "statement"],
    ]
    assert plain_lines(result.stdout) == [
        "Cash: $13,100.00. Cards: -$612.34. Other: $0.00.",
        "Net worth: $12,487.66.",
    ]


def test_an_account_without_a_balance(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Brokerage", "Test Bank", "other")
    engine.dispose()
    result = run("balances")
    assert table_rows(result.stdout)[1] == ["Test Brokerage", "other", "", "", ""]
    assert plain_lines(result.stdout) == [
        "Cash: $13,100.00. Cards: -$612.34. Other: $0.00.",
        "Net worth: $12,487.66.",
        "No balance yet: Test Brokerage.",
    ]


# Months


def test_three_months(money: Settings) -> None:
    result = run("months", "--to", "2026-05", "--count", "3")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        MONTHS,
        ["2026-03", "$20.00", "$3,000.00", "", "partly"],
        ["2026-04", "$150.00", "$3,000.00", "+$130.00", "yes"],
        ["2026-05", "$15.00", "$0.00", "-$135.00", "partly"],
    ]
    assert plain_lines(result.stdout) == [
        "Months from 2026-03 to 2026-05.",
        "2026-03: no data for the whole month from Test Card.",
        "2026-05: no data for the whole month from Test Card, Test Checking.",
    ]


def test_one_month_and_the_default_count(money: Settings) -> None:
    result = run("months", "--to", "2026-04", "--count", "1")
    assert result.stdout.splitlines()[0] == "Months from 2026-04 to 2026-04."
    assert table_rows(result.stdout) == [MONTHS, ["2026-04", "$150.00", "$3,000.00", "", "yes"]]
    rows = table_rows(run("months", "--to", "2026-05").stdout)
    assert [row[0] for row in rows] == [
        "Month",
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
        "2026-05",
    ]
    assert rows[1] == ["2025-12", "$0.00", "$0.00", "", "partly"]
    assert rows[2][3] == "$0.00"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--to", "2026-13"), "month must be a year and month, like 2026-05"),
        (("--to", "2026-05", "--count", "0"), "count must be from 1 to 24"),
        (("--to", "2026-05", "--count", "25"), "count must be from 1 to 24"),
    ],
)
def test_a_refused_report(money: Settings, args, message: str) -> None:
    assert failed_cleanly(run("months", *args), message)
