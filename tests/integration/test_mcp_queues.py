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
from finances.db.repositories import create_account, create_rule, create_transfer_pair
from finances.domain.models import CONFIRMED
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
TO_SAVINGS = {
    "id": 4,
    "posted": "2026-05-05",
    "account": "Test Checking",
    "description": "TRANSFER TO SAVINGS",
    "amount_cents": -2000,
}
FROM_CHECKING_5 = {
    "id": 5,
    "posted": "2026-05-05",
    "account": "Test Savings",
    "description": "TRANSFER FROM CHECKING",
    "amount_cents": 2000,
}
FROM_CHECKING_6 = {
    "id": 6,
    "posted": "2026-05-06",
    "account": "Test Savings",
    "description": "TRANSFER FROM CHECKING",
    "amount_cents": 2000,
}
CARD_PAYMENT = {
    "pair": 1,
    "status": "auto",
    "out": {
        "id": 7,
        "posted": "2026-05-10",
        "account": "Test Checking",
        "description": "PAYMENT TO TEST CARD",
        "amount_cents": -50000,
    },
    "in": {
        "id": 8,
        "posted": "2026-05-11",
        "account": "Test Card",
        "description": "PAYMENT THANK YOU",
        "amount_cents": 50000,
    },
}


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def queues(tmp_settings: Settings) -> Settings:
    """The dashboard's data: a card payment that pairs, a move to savings with two possible
    inflows, six transactions without a category, and three rules. Ids follow the rows."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card").id
        checking = create_account(session, "Test Checking", "Test Bank", "checking").id
        savings = create_account(session, "Test Savings", "Test Bank", "savings").id
        rows = [
            (card, date(2026, 4, 12), -3000, "FOOBAR GROCERY"),
            (checking, date(2026, 4, 15), 300000, "PAYCHECK EXAMPLE CORP"),
            (card, date(2026, 5, 3), -1500, "BAZ BOOKS"),
            (checking, date(2026, 5, 5), -2000, "TRANSFER TO SAVINGS"),
            (savings, date(2026, 5, 5), 2000, "TRANSFER FROM CHECKING"),
            (savings, date(2026, 5, 6), 2000, "TRANSFER FROM CHECKING"),
            (checking, date(2026, 5, 10), -50000, "PAYMENT TO TEST CARD"),
            (card, date(2026, 5, 11), 50000, "PAYMENT THANK YOU"),
            (card, date(2026, 5, 10), -20000, "FOOBAR GROCERY"),
            (card, date(2026, 5, 20), -3500, "LATE FEE"),
            (card, date(2026, 5, 28), -2345, "PURCHASE INTEREST CHARGE"),
            *(
                (card, date(2026, 5, day), -500, "ACME COFFEE")
                for day in (1, 2, 4, 6, 8, 11, 13, 15)
            ),
        ]
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
        session.flush()
        for pattern, category in (
            ("FOOBAR", "Groceries"),
            ("PAYCHECK", "Paycheck"),
            ("acme  coffee", "Coffee & Dessert"),
        ):
            create_rule(session, pattern, category)
        categorize(session)
        pair_transfers(session)
    engine.dispose()
    return tmp_settings


def test_sixteen_read_only_tools(tmp_settings: Settings) -> None:
    async def go():
        async with Client(build_server()) as client:
            return (await client.list_tools()).tools

    found = anyio.run(go)
    assert sorted(tool.name for tool in found) == TOOLS
    assert all(tool.annotations.read_only_hint for tool in found)


def test_uncategorized_latest_first_with_the_total(queues: Settings) -> None:
    found = call("list_uncategorized")
    assert found.is_error is False
    assert found.structured_content["total"] == 6
    assert [item["id"] for item in found.structured_content["transactions"]] == [11, 10, 6, 5, 4, 3]
    assert call("list_uncategorized", {"limit": 2}).structured_content == {
        "total": 6,
        "transactions": [
            {
                "id": 11,
                "posted": "2026-05-28",
                "account": "Test Card",
                "description": "PURCHASE INTEREST CHARGE",
                "amount_cents": -2345,
                "merchant": "PURCHASE INTEREST CHARGE",
            },
            {
                "id": 10,
                "posted": "2026-05-20",
                "account": "Test Card",
                "description": "LATE FEE",
                "amount_cents": -3500,
                "merchant": "LATE FEE",
            },
        ],
    }


def test_categories(queues: Settings) -> None:
    found = call("list_categories").structured_content["categories"]
    assert len(found) == 34
    assert [item["name"] for item in found[:3]] == [
        "Car Maintenance",
        "Clothing",
        "Coffee & Dessert",
    ]
    chosen = {
        item["name"]: item for item in found if item["name"] in ("Medical", "Paycheck", "Transfer")
    }
    assert chosen == {
        "Medical": {
            "name": "Medical",
            "group": "Health",
            "transfer": False,
            "income": False,
            "sensitive": True,
        },
        "Paycheck": {
            "name": "Paycheck",
            "group": "Income",
            "transfer": False,
            "income": True,
            "sensitive": False,
        },
        "Transfer": {
            "name": "Transfer",
            "group": "Transfers",
            "transfer": True,
            "income": False,
            "sensitive": False,
        },
    }
    assert all(item["group"] not in (None, "") for item in found)


def test_rules_in_the_order_they_are_tried(queues: Settings) -> None:
    assert call("list_rules").structured_content == {
        "rules": [
            {
                "id": 1,
                "priority": 0,
                "match": "contains",
                "pattern": "FOOBAR",
                "category": "Groceries",
            },
            {
                "id": 2,
                "priority": 0,
                "match": "contains",
                "pattern": "PAYCHECK",
                "category": "Paycheck",
            },
            {
                "id": 3,
                "priority": 0,
                "match": "contains",
                "pattern": "ACME COFFEE",
                "category": "Coffee & Dessert",
            },
        ]
    }


def test_suggestions_wait_for_a_person(queues: Settings) -> None:
    assert call("list_transfer_suggestions").structured_content == {
        "suggestions": [
            {"out": TO_SAVINGS, "in": FROM_CHECKING_5},
            {"out": TO_SAVINGS, "in": FROM_CHECKING_6},
        ]
    }


def test_transfers_newest_pair_first(queues: Settings) -> None:
    assert call("list_transfers").structured_content == {"total": 1, "pairs": [CARD_PAYMENT]}
    engine = get_engine()
    with session_scope(engine) as session:
        create_transfer_pair(session, 4, 5, CONFIRMED)
    engine.dispose()
    confirmed = {"pair": 2, "status": "confirmed", "out": TO_SAVINGS, "in": FROM_CHECKING_5}
    assert call("list_transfers").structured_content == {
        "total": 2,
        "pairs": [confirmed, CARD_PAYMENT],
    }
    assert call("list_transfers", {"limit": 1}).structured_content == {
        "total": 2,
        "pairs": [confirmed],
    }
    assert call("list_transfer_suggestions").structured_content == {"suggestions": []}


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("list_uncategorized", {"limit": 0}),
        ("list_uncategorized", {"limit": 501}),
        ("list_transfers", {"limit": 501}),
    ],
)
def test_limits_out_of_range(queues: Settings, tool: str, arguments: dict) -> None:
    result = call(tool, arguments)
    assert result.is_error is True
    assert result.content[0].text.startswith(f"Error executing tool {tool}: 1 validation error")


@pytest.mark.parametrize(
    "tool",
    [
        "list_uncategorized",
        "list_categories",
        "list_rules",
        "list_transfers",
        "list_transfer_suggestions",
    ],
)
def test_a_database_that_is_not_migrated(tmp_settings: Settings, tool: str) -> None:
    result = call(tool)
    assert [item.text for item in result.content] == [
        f"Error executing tool {tool}: The database is not up to date. Run: fin db upgrade"
    ]
