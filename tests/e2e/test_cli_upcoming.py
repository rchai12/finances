from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from tests.support import CLI_NOT_MIGRATED, plain_lines, run, table_rows

AS_OF = ("--as-of", "2026-05-25")
UPCOMING = ["Date", "What", "Merchant", "Every", "Amount"]
RECURRING = ["Merchant", "Every", "Amount", "Monthly", "Count", "Last", "Next", "Active"]


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    """A streaming plan, a weekly box, a yearly cloud plan, a paycheck every two weeks; and,
    never income, a grocery refund each month and a monthly move into savings."""
    assert run("db", "upgrade").exit_code == 0
    rows = [
        *((date(2026, month, 5), -1599, "QUUX STREAMING") for month in (2, 3, 4, 5)),
        *((date(2026, 5, day), -1200, "BAZ BOX") for day in (1, 8, 15, 22)),
        (date(2024, 6, 10), -9900, "QUUX CLOUD"),
        (date(2025, 6, 10), -9900, "QUUX CLOUD"),
        *(
            (day, 300000, "PAYCHECK EXAMPLE CORP")
            for day in (date(2026, 4, 3), date(2026, 4, 17), date(2026, 5, 1), date(2026, 5, 15))
        ),
        *((date(2026, month, 9), 599, "FOOBAR GROCERY") for month in (3, 4, 5)),
        *((date(2026, month, 1), 2000, "TRANSFER FROM CHECKING") for month in (3, 4, 5)),
    ]
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    for pattern, category in (
        ("PAYCHECK", "Paycheck"),
        ("FOOBAR", "Groceries"),
        ("TRANSFER FROM", "Transfer"),
    ):
        assert run("rules", "add", "--pattern", pattern, "--category", category).exit_code == 0
    return tmp_settings


@pytest.mark.parametrize("args", [("upcoming",), ("upcoming", *AS_OF), ("recurring", "--income")])
def test_needs_a_migrated_database(tmp_settings: Settings, args) -> None:
    result = run(*args)
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


def test_the_next_30_days(money: Settings) -> None:
    result = run("upcoming", *AS_OF)
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        UPCOMING,
        ["2026-05-29", "income", "PAYCHECK EXAMPLE CORP", "two_weeks", "$3,000.00"],
        ["2026-05-29", "bill", "BAZ BOX", "week", "-$12.00"],
        ["2026-06-05", "bill", "BAZ BOX", "week", "-$12.00"],
        ["2026-06-05", "bill", "QUUX STREAMING", "month", "-$15.99"],
        ["2026-06-10", "bill", "QUUX CLOUD", "year", "-$99.00"],
        ["2026-06-12", "income", "PAYCHECK EXAMPLE CORP", "two_weeks", "$3,000.00"],
        ["2026-06-12", "bill", "BAZ BOX", "week", "-$12.00"],
        ["2026-06-19", "bill", "BAZ BOX", "week", "-$12.00"],
    ]
    assert plain_lines(result.stdout) == [
        "Expected from 2026-05-25 to 2026-06-23.",
        "Bills: -$162.99. Income: $6,000.00.",
    ]


def test_a_shorter_window(money: Settings) -> None:
    result = run("upcoming", *AS_OF, "--days", "7")
    assert [row[2] for row in table_rows(result.stdout)[1:]] == ["PAYCHECK EXAMPLE CORP", "BAZ BOX"]
    assert plain_lines(result.stdout) == [
        "Expected from 2026-05-25 to 2026-05-31.",
        "Bills: -$12.00. Income: $3,000.00.",
    ]


def test_nothing_expected(tmp_settings: Settings) -> None:
    assert run("db", "upgrade").exit_code == 0
    assert run("upcoming", *AS_OF).stdout == (
        "Expected from 2026-05-25 to 2026-06-23.\nNothing expected.\nBills: $0.00. Income: $0.00.\n"
    )
    assert run("recurring", "--income", *AS_OF).stdout == (
        "No recurring income.\nRecurring income: 0 active, $0.00 a month.\n"
    )


def test_recurring_income(money: Settings) -> None:
    result = run("recurring", "--income", *AS_OF)
    assert table_rows(result.stdout) == [
        RECURRING,
        [
            "PAYCHECK EXAMPLE CORP",
            "two_weeks",
            "$3,000.00",
            "$6,500.00",
            "4",
            "2026-05-15",
            "2026-05-29",
            "yes",
        ],
    ]
    assert plain_lines(result.stdout) == ["Recurring income: 1 active, $6,500.00 a month."]


@pytest.mark.parametrize("days", ["0", "91"])
def test_a_window_out_of_range(money: Settings, days: str) -> None:
    result = run("upcoming", *AS_OF, "--days", days)
    assert result.exit_code == 2
    assert "'--days'" in result.stderr
