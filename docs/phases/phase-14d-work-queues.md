# Phase 14d: the agent's work queues

## Goal

The agent can see what waits for a person, so it knows what to recommend on. After this phase the MCP server has five more read-only tools:

| Tool | Wraps | Gives |
|---|---|---|
| `list_uncategorized` | `list_uncategorized`, `count_uncategorized` (11a) | transactions without a category, latest first, with the total |
| `list_categories` | `list_categories` (11a) | every category, its group, and its flags |
| `list_rules` | `list_rules` (11a) | every rule in the order rules are tried |
| `list_transfers` | `list_transfer_pairs` (11c) | the pairs already made, newest first |
| `list_transfer_suggestions` | `transfer_suggestions` (11c) | the pairings waiting for a person |

These are what Phase 19's proposals will refer to (a category for a transaction, a rule, a transfer or not). The tools only read; a person still decides. The roadmap's outline called the last tool `transfer_suggestions`; it is named `list_transfer_suggestions` here, like the other lists.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-14a-mcp-server.md` (the SDK facts, `reading()`, the logging rule), `docs/phases/phase-14c-outlook-tools.md`
- `src/finances/mcp_server/tools.py`, `src/finances/mcp_server/server.py`
- `src/finances/db/repositories.py`: `list_uncategorized`, `count_uncategorized`, `list_categories`, `list_rules`, `list_transfer_pairs`, `get_transaction`, `account_names`; `src/finances/categorize/transfers.py` (`transfer_suggestions`); `src/finances/domain/merchants.py` (`clean_merchant`); `src/finances/domain/models.py` (`Category`: a group has `group_id` None; `TransferPair.status` is `auto` or `confirmed`)

## Starting state

N is `3203` when Phase 14c is the last phase built.

`tools.py` already imports `list_accounts` from the repositories under another name, since a tool has that name; do the same for the repository functions these tools share names with.

## Scope

| Path | What changes |
|---|---|
| `src/finances/mcp_server/tools.py` | five tools (R1 to R5) |
| `src/finances/mcp_server/server.py` | five descriptions and their registration (R6) |
| four earlier MCP test files | the given diff (R7) |
| `tests/integration/test_mcp_queues.py` | new: given |
| `tests/integration/test_mcp_queues_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Any write, proposal, or confirmation (Phase 19); data coverage and `find_merchants` (14e).
- Changes to the functions wrapped, to the web, or to the terminal.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/mcp_server/tools.py
def list_uncategorized(limit: Annotated[int, Field(ge=1, le=500)] = 50) -> dict[str, Any]: ...
def list_categories() -> dict[str, Any]: ...
def list_rules() -> dict[str, Any]: ...
def list_transfers(limit: Annotated[int, Field(ge=1, le=500)] = 100) -> dict[str, Any]: ...
def list_transfer_suggestions() -> dict[str, Any]: ...
```

Descriptions, in `server.py`, exactly:

```python
LIST_UNCATEGORIZED_DESCRIPTION = (
    "Transactions without a category and not part of a transfer, latest first, at most limit "
    "(1 to 500, default 50), with the total count: id, posted day, account, description, the "
    "cleaned merchant, and the amount in integer cents (money out negative)."
)
LIST_CATEGORIES_DESCRIPTION = (
    "Every category with its group and whether it counts as a transfer, as income, or as "
    "sensitive, in name order ignoring case. No amounts."
)
LIST_RULES_DESCRIPTION = (
    "Every categorizing rule in the order rules are tried (highest priority first, then "
    "oldest): id, priority, match (contains, starts_with, equals), the pattern as stored, and "
    "the category it sets. No amounts."
)
LIST_TRANSFERS_DESCRIPTION = (
    "Transfers already paired, newest pair first, at most limit (1 to 500, default 100), with "
    "the total: each pair's id, status (auto when the app paired it, confirmed when a person "
    "did), and its outflow and inflow (id, posted day, account, description, amount in "
    "integer cents)."
)
LIST_TRANSFER_SUGGESTIONS_DESCRIPTION = (
    "Possible transfers waiting for a person to decide, where more than one pairing was "
    "possible: each an outflow and an inflow of the same amount on different accounts (id, "
    "posted day, account, description, amount in integer cents). A person confirms or rejects "
    "them; these tools never do."
)
```

## Requirements

A **brief** of a transaction is `{"id", "posted" (ISO), "account" (its name), "description" (as stored), "amount_cents"}`. Each tool reads through `reading()` and returns one JSON object.

- **R1.** `list_uncategorized` returns `{"total": count_uncategorized(session), "transactions": [...]}` with `list_uncategorized(session, limit)` in its order, each item a brief plus `"merchant"` (`clean_merchant` of the description).
- **R2.** `list_categories` returns `{"categories": [...]}`: every category that has a group (`group_id` not None), in `list_categories`' order, each `{"name", "group" (the group's name), "transfer", "income", "sensitive"}` from its flags. Groups are not items.
- **R3.** `list_rules` returns `{"rules": [...]}` in `list_rules`' order, each `{"id", "priority", "match", "pattern" (as stored), "category" (the category's name)}`.
- **R4.** `list_transfers` returns `{"total": <number of pairs>, "pairs": [...]}`: the pairs of `list_transfer_pairs`, highest pair id first, at most `limit`, each `{"pair", "status", "out": brief, "in": brief}`.
- **R5.** `list_transfer_suggestions` returns `{"suggestions": [{"out": brief, "in": brief}, ...]}` in `transfer_suggestions`' order.
- **R6.** `server.py` defines the five descriptions above and registers the five tools after 14c's, with `READ_ONLY` and `structured_output=True`. Nothing is logged.
- **R7.** Apply the given diff to four earlier test files: the tool lists and the description table gain the five tools; 14a's check that every description but `list_accounts`' mentions cents also excepts `list_categories` and `list_rules` (they hold no amounts); 14c's `test_eleven_read_only_tools` becomes `test_the_read_only_tools`. No other earlier test changes.

## Given tests

14 tests in one file, on the dashboard's data, whose dashboard test already pins six uncategorized transactions and two suggestions. One test confirms a second pair by hand to decide the order and the limit.

`tests/integration/test_mcp_queues.py`

```python
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
```

The diff to earlier tests (apply it exactly):

```text
diff --git a/tests/integration/test_mcp_accounts.py b/tests/integration/test_mcp_accounts.py
index 1e806ec..c699df7 100644
--- a/tests/integration/test_mcp_accounts.py
+++ b/tests/integration/test_mcp_accounts.py
@@ -20,6 +20,7 @@ from finances.domain.models import DataSource
 from finances.mcp_server.access import reading
 from finances.mcp_server.server import INSTRUCTIONS, build_server
 
