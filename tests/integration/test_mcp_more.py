from datetime import date
from pathlib import Path

import anyio
import pytest
from mcp.client import Client
from sqlalchemy import text

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import add_balance_snapshot, create_account
from finances.domain.models import DataSource
from finances.mcp_server.access import reading
from finances.mcp_server.server import (
    DATA_COVERAGE_DESCRIPTION,
    FIND_MERCHANTS_DESCRIPTION,
    GET_BALANCES_DESCRIPTION,
    GET_BUDGETS_DESCRIPTION,
    GET_FORECAST_DESCRIPTION,
    GET_INSIGHTS_DESCRIPTION,
    GET_NET_WORTH_DESCRIPTION,
    GET_RECURRING_DESCRIPTION,
    GET_SPENDING_DESCRIPTION,
    GET_UPCOMING_DESCRIPTION,
    LIST_ACCOUNTS_DESCRIPTION,
    LIST_ADVICE_DESCRIPTION,
    LIST_CATEGORIES_DESCRIPTION,
    LIST_PROPOSALS_DESCRIPTION,
    LIST_RULES_DESCRIPTION,
    LIST_TRANSACTIONS_DESCRIPTION,
    LIST_TRANSFER_SUGGESTIONS_DESCRIPTION,
    LIST_TRANSFERS_DESCRIPTION,
    LIST_UNCATEGORIZED_DESCRIPTION,
    LOG_ADVICE_DESCRIPTION,
    MONTH_OVER_MONTH_DESCRIPTION,
    PROPOSE_CATEGORY_DESCRIPTION,
    build_server,
)
from tests.support import run


def call(server, name: str, arguments: dict | None = None):
    async def go():
        async with Client(server) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def test_read_only_engine_still_enforces_foreign_keys(tmp_path: Path) -> None:
    url = sqlite_url(tmp_path / "ro.db")
    engine = get_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE child (id INTEGER PRIMARY KEY, "
                "parent_id INTEGER NOT NULL REFERENCES parent (id))"
            )
        )
    engine.dispose()
    readonly = get_engine(url, read_only=True)
    with readonly.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert connection.execute(text("PRAGMA query_only")).scalar_one() == 1
    readonly.dispose()


def test_reading_disposes_the_engine_when_the_block_raises(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    upgrade_to_head()
    disposed: list[bool] = []
    real = get_engine

    def tracking(*args: object, **kwargs: object):
        engine = real(*args, **kwargs)
        original = engine.dispose

        def dispose() -> None:
            disposed.append(True)
            original()

        engine.dispose = dispose
        return engine

    monkeypatch.setattr("finances.mcp_server.access.get_engine", tracking)
    with pytest.raises(RuntimeError, match="boom"):
        with reading():
            raise RuntimeError("boom")
    assert disposed == [True]


def test_list_accounts_and_get_balances_with_no_accounts(tmp_settings: Settings) -> None:
    upgrade_to_head()
    server = build_server()
    assert call(server, "list_accounts").structured_content == {"accounts": []}
    found = call(server, "get_balances").structured_content
    assert found == {
        "accounts": [],
        "cash_cents": 0,
        "cards_cents": 0,
        "other_cents": 0,
        "net_worth_cents": 0,
        "without_balance": [],
    }


def test_get_net_worth_without_arguments_uses_twelve_months(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 5, 25))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        add_balance_snapshot(session, checking.id, date(2025, 6, 1), 100000, DataSource.STATEMENT)
    engine.dispose()
    server = build_server()
    default = call(server, "get_net_worth").structured_content
    explicit = call(server, "get_net_worth", {"months": 12}).structured_content
    assert default == explicit
    assert len(default["points"]) == 12
    assert default["as_of"] == "2026-05-25"


def test_each_tool_description_matches_the_table(tmp_settings: Settings) -> None:
    async def go():
        async with Client(build_server()) as client:
            return {tool.name: tool.description for tool in (await client.list_tools()).tools}

    found = anyio.run(go)
    assert found == {
        "list_accounts": LIST_ACCOUNTS_DESCRIPTION,
        "get_balances": GET_BALANCES_DESCRIPTION,
        "get_net_worth": GET_NET_WORTH_DESCRIPTION,
        "list_transactions": LIST_TRANSACTIONS_DESCRIPTION,
        "get_spending": GET_SPENDING_DESCRIPTION,
        "month_over_month": MONTH_OVER_MONTH_DESCRIPTION,
        "get_insights": GET_INSIGHTS_DESCRIPTION,
        "get_recurring": GET_RECURRING_DESCRIPTION,
        "get_upcoming": GET_UPCOMING_DESCRIPTION,
        "get_forecast": GET_FORECAST_DESCRIPTION,
        "get_budgets": GET_BUDGETS_DESCRIPTION,
        "list_uncategorized": LIST_UNCATEGORIZED_DESCRIPTION,
        "list_categories": LIST_CATEGORIES_DESCRIPTION,
        "list_rules": LIST_RULES_DESCRIPTION,
        "list_transfers": LIST_TRANSFERS_DESCRIPTION,
        "list_transfer_suggestions": LIST_TRANSFER_SUGGESTIONS_DESCRIPTION,
        "data_coverage": DATA_COVERAGE_DESCRIPTION,
        "find_merchants": FIND_MERCHANTS_DESCRIPTION,
        "propose_category": PROPOSE_CATEGORY_DESCRIPTION,
        "list_proposals": LIST_PROPOSALS_DESCRIPTION,
        "log_advice": LOG_ADVICE_DESCRIPTION,
        "list_advice": LIST_ADVICE_DESCRIPTION,
    }


def test_mcp_help_lists_serve(tmp_settings: Settings) -> None:
    result = run("mcp", "--help")
    assert result.exit_code == 0
    assert "serve" in result.stdout
