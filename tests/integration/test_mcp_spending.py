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
from finances.db.repositories import create_account, create_person, create_rule, set_account_owner
from finances.mcp_server.server import build_server

TOOLS = [
    "get_balances",
    "get_budgets",
    "get_forecast",
    "get_insights",
    "get_net_worth",
    "get_recurring",
    "get_spending",
    "get_upcoming",
    "list_accounts",
    "list_categories",
    "list_rules",
    "list_transactions",
    "list_transfer_suggestions",
    "list_transfers",
    "list_uncategorized",
    "month_over_month",
]
REFUND = {
    "id": 2,
    "day": "2026-05-10",
    "posted": "2026-05-10",
    "account": "Test Card",
    "description": "FOOBAR GROCERY #77",
    "merchant": "FOOBAR GROCERY",
    "amount_cents": 599,
    "kind": "spending",
    "refund": True,
    "category": "Groceries",
    "group": "Food",
    "person": "Pat Example",
    "card": "1111",
    "pending": False,
}


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def ids(result) -> list[int]:
    return [item["id"] for item in result.structured_content["transactions"]]


@pytest.fixture
def money(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """May 2026 on Pat's card and a checking account: groceries and $5.99 of them refunded, a
    book with no category, pay, a card payment that pairs, a pending charge, and money in with no
    category; groceries in April. Ids follow the rows."""
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 5, 29))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        set_account_owner(session, card.id, create_person(session, "Pat Example").id)
        rows = [
            (card, date(2026, 5, 2), -2599, "FOOBAR GROCERY #77", "1111", False),
            (card, date(2026, 5, 10), 599, "FOOBAR GROCERY #77", "1111", False),
            (card, date(2026, 5, 12), -1500, "BAZ BOOKS", None, False),
            (checking, date(2026, 5, 15), 300000, "PAYCHECK EXAMPLE CORP", None, False),
            (checking, date(2026, 5, 20), -50000, "PAYMENT TO TEST CARD", None, False),
            (card, date(2026, 5, 21), 50000, "PAYMENT THANK YOU", None, False),
            (card, date(2026, 4, 8), -3000, "FOOBAR GROCERY #12", "1111", False),
            (card, date(2026, 5, 25), -999, "QUUX STREAMING", None, True),
            (checking, date(2026, 5, 28), 2500, "ACME CREDIT", None, False),
        ]
        for number, (account, day, cents, description, last4, pending) in enumerate(rows, 1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    card_last4=last4,
                    is_pending=pending,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        pair_transfers(session)
        create_rule(session, "FOOBAR", "Groceries")
        create_rule(session, "PAYCHECK", "Paycheck")
        categorize(session)
    engine.dispose()
    return tmp_settings


def test_the_read_only_tools(tmp_settings: Settings) -> None:
    async def go():
        async with Client(build_server()) as client:
            return (await client.list_tools()).tools

    found = anyio.run(go)
    assert sorted(tool.name for tool in found) == TOOLS
    for tool in found:
        assert tool.annotations.read_only_hint is True, tool.name


def test_every_transaction_latest_first(money: Settings) -> None:
    result = call("list_transactions")
    assert result.is_error is False
    assert ids(result) == [9, 8, 6, 5, 4, 3, 2, 1, 7]
    assert result.structured_content["next_offset"] is None
    assert result.structured_content["transactions"][6] == REFUND
    refunds = [item["id"] for item in result.structured_content["transactions"] if item["refund"]]
    assert refunds == [2]


def test_pages(money: Settings) -> None:
    first = call("list_transactions", {"limit": 3})
    assert (ids(first), first.structured_content["next_offset"]) == ([9, 8, 6], 3)
    last = call("list_transactions", {"limit": 3, "offset": 6})
    assert (ids(last), last.structured_content["next_offset"]) == ([2, 1, 7], None)
    beyond = call("list_transactions", {"offset": 9})
    assert (ids(beyond), beyond.structured_content["next_offset"]) == ([], None)


@pytest.mark.parametrize(
    ("arguments", "found"),
    [
        ({"kind": "refund"}, [2]),
        ({"merchant": "foobar grocery"}, [2, 1, 7]),
        ({"person": "pat example", "start": "2026-05-01", "end": "2026-05-24"}, [6, 3, 2, 1]),
        ({"text": "payment"}, [6, 5]),
        ({"kind": "unsorted_in"}, [9]),
        ({"kind": "pending"}, [8]),
        ({"category": "Groceries", "card": "1111", "start": "2026-05-01"}, [2, 1]),
    ],
)
def test_filters(money: Settings, arguments: dict, found: list[int]) -> None:
    assert ids(call("list_transactions", arguments)) == found


@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        ("list_transactions", {"account": "Nope"}, "account not found"),
        ("list_transactions", {"person": "Nobody"}, "person not found"),
        (
            "list_transactions",
            {"kind": "spend"},
            "kind must be one of: spending, income, transfer, unsorted_in, pending, refund",
        ),
        (
            "list_transactions",
            {"start": "2026-05-10", "end": "2026-05-01"},
            "the start date is after the end date",
        ),
        ("get_spending", {"start": "2026-05-01"}, "give both start and end, or neither"),
        (
            "get_spending",
            {"start": "2026-05-10", "end": "2026-05-01"},
            "the start date is after the end date",
        ),
        ("month_over_month", {"month": "May"}, "month must be a year and month, like 2026-05"),
    ],
)
def test_refusals(money: Settings, tool: str, arguments: dict, message: str) -> None:
    result = call(tool, arguments)
    assert result.is_error is True
    assert [item.text for item in result.content] == [f"Error executing tool {tool}: {message}"]


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("list_transactions", {"limit": 0}),
        ("list_transactions", {"limit": 201}),
        ("list_transactions", {"offset": -1}),
        ("get_spending", {"by": "shop"}),
        ("month_over_month", {"count": 25}),
    ],
)
def test_arguments_out_of_range(money: Settings, tool: str, arguments: dict) -> None:
    result = call(tool, arguments)
    assert result.is_error is True
    assert result.content[0].text.startswith(f"Error executing tool {tool}: 1 validation error")


