import logging
from datetime import date

import anyio
import pytest
from mcp.client import Client
from sqlalchemy.exc import OperationalError

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    create_person,
    set_account_active,
    set_account_owner,
)
from finances.domain.models import DataSource
from finances.mcp_server.access import reading
from finances.mcp_server.server import INSTRUCTIONS, build_server
from tests.support import MCP_TOOLS, MCP_WRITERS

NO_AMOUNTS = (
    "list_accounts",
    "list_categories",
    "list_rules",
    "find_merchants",
    "propose_category",
    "propose_merchant_alias",
    "list_proposals",
    "list_advice",
    "propose_transfer",
    "propose_not_transfer",
    "propose_rule",
    "propose_group",
    "propose_new_category",
    "propose_rule_change",
)
READ_ONLY = {
    "read_only_hint": True,
    "destructive_hint": False,
    "idempotent_hint": True,
    "open_world_hint": False,
}


def call(server, name: str, arguments: dict | None = None):
    async def go():
        async with Client(server) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def money(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """A card Pat owns, a joint checking account, savings with no owner and no balance, and a
    closed account."""
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 5, 25))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        pat = create_person(session, "Pat Example")
        card = create_account(session, "Test Card", "Example Card Co", "credit_card", last4="4321")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        create_account(session, "Test Savings", "Test Bank", "savings")
        old = create_account(session, "Test Old", "Test Bank", "checking")
        set_account_owner(session, card.id, pat.id)
        set_account_owner(session, checking.id, None)
        for account, day, cents, source in (
            (card, date(2026, 4, 30), -30000, DataSource.STATEMENT),
            (card, date(2026, 5, 24), -45000, DataSource.AGGREGATOR),
            (checking, date(2026, 4, 30), 250000, DataSource.STATEMENT),
            (checking, date(2026, 5, 20), 300000, DataSource.AGGREGATOR),
            (old, date(2026, 1, 31), 500000, DataSource.STATEMENT),
        ):
            add_balance_snapshot(session, account.id, day, cents, source)
        set_account_active(session, old.id, False)
    engine.dispose()
    return tmp_settings


def test_the_server_and_its_tools(tmp_settings: Settings) -> None:
    async def go():
        async with Client(build_server()) as client:
            return client.server_info.name, client.instructions, (await client.list_tools()).tools

    name, instructions, tools = anyio.run(go)
    assert (name, instructions) == ("finances", INSTRUCTIONS)
    assert sorted(tool.name for tool in tools) == MCP_TOOLS
    for tool in tools:
        if tool.name not in MCP_WRITERS:
            assert tool.annotations.model_dump(include=set(READ_ONLY)) == READ_ONLY, tool.name
        assert "cents" in tool.description or tool.name in NO_AMOUNTS, tool.name


def test_list_accounts(money: Settings) -> None:
    card = {
        "name": "Test Card",
        "institution": "Example Card Co",
        "type": "credit_card",
        "currency": "USD",
        "last4": "4321",
        "active": True,
        "owner": "Pat Example",
        "joint": False,
    }
    checking = {
        "name": "Test Checking",
        "institution": "Test Bank",
        "type": "checking",
        "currency": "USD",
        "last4": None,
        "active": True,
        "owner": None,
        "joint": True,
    }
    old = {
        "name": "Test Old",
        "institution": "Test Bank",
        "type": "checking",
        "currency": "USD",
        "last4": None,
        "active": False,
        "owner": None,
        "joint": False,
    }
    savings = {
        "name": "Test Savings",
        "institution": "Test Bank",
        "type": "savings",
        "currency": "USD",
        "last4": None,
        "active": True,
        "owner": None,
        "joint": False,
    }
    server = build_server()
    result = call(server, "list_accounts")
    assert result.is_error is False
    assert result.structured_content == {"accounts": [card, checking, savings]}
    found = call(server, "list_accounts", {"include_inactive": True}).structured_content
    assert found == {"accounts": [card, checking, old, savings]}


def test_get_balances(money: Settings) -> None:
    assert call(build_server(), "get_balances").structured_content == {
        "accounts": [
            {
                "name": "Test Card",
                "type": "credit_card",
                "balance_cents": -45000,
                "as_of": "2026-05-24",
                "source": "aggregator",
            },
            {
                "name": "Test Checking",
                "type": "checking",
                "balance_cents": 300000,
                "as_of": "2026-05-20",
                "source": "aggregator",
            },
            {
                "name": "Test Savings",
                "type": "savings",
                "balance_cents": None,
                "as_of": None,
                "source": None,
            },
        ],
        "cash_cents": 300000,
        "cards_cents": -45000,
        "other_cents": 0,
        "net_worth_cents": 255000,
        "without_balance": ["Test Savings"],
    }


def test_get_net_worth_follows_the_app_clock(money: Settings) -> None:
    assert call(build_server(), "get_net_worth", {"months": 3}).structured_content == {
        "as_of": "2026-05-25",
        "points": [
            {"day": "2026-04-30", "net_worth_cents": 220000, "accounts": 2},
            {"day": "2026-05-25", "net_worth_cents": 255000, "accounts": 2},
        ],
    }


@pytest.mark.parametrize("months", [0, 61])
def test_get_net_worth_refuses_months_out_of_range(money: Settings, months: int) -> None:
    result = call(build_server(), "get_net_worth", {"months": months})
    assert result.is_error is True
    assert result.content[0].text.startswith(
        "Error executing tool get_net_worth: 1 validation error"
    )


@pytest.mark.parametrize("tool", ["list_accounts", "get_balances", "get_net_worth"])
def test_a_database_that_is_not_migrated(tmp_settings: Settings, tool: str) -> None:
    result = call(build_server(), tool)
    assert result.is_error is True
    assert [item.text for item in result.content] == [
        f"Error executing tool {tool}: The database is not up to date. Run: fin db upgrade"
    ]


def test_the_tools_read_through_a_session_that_cannot_write(money: Settings) -> None:
    with pytest.raises(OperationalError, match="readonly database"):
        with reading() as session:
            create_account(session, "Test New", "Test Bank", "checking")
            session.flush()


def test_a_tool_that_crashes_logs_nothing(
    money: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    server = build_server()

    def crash() -> dict:
        raise RuntimeError("ACME COFFEE 1234")

    server.add_tool(crash)
    caplog.set_level(logging.DEBUG)
    result = call(server, "crash")
    assert (result.is_error, [item.text for item in result.content]) == (
        True,
        ["Error executing tool crash"],
    )
    assert [record.getMessage() for record in caplog.records if record.name.startswith("mcp")] == []
    assert "ACME" not in caplog.text
