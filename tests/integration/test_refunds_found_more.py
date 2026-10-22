from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.analysis.refunds import RefundFacts, refund_facts
from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule, set_account_active
from finances.web.app import create_app
from tests.support import WEB_PORT, page, texts


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


def _store(session, account, rows: list[tuple[date, int, str, bool]]) -> None:
    for number, (day, cents, description, pending) in enumerate(rows, start=1):
        session.add(
            TransactionRow(
                account_id=account.id,
                posted_date=day,
                amount_cents=cents,
                description=description,
                is_pending=pending,
                source="statement",
                fingerprint=f"t{number:02d}".ljust(64, "0"),
            )
        )
    session.flush()
    create_rule(session, "FOOBAR", "Groceries")
    categorize(session)


def test_a_refund_on_a_closed_account_still_matches(client: TestClient) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        _store(
            session,
            card,
            [
                (date(2026, 5, 10), -2599, "FOOBAR GROCERY", False),
                (date(2026, 6, 12), 599, "FOOBAR GROCERY", False),
            ],
        )
        set_account_active(session, card.id, False)
    engine.dispose()
    found = page(client, "/transactions/2")
    assert "Likely returns the purchase of 2026-05-10 for -$25.99." in texts(found, "summary")
    assert "/transactions/1" in found.links


def test_two_refunds_of_one_purchase_are_listed_oldest_first(client: TestClient) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        _store(
            session,
            card,
            [
                (date(2026, 5, 10), -2599, "FOOBAR GROCERY", False),
                (date(2026, 6, 1), 400, "FOOBAR GROCERY", False),
                (date(2026, 6, 12), 599, "FOOBAR GROCERY", False),
            ],
        )
    engine.dispose()
    found = page(client, "/transactions/1")
    assert texts(found, "summary") == [
        "Refunded $4.00 on 2026-06-01.",
        "Refunded $5.99 on 2026-06-12.",
    ]


def test_a_refund_on_another_account_never_matches(client: TestClient) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        first = create_account(session, "Test Card", "Test Bank", "credit_card")
        second = create_account(session, "Other Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=first.id,
                posted_date=date(2026, 5, 10),
                amount_cents=-2599,
                description="FOOBAR GROCERY",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
        session.add(
            TransactionRow(
                account_id=second.id,
                posted_date=date(2026, 6, 12),
                amount_cents=599,
                description="FOOBAR GROCERY",
                source="statement",
                fingerprint="t02".ljust(64, "0"),
            )
        )
        session.flush()
        create_rule(session, "FOOBAR", "Groceries")
        categorize(session)
    engine.dispose()
    found = page(client, "/transactions/2")
    assert texts(found, "empty") == [
        "No purchase of at least $5.99 from this merchant on this account in the 90 days before."
    ]


def test_a_pending_charge_is_never_a_purchase(client: TestClient) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        _store(
            session,
            card,
            [
                (date(2026, 5, 10), -2599, "FOOBAR GROCERY", True),
                (date(2026, 6, 12), 599, "FOOBAR GROCERY", False),
            ],
        )
    engine.dispose()
    found = page(client, "/transactions/2")
    assert texts(found, "empty") == [
        "No purchase of at least $5.99 from this merchant on this account in the 90 days before."
    ]


def test_the_account_page_shows_the_refund_badge(client: TestClient) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        _store(
            session,
            card,
            [
                (date(2026, 5, 10), -2599, "FOOBAR GROCERY", False),
                (date(2026, 6, 12), 599, "FOOBAR GROCERY", False),
            ],
        )
    engine.dispose()
    found = page(client, "/account?name=Test%20Card")
    assert ["2026-06-12", "FOOBAR GROCERY", "Groceries refund", "$5.99", "", ""] in found.rows


def test_kind_refund_together_with_a_category_filter(client: TestClient) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=card.id,
                posted_date=date(2026, 6, 12),
                amount_cents=599,
                description="FOOBAR GROCERY",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
        session.add(
            TransactionRow(
                account_id=card.id,
                posted_date=date(2026, 6, 1),
                amount_cents=1500,
                description="BAZ BOOKS",
                source="statement",
                fingerprint="t02".ljust(64, "0"),
            )
        )
        session.flush()
        create_rule(session, "FOOBAR", "Groceries")
        create_rule(session, "BAZ BOOKS", "Education")
        categorize(session)
    engine.dispose()
    found = page(client, "/transactions?kind=refund&category=Groceries")
    assert [row[2:5] for row in found.rows[1:]] == [["FOOBAR GROCERY", "Groceries refund", "$5.99"]]


def test_refund_facts_of_a_missing_transaction(tmp_settings: Settings) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        assert refund_facts(session, 9) == RefundFacts(False, None, [])
    engine.dispose()
