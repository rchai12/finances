import ast
from datetime import UTC, date, datetime
from pathlib import Path

import anyio
import pytest
from mcp.client import Client

import finances.mcp_server
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, list_category_assignments, set_category_by_hand
from finances.mcp_server.server import build_server
from tests.support import MCP_WRITERS

WRITERS = set(MCP_WRITERS)
FROM_REPOSITORIES = {
    "account_names",
    "count_uncategorized",
    "get_transaction",
    "list_account_owners",
    "list_accounts",
    "list_advice",
    "list_categories",
    "list_people",
    "list_proposals",
    "list_rules",
    "list_transfer_pairs",
    "list_uncategorized",
    "log_advice",
    "proposal_out_of_date",
    "propose_category",
    "propose_group",
    "propose_merchant_alias",
    "propose_new_category",
    "propose_not_transfer",
    "propose_rule",
    "propose_transfer",
}


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def one(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """A card with one coffee and no category."""
    monkeypatch.setattr(
        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=date(2026, 5, 1),
                amount_cents=-500,
                description="ACME COFFEE",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
    engine.dispose()
    return tmp_settings


def test_only_two_tools_write_and_none_decides(tmp_settings: Settings) -> None:
    async def go():
        async with Client(build_server()) as client:
            return (await client.list_tools()).tools

    tools = {tool.name: tool for tool in anyio.run(go)}
    assert {name for name, tool in tools.items() if not tool.annotations.read_only_hint} == WRITERS
    for name in WRITERS:
        assert tools[name].annotations.destructive_hint is False
    assert not [name for name in tools if "accept" in name or "decline" in name]


def test_the_server_reaches_only_these_repository_functions() -> None:
    folder = Path(finances.mcp_server.__file__).parent
    names = set()
    for path in folder.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module == "finances.db.repositories":
                names |= {alias.name for alias in node.names}
    assert names == FROM_REPOSITORIES


def test_a_proposal_and_its_listing(one: Settings) -> None:
    made = call(
        "propose_category",
        {"transaction_id": 1, "category": "Coffee & Dessert", "reason": "a cafe"},
    )
    expected = {
        "id": 1,
        "kind": "category",
        "transaction_id": 1,
        "in_id": None,
        "category": "Coffee & Dessert",
        "rule": None,
        "alias": None,
        "new": None,
        "waits_for": None,
        "reason": "a cafe",
        "status": "open",
        "created_at": "2026-05-25T12:00:00+00:00",
        "decided_at": None,
        "out_of_date": False,
    }
    assert made.structured_content == {"proposal": expected}
    engine = get_engine()
    with session_scope(engine) as session:
        assert list_category_assignments(session) == {}
        set_category_by_hand(session, 1, "Dining")
    engine.dispose()
    assert call("list_proposals").structured_content == {
        "proposals": [{**expected, "out_of_date": True}]
    }
    assert call("list_proposals", {"status": "declined"}).structured_content == {"proposals": []}


def test_a_refused_proposal(one: Settings) -> None:
    result = call("propose_category", {"transaction_id": 9, "category": "Dining", "reason": "why"})
    assert [item.text for item in result.content] == [
        "Error executing tool propose_category: transaction not found"
    ]


def test_the_agents_notes(one: Settings) -> None:
    kept = call("log_advice", {"text": "Suggested a coffee budget.", "subject": "budgets"})
    note = {
        "id": 1,
        "created_at": "2026-05-25T12:00:00+00:00",
        "subject": "budgets",
        "text": "Suggested a coffee budget.",
        "dismissed_at": None,
    }
    assert kept.structured_content == {"advice": note}
    assert call("list_advice").structured_content == {"advice": [note]}
    refused = call("log_advice", {"text": "  "})
    assert [item.text for item in refused.content] == [
        "Error executing tool log_advice: advice must be 1 to 1000 characters"
    ]


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("propose_category", {"transaction_id": 1, "category": "Dining", "reason": "why"}),
        ("log_advice", {"text": "note"}),
    ],
)
def test_a_database_that_is_not_migrated(
    tmp_settings: Settings, tool: str, arguments: dict
) -> None:
    assert [item.text for item in call(tool, arguments).content] == [
        f"Error executing tool {tool}: The database is not up to date. Run: fin db upgrade"
    ]
