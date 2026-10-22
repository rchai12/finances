from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_statement, set_account_active
from tests.integration.test_mcp_coverage import call


@pytest.fixture
def today(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 5, 20))
    upgrade_to_head()
    return tmp_settings


def test_an_account_with_no_data(today: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Empty", "Test Bank", "checking")
    engine.dispose()
    found = call("data_coverage").structured_content["accounts"][0]
    assert found["name"] == "Test Empty"
    assert found["first_day"] is None
    assert found["last_day"] is None
    assert found["audited"] == []
    assert found["mapped"] is False


def test_a_closed_account_is_left_out(today: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Open", "Test Bank", "checking")
        old = create_account(session, "Test Closed", "Test Bank", "checking")
        set_account_active(session, old.id, False)
    engine.dispose()
    names = [item["name"] for item in call("data_coverage").structured_content["accounts"]]
    assert names == ["Test Open"]


def test_a_stale_statement_is_listed(today: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        create_statement(
            session,
            account_id=card.id,
            source_filename="card.pdf",
            file_sha256="a" * 64,
            parser_name="test",
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            opening_balance_cents=0,
            closing_balance_cents=0,
            lines_parsed=0,
            rows_inserted=0,
            rows_duplicate=0,
        )
    engine.dispose()
    problems = [
        item
        for item in call("data_coverage").structured_content["problems"]
        if item["kind"] == "statements"
    ]
    assert problems == [
        {
            "kind": "statements",
            "account": "Test Card",
            "detail": "The newest statement ends 2026-03-31 (50 days ago).",
            "action": (
                "Upload the newest statement on the Statements page, or run fin import statement."
            ),
        }
    ]


def test_find_merchants_on_an_empty_database_matches_categories(today: Settings) -> None:
    assert call("find_merchants", {"phrase": "coffee"}).structured_content == {
        "matches": [{"name": "Coffee & Dessert", "kind": "category", "score": 100}]
    }


def test_a_pending_merchant_is_not_offered(today: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=card.id,
                posted_date=date(2026, 5, 18),
                amount_cents=-999,
                description="ZYZZY PENDING STORE",
                source="aggregator",
                is_pending=True,
                fingerprint="t01".ljust(64, "0"),
            )
        )
    engine.dispose()
    names = [
        item["name"]
        for item in call("find_merchants", {"phrase": "ZYZZY"}).structured_content["matches"]
    ]
    assert names == []
