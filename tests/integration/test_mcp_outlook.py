from datetime import date

import anyio
import pytest
from mcp.client import Client

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
    set_budget,
)
from finances.domain.models import DataSource
from finances.mcp_server.server import build_server

TOOLS = [
    "data_coverage",
    "find_merchants",
    "get_balances",
    "get_budgets",
    "get_forecast",
    "get_insights",
    "get_net_worth",
    "get_recurring",
    "get_spending",
    "get_upcoming",
    "list_accounts",
    "list_advice",
    "list_categories",
    "list_proposals",
    "list_rules",
    "list_transactions",
    "list_transfer_suggestions",
    "list_transfers",
    "list_uncategorized",
    "log_advice",
    "month_over_month",
    "propose_category",
]
CHECKING = {
    "account": "Test Checking",
    "balance_cents": 30000,
    "balance_day": "2026-05-24",
    "in_cents": 600000,
    "out_cents": -62000,
    "end_cents": 568000,
    "lowest_cents": 18000,
    "lowest_day": "2026-05-27",
    "steps": [
        {
            "day": "2026-05-27",
            "merchant": "ACME UTILITY",
            "amount_cents": -12000,
            "balance_cents": 18000,
        },
        {
            "day": "2026-05-29",
            "merchant": "PAYCHECK EXAMPLE CORP",
            "amount_cents": 300000,
            "balance_cents": 318000,
        },
        {
            "day": "2026-06-02",
            "merchant": "PAYMENT TO TEST CARD",
            "amount_cents": -50000,
            "balance_cents": 268000,
        },
        {
            "day": "2026-06-12",
            "merchant": "PAYCHECK EXAMPLE CORP",
            "amount_cents": 300000,
            "balance_cents": 568000,
        },
    ],
}


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def store(rows: list) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        for number, (account, day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=account,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()


@pytest.fixture
def today(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 5, 25))
    upgrade_to_head()
    return tmp_settings


@pytest.fixture
def ahead(today: Settings) -> Settings:
    """Phase 27b's data: checking with a utility, pay every two weeks, and a card payment; the
    card with streaming and a weekly box; savings with interest; brokerage with no balance; and
    a $20.00 budget for streaming's category."""
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking").id
        card = create_account(session, "Test Card", "Test Bank", "credit_card").id
        savings = create_account(session, "Test Savings", "Test Bank", "savings").id
        create_account(session, "Test Brokerage", "Test Bank", "other")
        set_balance_snapshot(session, checking, date(2026, 5, 24), 30000, DataSource.AGGREGATOR)
        set_balance_snapshot(session, card, date(2026, 5, 24), -45000, DataSource.AGGREGATOR)
        add_balance_snapshot(session, savings, date(2026, 5, 24), 100000, DataSource.STATEMENT)
    engine.dispose()
    store(
        [
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
    )
    engine = get_engine()
    with session_scope(engine) as session:
        pair_transfers(session)
        for pattern, category in (
            ("PAYCHECK", "Paycheck"),
            ("INTEREST PAID", "Interest Income"),
            ("QUUX", "Subscriptions & Digital"),
        ):
            create_rule(session, pattern, category)
        categorize(session)
        set_budget(session, "Subscriptions & Digital", 2000)
    engine.dispose()
    return today


@pytest.fixture
def month(today: Settings) -> Settings:
    """The dashboard's May 2026: groceries that jump, coffee eight times, a late fee, interest,
    a card payment, and a gym that stopped in January."""
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card").id
        checking = create_account(session, "Test Checking", "Test Bank", "checking").id
    engine.dispose()
    store(
        [
            (card, date(2026, 4, 12), -3000, "FOOBAR GROCERY"),
            (checking, date(2026, 4, 15), 300000, "PAYCHECK EXAMPLE CORP"),
            (card, date(2026, 5, 3), -1500, "BAZ BOOKS"),
            (checking, date(2026, 5, 10), -50000, "PAYMENT TO TEST CARD"),
            (card, date(2026, 5, 11), 50000, "PAYMENT THANK YOU"),
            (card, date(2026, 5, 10), -20000, "FOOBAR GROCERY"),
            (card, date(2026, 5, 20), -3500, "LATE FEE"),
            (card, date(2026, 5, 28), -2345, "PURCHASE INTEREST CHARGE"),
            *(
                (card, date(2026, 5, day), -500, "ACME COFFEE")
                for day in (1, 2, 4, 6, 8, 11, 13, 15)
            ),
            *(
                (card, day, -2500, "OLD GYM")
                for day in (date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1))
            ),
        ]
    )
    engine = get_engine()
    with session_scope(engine) as session:
        for pattern, category in (
            ("FOOBAR", "Groceries"),
            ("PAYCHECK", "Paycheck"),
            ("ACME COFFEE", "Coffee & Dessert"),
        ):
            create_rule(session, pattern, category)
        categorize(session)
        pair_transfers(session)
    engine.dispose()
    return today


