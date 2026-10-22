from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    get_account_by_name,
    set_balance_snapshot,
)
from finances.domain.models import DataSource
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, plain_lines, run, table_rows

AS_OF = ("--as-of", "2026-05-25")
HEADINGS = [
    "Account",
    "Balance",
    "As of",
    "Expected in",
    "Expected out",
    "End",
    "Lowest",
    "Lowest on",
]
CARD = [
    "Test Card",
    "-$450.00",
    "2026-05-24",
    "$500.00",
    "-$63.99",
    "-$13.99",
    "-$462.00",
    "2026-05-29",
]
CHECKING = [
    "Test Checking",
    "$300.00",
    "2026-05-24",
    "$6,000.00",
    "-$620.00",
    "$5,680.00",
    "$180.00",
    "2026-05-27",
]
SAVINGS = [
    "Test Savings",
    "$1,000.00",
    "2026-05-24",
    "$1.00",
    "$0.00",
    "$1,001.00",
    "$1,000.00",
    "2026-05-25",
]


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    """Checking: a utility on the 27th, pay every two weeks, a card payment on the 2nd.
    Card: streaming, a weekly box, the payment arriving on the 3rd. Savings: monthly interest.
    Brokerage: no balance."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        create_account(session, "Test Brokerage", "Test Bank", "other")
        set_balance_snapshot(session, checking.id, date(2026, 5, 24), 30000, DataSource.AGGREGATOR)
        set_balance_snapshot(session, card.id, date(2026, 5, 24), -45000, DataSource.AGGREGATOR)
        add_balance_snapshot(session, savings.id, date(2026, 5, 24), 100000, DataSource.STATEMENT)
        rows = [
            *((checking, date(2026, month, 27), -12000, "ACME UTILITY") for month in (2, 3, 4)),
            *(
                (checking, day, 300000, "PAYCHECK EXAMPLE CORP")
                for day in (
                    date(2026, 4, 3),
                    date(2026, 4, 17),
                    date(2026, 5, 1),
                    date(2026, 5, 15),
                )
            ),
            *(
                (checking, date(2026, month, 2), -50000, "PAYMENT TO TEST CARD")
                for month in (3, 4, 5)
            ),
            *((card, date(2026, month, 3), 50000, "PAYMENT THANK YOU") for month in (3, 4, 5)),
            *((card, date(2026, month, 5), -1599, "QUUX STREAMING") for month in (2, 3, 4, 5)),
            *((card, date(2026, 5, day), -1200, "BAZ BOX") for day in (1, 8, 15, 22)),
            *(
                (savings, day, 100, "INTEREST PAID")
                for day in (date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30))
            ),
        ]
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
    for pattern, category in (("PAYCHECK", "Paycheck"), ("INTEREST PAID", "Interest Income")):
        assert run("rules", "add", "--pattern", pattern, "--category", category).exit_code == 0
    return tmp_settings


@pytest.mark.parametrize(
    "args", [("forecast",), ("forecast", *AS_OF), ("forecast", "--account", "X")]
)
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run(*args)
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


def test_every_account(money: Settings) -> None:
    result = run("forecast", *AS_OF)
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [HEADINGS, CARD, CHECKING, SAVINGS]
    assert plain_lines(result.stdout) == [
        "Forecast from 2026-05-25 to 2026-06-23.",
        "No balance yet: Test Brokerage.",
    ]


def test_one_account_day_by_day(money: Settings) -> None:
    result = run("forecast", *AS_OF, "--account", "test checking")
    assert table_rows(result.stdout) == [
        ["Date", "Merchant", "Amount", "Balance"],
        ["2026-05-27", "ACME UTILITY", "-$120.00", "$180.00"],
        ["2026-05-29", "PAYCHECK EXAMPLE CORP", "$3,000.00", "$3,180.00"],
        ["2026-06-02", "PAYMENT TO TEST CARD", "-$500.00", "$2,680.00"],
        ["2026-06-12", "PAYCHECK EXAMPLE CORP", "$3,000.00", "$5,680.00"],
    ]
    assert plain_lines(result.stdout) == [
        "Forecast for Test Checking from 2026-05-25 to 2026-06-23.",
        "Starting balance: $300.00 (as of 2026-05-24).",
        "Lowest: $180.00 on 2026-05-27.",
    ]


def test_a_shorter_window(money: Settings) -> None:
    rows = table_rows(run("forecast", *AS_OF, "--days", "7").stdout)
    assert rows[2] == [
        "Test Checking",
        "$300.00",
        "2026-05-24",
        "$3,000.00",
        "-$120.00",
        "$3,180.00",
        "$180.00",
        "2026-05-27",
    ]


def test_nothing_to_forecast(tmp_settings: Settings) -> None:
    assert run("db", "upgrade").exit_code == 0
    assert run("forecast", *AS_OF).stdout == (
        "Forecast from 2026-05-25 to 2026-06-23.\nNo accounts with a balance.\n"
    )


@pytest.mark.parametrize(
    ("account", "message"),
    [("Nope", "account not found"), ("Test Brokerage", "Test Brokerage has no balance yet")],
)
def test_a_refused_account(money: Settings, account: str, message: str) -> None:
    assert failed_cleanly(run("forecast", *AS_OF, "--account", account), message)


def test_one_account_with_nothing_expected(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        quiet = create_account(session, "Test Quiet", "Test Bank", "checking")
        add_balance_snapshot(session, quiet.id, date(2026, 5, 20), 500, DataSource.STATEMENT)
    engine.dispose()
    assert run("forecast", *AS_OF, "--account", "Test Quiet").stdout == (
        "Forecast for Test Quiet from 2026-05-25 to 2026-06-23.\n"
        "Starting balance: $5.00 (as of 2026-05-20).\n"
        "Nothing expected.\n"
        "Lowest: $5.00 on 2026-05-25.\n"
    )


def test_a_balance_after_the_start_is_not_used(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        savings = get_account_by_name(session, "Test Savings")
        add_balance_snapshot(session, savings.id, date(2026, 6, 1), 200000, DataSource.STATEMENT)
    engine.dispose()
    assert table_rows(run("forecast", *AS_OF).stdout)[3] == SAVINGS
