from datetime import date

import pytest

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_rule,
    set_balance_snapshot,
    set_budget,
)
from finances.domain.models import DataSource
from tests.integration.test_mcp_outlook import call, store


@pytest.fixture
def today(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 5, 25))
    upgrade_to_head()
    return tmp_settings


def test_a_price_change_signs_previous_cents(today: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card").id
    engine.dispose()
    store(
        [
            (card, date(2026, 2, 27), -12000, "ACME UTILITY"),
            (card, date(2026, 3, 27), -12000, "ACME UTILITY"),
            (card, date(2026, 4, 27), -15000, "ACME UTILITY"),
        ]
    )
    assert call("get_recurring").structured_content["series"] == [
        {
            "merchant": "ACME UTILITY",
            "cadence": "month",
            "amount_cents": -15000,
            "monthly_cents": -15000,
            "count": 3,
            "first_day": "2026-02-27",
            "last_day": "2026-04-27",
            "next_day": "2026-05-27",
            "active": True,
            "previous_cents": -12000,
        }
    ]


def test_upcoming_and_forecast_default_to_thirty_days(today: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking").id
        set_balance_snapshot(session, checking, date(2026, 5, 24), 30000, DataSource.AGGREGATOR)
    engine.dispose()
    store(
        [
            (checking, date(2026, 2, 27), -12000, "ACME UTILITY"),
            (checking, date(2026, 3, 27), -12000, "ACME UTILITY"),
            (checking, date(2026, 4, 27), -12000, "ACME UTILITY"),
        ]
    )
    upcoming = call("get_upcoming").structured_content
    assert upcoming["start"] == "2026-05-25"
    assert upcoming["end"] == "2026-06-23"
    assert [item["day"] for item in upcoming["items"]] == ["2026-05-27"]
    forecast = call("get_forecast").structured_content
    assert forecast["start"] == "2026-05-25"
    assert forecast["end"] == "2026-06-23"
    assert [step["day"] for step in forecast["accounts"][0]["steps"]] == ["2026-05-27"]


def test_a_group_budget(today: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=card.id,
                posted_date=date(2026, 5, 10),
                amount_cents=-2599,
                description="FOOBAR GROCERY",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
        session.flush()
        create_rule(session, "FOOBAR", "Groceries")
        categorize(session)
        set_budget(session, "Food", 10000)
    engine.dispose()
    assert call("get_budgets").structured_content == {
        "month": "2026-05",
        "budgets": [
            {
                "name": "Food",
                "kind": "group",
                "target_cents": 10000,
                "net_cents": 2599,
                "left_cents": 7401,
                "used_percent": 26,
                "month_gone_percent": 81,
            }
        ],
    }


def test_insights_for_a_month_with_no_data(today: Settings) -> None:
    assert call("get_insights", {"month": "2024-01"}).structured_content == {
        "month": "2024-01",
        "findings": [],
        "merchants": [],
    }


def test_budgets_for_a_past_month(today: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=card.id,
                posted_date=date(2026, 4, 5),
                amount_cents=-1599,
                description="QUUX STREAMING",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
        session.flush()
        create_rule(session, "QUUX", "Subscriptions & Digital")
        categorize(session)
        set_budget(session, "Subscriptions & Digital", 2000)
    engine.dispose()
    assert call("get_budgets", {"month": "2026-04"}).structured_content == {
        "month": "2026-04",
        "budgets": [
            {
                "name": "Subscriptions & Digital",
                "kind": "category",
                "target_cents": 2000,
                "net_cents": 1599,
                "left_cents": 401,
                "used_percent": 80,
                "month_gone_percent": 100,
            }
        ],
    }
