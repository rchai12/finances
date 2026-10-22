from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from tests.support import plain_lines, run, table_rows

JUNE = ("--month", "2026-06")


@pytest.fixture
def refunded(tmp_settings: Settings) -> Settings:
    """Groceries bought in May and partly refunded in June; a box bought in May; nothing else
    in June. A Groceries budget of $100.00."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [
            (date(2026, 5, 10), -2599, "FOOBAR GROCERY"),
            (date(2026, 5, 14), -1200, "BAZ BOX"),
            (date(2026, 6, 12), 599, "FOOBAR GROCERY"),
        ]
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
    assert run("rules", "add", "--pattern", "FOOBAR", "--category", "Groceries").exit_code == 0
    assert run("budgets", "set", "--name", "Groceries", "--amount", "100").exit_code == 0
    return tmp_settings


def test_a_month_where_refunds_win(refunded: Settings) -> None:
    result = run("spending", *JUNE)
    assert table_rows(result.stdout) == [
        ["Category", "Spent", "Refunds", "Net", "Count"],
        ["Groceries", "$0.00", "$5.99", "$5.99 back", "1"],
    ]
    assert plain_lines(result.stdout) == [
        "Spending from 2026-06-01 to 2026-06-30, by category.",
        "Spent: $0.00. Refunds: $5.99. Net: $5.99 back. Income: $0.00.",
        "Transfers left out: 0.",
    ]


def test_the_months_table_says_back(refunded: Settings) -> None:
    rows = table_rows(run("months", "--to", "2026-06", "--count", "2").stdout)
    assert rows == [
        ["Month", "Spent", "Income", "Change", "Covered"],
        ["2026-05", "$37.99", "$0.00", "", "partly"],
        ["2026-06", "$5.99 back", "$0.00", "-$43.98", "partly"],
    ]


def test_a_budget_with_money_back_is_not_below_zero_used(refunded: Settings) -> None:
    rows = table_rows(run("budgets", "list", *JUNE).stdout)
    assert [row[:6] for row in rows] == [
        ["Budget", "Kind", "Target", "Spent", "Left", "Used"],
        ["Groceries", "category", "$100.00", "$5.99 back", "$105.99", "0%"],
    ]