+NO_AMOUNTS = ("list_accounts", "list_categories", "list_rules")
 READ_ONLY = {
     "read_only_hint": True,
     "destructive_hint": False,
@@ -81,12 +82,17 @@ def test_the_server_and_its_tools(tmp_settings: Settings) -> None:
         "get_spending",
         "get_upcoming",
         "list_accounts",
+        "list_categories",
+        "list_rules",
         "list_transactions",
+        "list_transfer_suggestions",
+        "list_transfers",
+        "list_uncategorized",
         "month_over_month",
     ]
     for tool in tools:
         assert tool.annotations.model_dump(include=set(READ_ONLY)) == READ_ONLY, tool.name
-        assert "cents" in tool.description or tool.name == "list_accounts", tool.name
+        assert "cents" in tool.description or tool.name in NO_AMOUNTS, tool.name
 
 
 def test_list_accounts(money: Settings) -> None:
diff --git a/tests/integration/test_mcp_more.py b/tests/integration/test_mcp_more.py
index afaebc2..377fffe 100644
--- a/tests/integration/test_mcp_more.py
+++ b/tests/integration/test_mcp_more.py
@@ -22,7 +22,12 @@ from finances.mcp_server.server import (
     GET_SPENDING_DESCRIPTION,
     GET_UPCOMING_DESCRIPTION,
     LIST_ACCOUNTS_DESCRIPTION,
+    LIST_CATEGORIES_DESCRIPTION,
+    LIST_RULES_DESCRIPTION,
     LIST_TRANSACTIONS_DESCRIPTION,
+    LIST_TRANSFER_SUGGESTIONS_DESCRIPTION,
+    LIST_TRANSFERS_DESCRIPTION,
+    LIST_UNCATEGORIZED_DESCRIPTION,
     MONTH_OVER_MONTH_DESCRIPTION,
     build_server,
 )