def test_the_read_only_tools(tmp_settings: Settings) -> None:
    async def go():
        async with Client(build_server()) as client:
            return (await client.list_tools()).tools

    found = anyio.run(go)
    assert sorted(tool.name for tool in found) == TOOLS
    assert all(
        tool.annotations.read_only_hint
        for tool in found
        if tool.name not in ("propose_category", "log_advice")
    )


def test_recurring_charges_are_negative(ahead: Settings) -> None:
    assert call("get_recurring").structured_content == {
        "as_of": "2026-05-25",
        "income": False,
        "series": [
            {
                "merchant": "ACME UTILITY",
                "cadence": "month",
                "amount_cents": -12000,
                "monthly_cents": -12000,
                "count": 3,
                "first_day": "2026-02-27",
                "last_day": "2026-04-27",
                "next_day": "2026-05-27",
                "active": True,
                "previous_cents": None,
            },
            {
                "merchant": "BAZ BOX",
                "cadence": "week",
                "amount_cents": -1200,
                "monthly_cents": -5200,
                "count": 4,
                "first_day": "2026-05-01",
                "last_day": "2026-05-22",
                "next_day": "2026-05-29",
                "active": True,
                "previous_cents": None,
            },
            {
                "merchant": "QUUX STREAMING",
                "cadence": "month",
                "amount_cents": -1599,
                "monthly_cents": -1599,
                "count": 4,
                "first_day": "2026-02-05",
                "last_day": "2026-05-05",
                "next_day": "2026-06-05",
                "active": True,
                "previous_cents": None,
            },
        ],
    }


def test_recurring_income_is_positive(ahead: Settings) -> None:
    series = call("get_recurring", {"income": True}).structured_content["series"]
    assert [
        (item["merchant"], item["cadence"], item["amount_cents"], item["monthly_cents"])
        for item in series
    ] == [
        ("PAYCHECK EXAMPLE CORP", "two_weeks", 300000, 650000),
        ("INTEREST PAID", "month", 100, 100),
    ]


def test_stopped_charges_only_when_asked(month: Settings) -> None:
    assert call("get_recurring").structured_content["series"] == []
    assert call("get_recurring", {"include_inactive": True}).structured_content["series"] == [
        {
            "merchant": "OLD GYM",
            "cadence": "month",
            "amount_cents": -2500,
            "monthly_cents": -2500,
            "count": 3,
            "first_day": "2025-11-01",
            "last_day": "2026-01-01",
            "next_day": "2026-02-01",
            "active": False,
            "previous_cents": None,
        }
    ]


def test_upcoming(ahead: Settings) -> None:
    assert call("get_upcoming", {"days": 7}).structured_content == {
        "start": "2026-05-25",
        "end": "2026-05-31",
        "items": [
            {
                "day": "2026-05-27",
                "kind": "bill",
                "merchant": "ACME UTILITY",
                "cadence": "month",
                "amount_cents": -12000,
            },
            {
                "day": "2026-05-29",
                "kind": "income",
                "merchant": "PAYCHECK EXAMPLE CORP",
                "cadence": "two_weeks",
                "amount_cents": 300000,
            },
            {
                "day": "2026-05-29",
                "kind": "bill",
                "merchant": "BAZ BOX",
                "cadence": "week",
                "amount_cents": -1200,
            },
            {
                "day": "2026-05-30",
                "kind": "income",
                "merchant": "INTEREST PAID",
                "cadence": "month",
                "amount_cents": 100,
            },
        ],
        "bills_cents": -13200,
        "income_cents": 300100,
    }