def test_spending_this_month_by_category(money: Settings) -> None:
    assert call("get_spending").structured_content == {
        "start": "2026-05-01",
        "end": "2026-05-31",
        "by": "category",
        "lines": [
            {
                "label": "Groceries",
                "spent_cents": 2599,
                "refunds_cents": 599,
                "net_cents": 2000,
                "count": 2,
            },
            {
                "label": "Uncategorized",
                "spent_cents": 1500,
                "refunds_cents": 0,
                "net_cents": 1500,
                "count": 1,
            },
        ],
        "summary": {
            "spent_cents": 4099,
            "refunds_cents": 599,
            "net_cents": 3500,
            "income_cents": 300000,
            "transfers": 2,
            "unsorted_in_cents": 2500,
            "unsorted_in_count": 1,
        },
    }


def test_spending_by_person_over_a_range(money: Settings) -> None:
    found = call("get_spending", {"start": "2026-04-01", "end": "2026-05-31", "by": "person"})
    assert found.structured_content["lines"] == [
        {
            "label": "Pat Example",
            "spent_cents": 7099,
            "refunds_cents": 599,
            "net_cents": 6500,
            "count": 4,
        }
    ]


def test_month_over_month(money: Settings) -> None:
    assert call("month_over_month", {"month": "2026-05", "count": 2}).structured_content == {
        "months": [
            {
                "month": "2026-04",
                "net_cents": 3000,
                "income_cents": 0,
                "uncovered": ["Test Card", "Test Checking"],
            },
            {
                "month": "2026-05",
                "net_cents": 3500,
                "income_cents": 300000,
                "uncovered": ["Test Card", "Test Checking"],
            },
        ]
    }


def test_month_over_month_ends_this_month_by_default(money: Settings) -> None:
    months = call("month_over_month").structured_content["months"]
    assert [item["month"] for item in months] == [
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
        "2026-05",
    ]


def test_month_over_month_ends_with_the_month_given(money: Settings) -> None:
    months = call("month_over_month", {"month": "2026-04", "count": 2}).structured_content["months"]
    assert [(item["month"], item["net_cents"]) for item in months] == [
        ("2026-03", 0),
        ("2026-04", 3000),
    ]
