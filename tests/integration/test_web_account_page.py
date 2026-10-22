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
    create_person,
    create_rule,
    set_account_owner,
)
from finances.domain.models import DataSource
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts

TODAY = date(2026, 5, 25)
CARD = "/account?name=Test%20Card"
SPENDING = ["Group", "Spent", "Refunds", "Net", "Count"]
MONTHS = ["Month", "Spent", "Income"]
BALANCES = ["Date", "Balance", "From"]
LATEST = ["Date", "Description", "Category", "Amount", "Card", "Person"]
DETAIL = [
    ["Name", "Test Card"],
    ["Institution", "Test Bank"],
    ["Type", "credit_card"],
    ["Last 4", "9999"],
    ["Owner", "Pat Example"],
    ["Status", "open"],
    ["Balance", "-$612.34 on 2026-05-20 (SimpleFIN)"],
]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Test Card (Pat's) with cards 1111 and 2222, three balances, and a payment from Test
    Checking that pairs as a transfer; Test Checking has a utility bill of its own."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card", last4="9999")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        pat = create_person(session, "Pat Example")
        set_account_owner(session, card.id, pat.id)
        add_balance_snapshot(session, card.id, date(2026, 3, 31), -40000, DataSource.STATEMENT)
        add_balance_snapshot(session, card.id, date(2026, 4, 30), -45000, DataSource.STATEMENT)
        add_balance_snapshot(session, card.id, date(2026, 5, 20), -61234, DataSource.AGGREGATOR)
        rows = [
            (card, date(2026, 4, 12), -3000, "FOOBAR GROCERY", "1111"),
            (card, date(2026, 5, 3), -1500, "BAZ BOOKS", "2222"),
            (card, date(2026, 5, 10), -20000, "FOOBAR GROCERY", "1111"),
            (card, date(2026, 5, 12), -500, "ACME COFFEE", "2222"),
            (card, date(2026, 5, 15), 599, "FOOBAR GROCERY", "1111"),
            (checking, date(2026, 5, 5), -12000, "ACME UTILITY", None),
            (card, date(2026, 5, 20), -3500, "LATE FEE", None),
            (checking, date(2026, 5, 20), -50000, "PAYMENT TO TEST CARD", None),
            (card, date(2026, 5, 21), 50000, "PAYMENT THANK YOU", None),
        ]
        for number, (account, day, cents, description, last4) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    card_last4=last4,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for pattern, category in (
            ("FOOBAR", "Groceries"),
            ("ACME COFFEE", "Coffee & Dessert"),
            ("ACME UTILITY", "Utilities & Internet"),
        ):
            create_rule(session, pattern, category)
        categorize(session)
        pair_transfers(session)
    engine.dispose()
    return client


def table(found: Page, heading: list[str]) -> list[list[str]]:
    start = found.rows.index(heading)
    end = start + 1
    while end < len(found.rows) and len(found.rows[end]) == len(heading):
        if found.rows[end] in (SPENDING, MONTHS, BALANCES, LATEST):
            break
        end += 1
    return found.rows[start:end]


