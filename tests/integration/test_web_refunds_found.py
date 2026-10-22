from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule
from finances.web.app import create_app
from tests.support import WEB_PORT, page, texts

HEADINGS = ["Date", "Account", "Description", "Category", "Amount", "Card", "Section", "Person"]
CARD_NOTE = (
    "Money in on a card: 1, likely a refund or a card payment."
    " Set a category, or pair it on the Transfers page."
)


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def refunds(client: TestClient) -> TestClient:
    """On the card: groceries in April and May, $5.99 of May's refunded in June, groceries
    again after the refund, a book refund with no purchase, and a credit with no category.
    On checking: a deposit with no category. Ids follow the rows."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        rows = [
            (card, date(2026, 4, 1), -1000, "FOOBAR GROCERY"),
            (card, date(2026, 5, 10), -2599, "FOOBAR GROCERY"),
            (card, date(2026, 6, 12), 599, "FOOBAR GROCERY"),
            (card, date(2026, 6, 1), 1500, "BAZ BOOKS"),
            (card, date(2026, 6, 5), 2500, "QUUX CREDIT"),
            (checking, date(2026, 6, 1), 300000, "ACME DEPOSIT"),
            (card, date(2026, 6, 15), -800, "FOOBAR GROCERY"),
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
        create_rule(session, "FOOBAR", "Groceries")
        create_rule(session, "BAZ BOOKS", "Education")
        categorize(session)
    engine.dispose()
    return client


def test_refunds_carry_a_label(refunds: TestClient) -> None:
    found = page(refunds, "/transactions")
    assert [row[2:5] for row in found.rows] == [
        HEADINGS[2:5],
        ["FOOBAR GROCERY", "Groceries", "-$8.00"],
        ["FOOBAR GROCERY", "Groceries refund", "$5.99"],
        ["QUUX CREDIT", "", "$25.00"],
        ["ACME DEPOSIT", "", "$3,000.00"],
        ["BAZ BOOKS", "Education refund", "$15.00"],
        ["FOOBAR GROCERY", "Groceries", "-$25.99"],
        ["FOOBAR GROCERY", "Groceries", "-$10.00"],
    ]
    assert "/transactions?kind=refund" in found.links


def test_only_refunds(refunds: TestClient) -> None:
    found = page(refunds, "/transactions?kind=refund")
    assert [row[2:5] for row in found.rows[1:]] == [
        ["FOOBAR GROCERY", "Groceries refund", "$5.99"],
        ["BAZ BOOKS", "Education refund", "$15.00"],
    ]
    assert "Also filtered by: kind refund. Clear all filters" in texts(found, "hint")


def test_a_refund_names_its_likely_purchase(refunds: TestClient) -> None:
    found = page(refunds, "/transactions/3")
    assert "Likely returns the purchase of 2026-05-10 for -$25.99." in texts(found, "summary")
    assert "/transactions/2" in found.links


def test_the_purchase_names_its_refund(refunds: TestClient) -> None:
    found = page(refunds, "/transactions/2")
    assert "Refunded $5.99 on 2026-06-12." in texts(found, "summary")
    assert "/transactions/3" in found.links


@pytest.mark.parametrize("transaction_id", [1, 5, 6, 7])
def test_no_refund_section_where_none_applies(refunds: TestClient, transaction_id: int) -> None:
    html = refunds.get(f"/transactions/{transaction_id}").text
    assert "<h2>Refund</h2>" not in html and "<h2>Refunds</h2>" not in html


def test_a_refund_with_no_purchase(refunds: TestClient) -> None:
    found = page(refunds, "/transactions/4")
    assert texts(found, "empty") == [
        "No purchase of at least $15.00 from this merchant on this account in the 90 days before."
    ]


def test_money_in_on_a_card_without_a_category(refunds: TestClient) -> None:
    assert CARD_NOTE in texts(page(refunds, "/categories"), "hint")