def test_one_account_forecast(ahead: Settings) -> None:
    assert call("get_forecast", {"account": "test checking"}).structured_content == {
        "start": "2026-05-25",
        "end": "2026-06-23",
        "accounts": [CHECKING],
        "no_balance": [],
    }


def test_every_account_forecast(ahead: Settings) -> None:
    found = call("get_forecast").structured_content
    assert found["accounts"][1] == CHECKING
    assert [
        (
            item["account"],
            item["end_cents"],
            item["lowest_cents"],
            item["lowest_day"],
            len(item["steps"]),
        )
        for item in found["accounts"]
    ] == [
        ("Test Card", -1399, -46200, "2026-05-29", 6),
        ("Test Checking", 568000, 18000, "2026-05-27", 4),
        ("Test Savings", 100100, 100000, "2026-05-25", 1),
    ]
    assert found["no_balance"] == ["Test Brokerage"]


def test_budgets(ahead: Settings) -> None:
    assert call("get_budgets").structured_content == {
        "month": "2026-05",
        "budgets": [
            {
                "name": "Subscriptions & Digital",
                "kind": "category",
                "target_cents": 2000,
                "net_cents": 1599,
                "left_cents": 401,
                "used_percent": 80,
                "month_gone_percent": 81,
            }
        ],
    }


def test_insights(month: Settings) -> None:
    found = call("get_insights", {"month": "2026-05"}).structured_content
    assert found["month"] == "2026-05"
    assert found["findings"] == [
        {
            "type": "interest",
            "severity": "high",
            "subject": None,
            "savings_cents": 2345,
            "detail": "Interest charged: $23.45.",
        },
        {
            "type": "spike",
            "severity": "medium",
            "subject": "Groceries",
            "savings_cents": 19000,
            "detail": "Groceries: $200.00 this month, against $10.00 a month before.",
        },
        {
            "type": "fees",
            "severity": "medium",
            "subject": None,
            "savings_cents": 3500,
            "detail": "Fees charged: $35.00.",
        },
        {
            "type": "frequent_small",
            "severity": "low",
            "subject": "ACME COFFEE",
            "savings_cents": 2000,
            "detail": "ACME COFFEE: 8 visits averaging $5.00.",
        },
    ]
    assert found["merchants"][:2] == [
        {
            "merchant": "FOOBAR GROCERY",
            "visits": 1,
            "spent_cents": 20000,
            "average_cents": 20000,
            "baseline_cents": 1000,
            "change_cents": 19000,
            "weekend_visits": 1,
        },
        {
            "merchant": "ACME COFFEE",
            "visits": 8,
            "spent_cents": 4000,
            "average_cents": 500,
            "baseline_cents": 0,
            "change_cents": 4000,
            "weekend_visits": 1,
        },
    ]


@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        ("get_forecast", {"account": "Nope"}, "account not found"),
        ("get_forecast", {"account": "Test Brokerage"}, "Test Brokerage has no balance yet"),
        ("get_insights", {"month": "May"}, "month must be a year and month, like 2026-05"),
        ("get_budgets", {"month": "May"}, "month must be a year and month, like 2026-05"),
    ],
)
def test_refusals(ahead: Settings, tool: str, arguments: dict, message: str) -> None:
    result = call(tool, arguments)
    assert result.is_error is True
    assert [item.text for item in result.content] == [f"Error executing tool {tool}: {message}"]


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [("get_upcoming", {"days": 0}), ("get_upcoming", {"days": 91}), ("get_forecast", {"days": 91})],
)
def test_days_out_of_range(today: Settings, tool: str, arguments: dict) -> None:
    result = call(tool, arguments)
    assert result.is_error is True
    assert result.content[0].text.startswith(f"Error executing tool {tool}: 1 validation error")
