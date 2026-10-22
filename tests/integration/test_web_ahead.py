from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.categorize.transfers import pair_transfers
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    create_rule,
    set_balance_snapshot,
)
from finances.domain.models import DataSource
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts

TODAY = date(2026, 5, 25)
FORECAST = [
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
EXPECTED = ["Date", "What", "Merchant", "Every", "Amount"]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return found


@pytest.fixture
def money(client: TestClient) -> TestClient:
    """Checking: a utility on the 27th, pay every two weeks, a card payment on the 2nd.
    Card: streaming, a weekly box, the payment arriving on the 3rd. Savings: monthly interest.
    Brokerage: no balance."""
    upgrade_to_head()
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
        session.flush()
        pair_transfers(session)
        create_rule(session, "PAYCHECK", "Paycheck")
        create_rule(session, "INTEREST PAID", "Interest Income")
        categorize(session)
    engine.dispose()
    return client


def test_not_migrated(client: TestClient) -> None:
    response = client.get("/ahead")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_every_account_and_what_is_expected(money: TestClient) -> None:
    response = money.get("/ahead")
    assert response.status_code == 200
    assert 'href="/ahead" aria-current="page">Ahead</a>' in response.text
    found = Page(response.text)
    assert found.rows == [
        FORECAST,
        CARD,
        CHECKING,
        SAVINGS,
        EXPECTED,
        ["2026-05-27", "bill", "ACME UTILITY", "month", "-$120.00"],
        ["2026-05-29", "income", "PAYCHECK EXAMPLE CORP", "two_weeks", "$3,000.00"],
        ["2026-05-29", "bill", "BAZ BOX", "week", "-$12.00"],
        ["2026-05-30", "income", "INTEREST PAID", "month", "$1.00"],
        ["2026-06-05", "bill", "BAZ BOX", "week", "-$12.00"],
        ["2026-06-05", "bill", "QUUX STREAMING", "month", "-$15.99"],
        ["2026-06-12", "income", "PAYCHECK EXAMPLE CORP", "two_weeks", "$3,000.00"],
        ["2026-06-12", "bill", "BAZ BOX", "week", "-$12.00"],
        ["2026-06-19", "bill", "BAZ BOX", "week", "-$12.00"],
    ]
    assert texts(found, "summary") == [
        "Forecast from 2026-05-25 to 2026-06-23.",
        "Expected from 2026-05-25 to 2026-06-23.",
        "Bills: -$183.99. Income: $6,001.00.",
    ]
    assert texts(found, "hint") == ["No balance yet: Test Brokerage."]
    assert "/ahead?account=Test%20Checking&days=30" in found.links
    assert found.forms[0]["inputs"] == {"days": ("number", "30")}


def test_one_account_day_by_day(money: TestClient) -> None:
    found = page(money, "/ahead?account=test+checking&days=30")
    assert found.rows == [
        ["Date", "Merchant", "Amount", "Balance"],
        ["2026-05-27", "ACME UTILITY", "-$120.00", "$180.00"],
        ["2026-05-29", "PAYCHECK EXAMPLE CORP", "$3,000.00", "$3,180.00"],
        ["2026-06-02", "PAYMENT TO TEST CARD", "-$500.00", "$2,680.00"],
        ["2026-06-12", "PAYCHECK EXAMPLE CORP", "$3,000.00", "$5,680.00"],
    ]
    assert texts(found, "summary") == [
        "Forecast for Test Checking from 2026-05-25 to 2026-06-23.",
        "Starting balance: $300.00 (as of 2026-05-24).",
        "Lowest: $180.00 on 2026-05-27.",
    ]
    assert "/ahead?days=30" in found.links
    assert found.forms[0]["inputs"] == {
        "days": ("number", "30"),
        "account": ("hidden", "Test Checking"),
    }


def test_a_shorter_window(money: TestClient) -> None:
    found = page(money, "/ahead?days=7")
    assert found.rows[2] == [
        "Test Checking",
        "$300.00",
        "2026-05-24",
        "$3,000.00",
        "-$120.00",
        "$3,180.00",
        "$180.00",
        "2026-05-27",
    ]
    assert texts(found, "summary")[-1] == "Bills: -$132.00. Income: $3,001.00."
    assert "/ahead?account=Test%20Card&days=7" in found.links


def test_nothing_yet(client: TestClient) -> None:
    upgrade_to_head()
    found = page(client, "/ahead")
    assert found.rows == []
    assert texts(found, "empty") == ["No accounts with a balance.", "Nothing expected."]
    assert texts(found, "hint") == []


@pytest.mark.parametrize("days", ["0", "91", "ten", "1.5", "-3"])
def test_refused_days(money: TestClient, days: str) -> None:
    response = money.get(f"/ahead?days={days}")
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == ["days must be a whole number from 1 to 90"]
    assert "/ahead" in found.links


@pytest.mark.parametrize(
    ("account", "message"),
    [("Nope", "account not found"), ("Test+Brokerage", "Test Brokerage has no balance yet")],
)
def test_refused_account(money: TestClient, account: str, message: str) -> None:
    response = money.get(f"/ahead?account={account}")
    assert response.status_code == 404
    assert texts(Page(response.text), "error") == [message]


def test_coming_up_on_the_dashboard(money: TestClient) -> None:
    found = page(money, "/")
    start = found.rows.index(["Date", "What", "Merchant", "Amount"])
    assert found.rows[start:] == [
        ["Date", "What", "Merchant", "Amount"],
        ["2026-05-27", "bill", "ACME UTILITY", "-$120.00"],
        ["2026-05-29", "income", "PAYCHECK EXAMPLE CORP", "$3,000.00"],
        ["2026-05-29", "bill", "BAZ BOX", "-$12.00"],
        ["2026-05-30", "income", "INTEREST PAID", "$1.00"],
    ]
    assert texts(found, "ahead") == ["Bills: -$132.00. Income: $3,001.00."]
    assert "/ahead" in found.links


def test_nothing_coming_up_on_the_dashboard(client: TestClient) -> None:
    upgrade_to_head()
    assert texts(page(client, "/"), "ahead") == [
        "Nothing expected in the next 7 days.",
        "Bills: $0.00. Income: $0.00.",
    ]
