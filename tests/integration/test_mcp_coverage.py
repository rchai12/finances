from datetime import UTC, date, datetime

import anyio
import pytest
from mcp.client import Client

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import FeedPullRow, TransactionRow
from finances.db.repositories import (
    create_account,
    create_rule,
    create_statement,
    map_feed_account,
)
from finances.domain.models import DEFAULT_LINK
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
    "list_categories",
    "list_rules",
    "list_transactions",
    "list_transfer_suggestions",
    "list_transfers",
    "list_uncategorized",
    "month_over_month",
]


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def data(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """A card with statements for January, February, and April (March missing) and no
    SimpleFIN; checking fed by SimpleFIN, pulled yesterday with $1.50 of drift; no backup."""
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 5, 20))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        months = [
            (date(2026, 1, 1), date(2026, 1, 31)),
            (date(2026, 2, 1), date(2026, 2, 28)),
            (date(2026, 4, 1), date(2026, 4, 30)),
        ]
        for number, (start, end) in enumerate(months):
            create_statement(
                session,
                account_id=card.id,
                source_filename=f"card-{number}.pdf",
                file_sha256=str(number) * 64,
                parser_name="test",
                period_start=start,
                period_end=end,
                opening_balance_cents=0,
                closing_balance_cents=0,
                lines_parsed=0,
                rows_inserted=0,
                rows_duplicate=0,
            )
        map_feed_account(session, checking.id, "ACT-1", link=DEFAULT_LINK)
        session.add(
            FeedPullRow(
                account_id=checking.id,
                inserted=0,
                updated=0,
                removed=0,
                unchanged=0,
                feed_total_cents=0,
                balance_cents=30000,
                balance_date=date(2026, 5, 19),
                drift_cents=-150,
                pulled_at=datetime(2026, 5, 19, 23, 45, tzinfo=UTC),
            )
        )
        rows = [
            (card, date(2026, 5, 10), -650, "ACME COFFEE #12"),
            (card, date(2026, 5, 11), -2599, "FOOBAR GROCERY #77"),
            (checking, date(2026, 5, 15), 300000, "PAYCHECK EXAMPLE CORP"),
            (card, date(2026, 5, 12), -1599, "QUUX STREAMING"),
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
        categorize(session)
    engine.dispose()
    return tmp_settings


def test_eighteen_read_only_tools(tmp_settings: Settings) -> None:
    async def go():
        async with Client(build_server()) as client:
            return (await client.list_tools()).tools

    found = anyio.run(go)
    assert sorted(tool.name for tool in found) == TOOLS
    assert all(tool.annotations.read_only_hint for tool in found)


def test_data_coverage(data: Settings) -> None:
    assert call("data_coverage").structured_content == {
        "as_of": "2026-05-20",
        "accounts": [
            {
                "name": "Test Card",
                "type": "credit_card",
                "first_day": "2026-01-01",
                "last_day": "2026-05-12",
                "audited": [
                    {"start": "2026-01-01", "end": "2026-02-28"},
                    {"start": "2026-04-01", "end": "2026-04-30"},
                ],
                "gaps": [{"start": "2026-03-01", "end": "2026-03-31"}],
                "newest_statement_end": "2026-04-30",
                "mapped": False,
                "last_pull": None,
                "drift_cents": None,
                "drift_date": None,
            },
            {
                "name": "Test Checking",
                "type": "checking",
                "first_day": "2026-05-15",
                "last_day": "2026-05-19",
                "audited": [],
                "gaps": [],
                "newest_statement_end": None,
                "mapped": True,
                "last_pull": "2026-05-19",
                "drift_cents": -150,
                "drift_date": "2026-05-19",
            },
        ],
        "problems": [
            {
                "kind": "backup",
                "account": None,
                "detail": "No backup yet.",
                "action": "Run fin backup run, or press Back up now on the Backups page.",
            },
            {
                "kind": "drift",
                "account": "Test Checking",
                "detail": "The balance differs from SimpleFIN's by -$1.50 on 2026-05-19.",
                "action": (
                    "Look for a missing or extra transaction, or import the statement"
                    " for that period."
                ),
            },
            {
                "kind": "gap",
                "account": "Test Card",
                "detail": "No statement covers 2026-03-01 to 2026-03-31.",
                "action": "Upload the statement for those days.",
            },
        ],
    }


@pytest.mark.parametrize(
    ("arguments", "matches"),
    [
        (
            {"phrase": "cofee"},
            [
                {"name": "ACME COFFEE", "kind": "merchant", "score": 91},
                {"name": "Coffee & Dessert", "kind": "category", "score": 91},
            ],
        ),
        (
            {"phrase": "paychek", "limit": 1},
            [{"name": "PAYCHECK EXAMPLE CORP", "kind": "merchant", "score": 93}],
        ),
        (
            {"phrase": "groceries"},
            [
                {"name": "Groceries", "kind": "category", "score": 100},
                {"name": "FOOBAR GROCERY", "kind": "merchant", "score": 75},
            ],
        ),
        ({"phrase": "xyz"}, []),
    ],
)
def test_find_merchants(data: Settings, arguments: dict, matches: list) -> None:
    assert call("find_merchants", arguments).structured_content == {"matches": matches}


@pytest.mark.parametrize(
    ("phrase", "message"),
    [("   ", "give a phrase to look for"), ("x" * 101, "a phrase is at most 100 characters")],
)
def test_a_refused_phrase(data: Settings, phrase: str, message: str) -> None:
    result = call("find_merchants", {"phrase": phrase})
    assert [item.text for item in result.content] == [
        f"Error executing tool find_merchants: {message}"
    ]


@pytest.mark.parametrize(
    "arguments", [{"phrase": "acme", "limit": 0}, {"phrase": "acme", "limit": 21}]
)
def test_a_limit_out_of_range(data: Settings, arguments: dict) -> None:
    result = call("find_merchants", arguments)
    assert result.is_error is True
    assert result.content[0].text.startswith(
        "Error executing tool find_merchants: 1 validation error"
    )


@pytest.mark.parametrize(
    ("tool", "arguments"), [("data_coverage", {}), ("find_merchants", {"phrase": "acme"})]
)
def test_a_database_that_is_not_migrated(
    tmp_settings: Settings, tool: str, arguments: dict
) -> None:
    assert [item.text for item in call(tool, arguments).content] == [
        f"Error executing tool {tool}: The database is not up to date. Run: fin db upgrade"
    ]