@@ -136,6 +141,11 @@ def test_each_tool_description_matches_the_table(tmp_settings: Settings) -> None
         "get_upcoming": GET_UPCOMING_DESCRIPTION,
         "get_forecast": GET_FORECAST_DESCRIPTION,
         "get_budgets": GET_BUDGETS_DESCRIPTION,
+        "list_uncategorized": LIST_UNCATEGORIZED_DESCRIPTION,
+        "list_categories": LIST_CATEGORIES_DESCRIPTION,
+        "list_rules": LIST_RULES_DESCRIPTION,
+        "list_transfers": LIST_TRANSFERS_DESCRIPTION,
+        "list_transfer_suggestions": LIST_TRANSFER_SUGGESTIONS_DESCRIPTION,
     }
 
 
diff --git a/tests/integration/test_mcp_outlook.py b/tests/integration/test_mcp_outlook.py
index b0bddbf..433ee71 100644
--- a/tests/integration/test_mcp_outlook.py
+++ b/tests/integration/test_mcp_outlook.py
@@ -30,7 +30,12 @@ TOOLS = [
     "get_spending",
     "get_upcoming",
     "list_accounts",
+    "list_categories",
+    "list_rules",
     "list_transactions",
+    "list_transfer_suggestions",
+    "list_transfers",
+    "list_uncategorized",
     "month_over_month",
 ]
 CHECKING = {
@@ -201,7 +206,7 @@ def month(today: Settings) -> Settings:
     return today
 
 
-def test_eleven_read_only_tools(tmp_settings: Settings) -> None:
+def test_the_read_only_tools(tmp_settings: Settings) -> None:
     async def go():
         async with Client(build_server()) as client:
             return (await client.list_tools()).tools
diff --git a/tests/integration/test_mcp_spending.py b/tests/integration/test_mcp_spending.py
index 8a32afb..69e5d20 100644
--- a/tests/integration/test_mcp_spending.py
+++ b/tests/integration/test_mcp_spending.py
@@ -23,7 +23,12 @@ TOOLS = [
     "get_spending",
     "get_upcoming",
     "list_accounts",
+    "list_categories",
+    "list_rules",
     "list_transactions",
+    "list_transfer_suggestions",
+    "list_transfers",
+    "list_uncategorized",
     "month_over_month",
 ]
 REFUND = {
```

## Tests to write

`tests/integration/test_mcp_queues_more.py`: a rule with a priority above zero comes first; a category created by a person appears in order; a transaction set by hand is not uncategorized; a rejected suggestion is no longer listed; each tool on an empty database.

## Rules for this phase

- The tools are thin: they call the functions above and rename fields; the only ordering of their own is the newest-first pairs.
- Nothing is logged; `mcp_server` imports nothing from `views`, `web`, or `cli`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file: `tests/integration/test_mcp_queues.py`, 14 tests; at least N + 14 passed in all;
- `git diff --stat HEAD -- tests` lists only the four files of the given diff;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.mcp_server --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches from Phase 14a: `git grep -n --untracked -E "^ *(from|import) +finances\.(views|web|cli)" -- src/finances/mcp_server` and `git grep -n --untracked -E "\.(debug|info|warning|error|exception|critical)\(|print\(" -- src/finances/mcp_server src/finances/cli/mcp.py`, no output.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 14d: the agent's work queues (YYYY-MM-DD)`.
