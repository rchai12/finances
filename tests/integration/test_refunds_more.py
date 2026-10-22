from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule
from finances.web.app import create_app
from tests.support import WEB_PORT, page, run, table_rows

JUNE = ("--month", "2026-06")


@pytest.fixture
def refunded(tmp_settings: Settings) -> Settings:
    """Groceries bought in May and partly refunded in June; a box bought in May."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [
            (date(2026, 5, 10), -2599, "FOOBAR GROCERY", "1111"),
            (date(2026, 5, 14), -1200, "BAZ BOX", None),
            (date(2026, 6, 12), 599, "FOOBAR GROCERY", "1111"),
        ]
        for number, (day, cents, description, last4) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    card_last4=last4,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    assert run("rules", "add", "--pattern", "FOOBAR", "--category", "Groceries").exit_code == 0
    return tmp_settings


def test_spending_by_merchant_and_card_in_a_month_with_a_refund(refunded: Settings) -> None:
    merchant = table_rows(run("spending", *JUNE, "--by", "merchant").stdout)
    assert merchant == [
        ["Merchant", "Spent", "Refunds", "Net", "Count"],
        ["FOOBAR GROCERY", "$0.00", "$5.99", "$5.99 back", "1"],
    ]
    card = table_rows(run("spending", *JUNE, "--by", "card").stdout)
    assert card == [
        ["Card", "Spent", "Refunds", "Net", "Count"],
        ["1111", "$0.00", "$5.99", "$5.99 back", "1"],
    ]


def test_the_dashboard_months_table_in_a_month_that_is_money_back(
    refunded: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("finances.web.app._today", lambda: date(2026, 6, 20))
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    found = page(client, "/")
    assert ["2026-06", "$5.99 back", "$0.00", "-$43.98", "partly"] in found.rows


def test_a_budget_group_whose_categories_net_to_money_back(refunded: Settings) -> None:
    assert run("budgets", "set", "--name", "Food", "--amount", "100").exit_code == 0
    rows = table_rows(run("budgets", "list", *JUNE).stdout)
    food = next(row for row in rows if row and row[0] == "Food")
    assert food[:6] == ["Food", "group", "$100.00", "$5.99 back", "$105.99", "0%"]


def test_one_category_back_does_not_make_the_summary_back(tmp_settings: Settings) -> None:
    """Purchases and a larger refund in Groceries, plus other spending so the month is still out."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [
            (date(2026, 6, 2), -200, "FOOBAR GROCERY"),
            (date(2026, 6, 12), 599, "FOOBAR GROCERY"),
            (date(2026, 6, 15), -1500, "ACME COFFEE"),
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
        session.flush()
        create_rule(session, "FOOBAR", "Groceries")
        create_rule(session, "ACME COFFEE", "Coffee & Dessert")
        categorize(session)
    engine.dispose()
    result = run("spending", *JUNE)
    rows = table_rows(result.stdout)
    groceries = next(row for row in rows if row and row[0] == "Groceries")
    assert groceries == ["Groceries", "$2.00", "$5.99", "$3.99 back", "2"]
    assert "Net: $11.01. Income: $0.00." in result.stdout