def test_every_account_name_and_card_opens_the_account_page(home: TestClient) -> None:
    assert CARD in page(home, "/accounts").links
    assert CARD in page(home, "/reports?month=2026-05").links
    transactions = page(home, "/transactions").links
    assert CARD in transactions and f"{CARD}&card=1111" in transactions
    assert "/account?name=Test%20Checking" in page(home, "/transfers").links


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get(CARD)
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_the_account_page(home: TestClient) -> None:
    response = home.get(CARD)
    assert response.status_code == 200
    assert 'href="/accounts" aria-current="page">Accounts</a>' in response.text
    found = Page(response.text)
    assert found.rows[:7] == DETAIL
    assert texts(found, "cards") == ["Cards: 1111, 2222"]
    assert table(found, SPENDING) == [
        SPENDING,
        ["Food", "$205.00", "$5.99", "$199.01", "3"],
        ["Uncategorized", "$50.00", "$0.00", "$50.00", "2"],
    ]
    months = table(found, MONTHS)
    assert len(months) == 13
    assert months[1] == ["2025-06", "$0.00", "$0.00"]
    assert months[-2:] == [["2026-04", "$30.00", "$0.00"], ["2026-05", "$249.01", "$0.00"]]
    assert table(found, BALANCES) == [
        BALANCES,
        ["2026-05-20", "-$612.34", "SimpleFIN"],
        ["2026-04-30", "-$450.00", "statement"],
        ["2026-03-31", "-$400.00", "statement"],
    ]
    assert table(found, LATEST) == [
        LATEST,
        ["2026-05-21", "PAYMENT THANK YOU", "", "$500.00", "", "Pat Example"],
        ["2026-05-20", "LATE FEE", "", "-$35.00", "", "Pat Example"],
        ["2026-05-15", "FOOBAR GROCERY", "Groceries refund", "$5.99", "••1111", "Pat Example"],
        ["2026-05-12", "ACME COFFEE", "Coffee & Dessert", "-$5.00", "••2222", "Pat Example"],
        ["2026-05-10", "FOOBAR GROCERY", "Groceries", "-$200.00", "••1111", "Pat Example"],
        ["2026-05-03", "BAZ BOOKS", "", "-$15.00", "••2222", "Pat Example"],
        ["2026-04-12", "FOOBAR GROCERY", "Groceries", "-$30.00", "••1111", "Pat Example"],
    ]
    for link in (
        "/transactions?account=Test%20Card&from=2026-05-01&to=2026-05-31&group=Food&kind=spending&limit=1000",
        f"{CARD}&month=2026-04",
        f"{CARD}&card=1111",
        "/transactions?account=Test%20Card",
    ):
        assert link in found.links, link


def test_one_card_of_the_account(home: TestClient) -> None:
    found = page(home, f"{CARD}&card=2222")
    assert "<h1>Test Card · card ending 2222</h1>" in home.get(f"{CARD}&card=2222").text
    assert found.rows[:7] == DETAIL
    assert table(found, SPENDING) == [
        SPENDING,
        ["Uncategorized", "$15.00", "$0.00", "$15.00", "1"],
        ["Food", "$5.00", "$0.00", "$5.00", "1"],
    ]
    assert table(found, MONTHS)[-1] == ["2026-05", "$20.00", "$0.00"]
    assert [row[1] for row in table(found, LATEST)[1:]] == ["ACME COFFEE", "BAZ BOOKS"]
    assert f"{CARD}" in found.links


def test_a_group_line_opens_exactly_its_transactions(home: TestClient) -> None:
    for query, count in (("", 3), ("&card=1111", 2)):
        found = page(home, f"{CARD}{query}")
        food = next(link for link in found.links if "group=Food" in link)
        assert len(page(home, food).rows) - 1 == count, food


def test_another_month(home: TestClient) -> None:
    found = page(home, f"{CARD}&month=2026-04")
    assert table(found, SPENDING) == [SPENDING, ["Food", "$30.00", "$0.00", "$30.00", "1"]]
    assert found.find("/account")["inputs"]["month"] == ("month", "2026-04")
    assert table(found, MONTHS)[-1] == ["2026-05", "$249.01", "$0.00"]
    found = page(home, f"{CARD}&month=2026-02")
    assert ("empty", "No spending in 2026-02.") in found.paragraphs


@pytest.mark.parametrize(
    ("query", "status", "message"),
    [
        ("/account?name=Nope", 404, "account not found"),
        ("/account", 404, "account not found"),
        (f"{CARD}&card=3333", 404, "card not found"),
        (f"{CARD}&card=12", 404, "card not found"),
        (f"{CARD}&month=2026-13", 400, "month must be a year and month, like 2026-05"),
    ],
)
def test_refused(home: TestClient, query: str, status: int, message: str) -> None:
    response = home.get(query)
    assert response.status_code == status
    assert ("error", message) in Page(response.text).paragraphs
