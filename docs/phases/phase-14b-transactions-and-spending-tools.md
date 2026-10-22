# Phase 14b: the agent's transaction and spending tools

## Goal

The agent can see what was spent. After this phase the MCP server of Phase 14a has three more read-only tools:

- `list_transactions`: the web search's filters (text, account, person, category, group, merchant, bank, card, kind including `refund`, a start and end day), latest first, with paging;
- `get_spending`: spending over a period grouped one of seven ways, with 35a's **spent, refunds, and net** for each line and a summary;
- `month_over_month`: net spending and income for each of the last N months, with the accounts whose data does not cover a month.

Each wraps one existing function (`search_transactions`, `spending_report`, `month_report`) and returns one JSON object in integer cents. The roadmap's outline named three spending tools (by category, merchant, person); one `get_spending` with a `by` argument covers those and the other four groupings with one function, so this phase builds that instead.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-14a-mcp-server.md` (the server, `reading()`, the SDK facts, the logging rule)
- `src/finances/mcp_server/tools.py`, `src/finances/mcp_server/server.py`
- `src/finances/analysis/search.py` (`TransactionQuery`, `search_transactions` and its refusals), `src/finances/analysis/spending.py` (`spending_report`), `src/finances/analysis/months.py` (`month_report`), `src/finances/domain/spending.py` (`is_refund`, `UNCATEGORIZED`, `UNASSIGNED`, `month_bounds`, `month_range`)

## Starting state

N is `3145` when Phase 35b is the last phase built.

`search_transactions` includes pending transactions and returns them latest posted first; `spending_report` and `month_report` count posted transactions only. In `SpendingLine` and `SpendingSummary`, `spent_cents` is **net** (purchases minus refunds) and `purchases_cents` / `refunds_cents` hold the parts (35a); the tools rename them so each name says what it holds.

## Scope

| Path | What changes |
|---|---|
| `src/finances/mcp_server/tools.py` | three tools (R1 to R4) |
| `src/finances/mcp_server/server.py` | three descriptions and their registration (R5) |
| `tests/integration/test_mcp_accounts.py`, `tests/integration/test_mcp_more.py` | the given diff (R6) |
| `tests/integration/test_mcp_spending.py` | new: given |
| `tests/integration/test_mcp_spending_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Findings, recurring, upcoming, forecast, budgets, data coverage (14c); the work queues and `find_merchants` (14d).
- Any change to the functions the tools wrap, to the web, or to the terminal.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/mcp_server/tools.py
def list_transactions(
    text: str = "",
    account: str = "",
    person: str = "",
    category: str = "",
    group: str = "",
    merchant: str = "",
    bank: str = "",
    card: str = "",
    kind: str = "",
    start: date | None = None,
    end: date | None = None,
    limit: Annotated[int, Field(ge=1, le=200)] = 50,
    offset: Annotated[int, Field(ge=0, le=5000)] = 0,
) -> dict[str, Any]: ...

def get_spending(
    start: date | None = None,
    end: date | None = None,
    by: Literal["category", "group", "merchant", "person", "account", "bank", "card"] = "category",
) -> dict[str, Any]: ...

def month_over_month(
    month: str = "", count: Annotated[int, Field(ge=1, le=24)] = 6
) -> dict[str, Any]: ...
```

Descriptions, in `server.py`, exactly:

```python
LIST_TRANSACTIONS_DESCRIPTION = (
    "Transactions, latest first, filtered by any of: text in the description, account, person "
    "(a name, joint, or unassigned), category, group, merchant, bank, card (last 4 digits), "
    "kind (spending, income, transfer, unsorted_in, pending, refund), and a start and end day. "
    "Amounts in integer cents, money out negative. At most limit (1 to 200, default 50) per "
    "call; pass next_offset as offset for the next page."
)
GET_SPENDING_DESCRIPTION = (
    "Spending from start to end (ISO days, both or neither; default this month) grouped by "
    "category, group, merchant, person, account, bank, or card. Each line: spent_cents "
    "(purchases), refunds_cents (money back), net_cents (spent minus refunds, below zero when "
    "refunds win), and count; plus a summary with income, transfers left out, and money in "
    "without a category. Integer cents."
)
MONTH_OVER_MONTH_DESCRIPTION = (
    "Net spending (purchases minus refunds) and income in integer cents for each of the last N "
    "months (1 to 24, default 6) ending with the given month (YYYY-MM, default this month), "
    "oldest first, with the accounts whose data does not cover that whole month."
)
```

## Requirements

### Part 1: transactions

- **R1.** `list_transactions` refuses `start` after `end` with `ToolError("the start date is after the end date")` before reading. Otherwise it calls `search_transactions` once with a `TransactionQuery` of its filters and `limit = offset + limit + 1`, and turns a `ValueError` from it into a `ToolError` with the same message (`account not found`, `person not found`, the kind message). It returns `{"transactions": [...], "next_offset": ...}`: the found items from `offset` up to `offset + limit`, and `next_offset` equal to `offset + limit` when more were found, else `null`.
- **R2.** Each item is `{"id", "day", "posted", "account", "description", "merchant", "amount_cents", "kind", "refund", "category", "group", "person", "card", "pending"}`: `day` the flow's day and `posted` the posted date (ISO); `account` the account's name; `description` as stored and `merchant` the cleaned name; `kind` the flow's kind; `refund` from `is_refund`; `category` and `group` null when uncategorized; `person` null when unassigned; `card` the last 4 digits or null; `pending` as stored.

### Part 2: spending

- **R3.** `get_spending` takes both `start` and `end` or neither (else `ToolError("give both start and end, or neither")`); with neither it covers this month (`month_bounds(clock.today())`, looked up through the module). It calls `spending_report` and turns its `ValueError` into a `ToolError` with the same message. It returns `{"start", "end", "by", "lines": [...], "summary": {...}}`: each line `{"label", "spent_cents", "refunds_cents", "net_cents", "count"}` with `spent_cents` the purchases (`purchases_cents`) and `net_cents` the line's `spent_cents`, in the report's order; the summary `{"spent_cents", "refunds_cents", "net_cents", "income_cents", "transfers", "unsorted_in_cents", "unsorted_in_count"}`, named the same way.
- **R4.** `month_over_month` reads `month` with `month_range` (a `ValueError` becomes a `ToolError` with its message) and uses that month's last day, or `clock.today()` when `month` is empty, as the day passed to `month_report(session, day, count)`. It returns `{"months": [...]}`, oldest first, each `{"month": "YYYY-MM", "net_cents", "income_cents", "uncovered": [account names]}`.

### Part 3: the server

- **R5.** `server.py` defines the three descriptions above and registers the three tools after 14a's three, with the same `READ_ONLY` annotations and `structured_output=True`. Every tool reads through `reading()`; nothing is logged.
- **R6.** Apply the given diff to two earlier test files (the tool list and the description table gain the three tools). No other earlier test changes.

## Given tests

27 tests in one file. `finances.clock.today` is replaced with 2026-05-29; the expected values were worked by hand from the fixture.

`tests/integration/test_mcp_spending.py`

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
from finances.db.repositories import create_account, create_person, create_rule, set_account_owner
from finances.mcp_server.server import build_server

TOOLS = [
    "get_balances",
    "get_net_worth",
    "get_spending",
    "list_accounts",
    "list_transactions",
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


def test_six_read_only_tools(tmp_settings: Settings) -> None:
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
```

The diff to earlier tests (apply it exactly):

```text
diff --git a/tests/integration/test_mcp_accounts.py b/tests/integration/test_mcp_accounts.py
index ca06f85..cd3ae47 100644
--- a/tests/integration/test_mcp_accounts.py
+++ b/tests/integration/test_mcp_accounts.py
@@ -71,7 +71,14 @@ def test_the_server_and_its_tools(tmp_settings: Settings) -> None:
 
     name, instructions, tools = anyio.run(go)
     assert (name, instructions) == ("finances", INSTRUCTIONS)
-    assert sorted(tool.name for tool in tools) == ["get_balances", "get_net_worth", "list_accounts"]
+    assert sorted(tool.name for tool in tools) == [
+        "get_balances",
+        "get_net_worth",
+        "get_spending",
+        "list_accounts",
+        "list_transactions",
+        "month_over_month",
+    ]
     for tool in tools:
         assert tool.annotations.model_dump(include=set(READ_ONLY)) == READ_ONLY, tool.name
         assert "cents" in tool.description or tool.name == "list_accounts", tool.name
diff --git a/tests/integration/test_mcp_more.py b/tests/integration/test_mcp_more.py
index 8c3ba22..5d0205e 100644
--- a/tests/integration/test_mcp_more.py
+++ b/tests/integration/test_mcp_more.py
@@ -15,7 +15,10 @@ from finances.mcp_server.access import reading
 from finances.mcp_server.server import (
     GET_BALANCES_DESCRIPTION,
     GET_NET_WORTH_DESCRIPTION,
+    GET_SPENDING_DESCRIPTION,
     LIST_ACCOUNTS_DESCRIPTION,
+    LIST_TRANSACTIONS_DESCRIPTION,
+    MONTH_OVER_MONTH_DESCRIPTION,
     build_server,
 )
 from tests.support import run
@@ -120,6 +123,9 @@ def test_each_tool_description_matches_the_table(tmp_settings: Settings) -> None
         "list_accounts": LIST_ACCOUNTS_DESCRIPTION,
         "get_balances": GET_BALANCES_DESCRIPTION,
         "get_net_worth": GET_NET_WORTH_DESCRIPTION,
+        "list_transactions": LIST_TRANSACTIONS_DESCRIPTION,
+        "get_spending": GET_SPENDING_DESCRIPTION,
+        "month_over_month": MONTH_OVER_MONTH_DESCRIPTION,
     }
 
 
```

## Tests to write

`tests/integration/test_mcp_spending_more.py`: the `account`, `bank`, and `group` filters; a closed account's transactions are listed; `limit` 200 with more than 200 transactions gives `next_offset` 200; `get_spending` by merchant, account, bank, card, and group; a period with no spending (`lines` empty, summary zeros); `month_over_month` with `count` 24.

## Rules for this phase

- The tools are thin: no sums, sorting, or filtering beyond slicing the page; every figure comes from the wrapped function.
- Refusals are `ToolError`s with the wrapped function's own constant messages; no tool echoes an argument.
- Nothing is logged; `mcp_server` imports nothing from `views`, `web`, or `cli`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file: `tests/integration/test_mcp_spending.py`, 27 tests; at least N + 27 passed in all;
- `git diff --stat HEAD -- tests` lists only the two files of the given diff;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.mcp_server --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches from Phase 14a: `git grep -n --untracked -E "^ *(from|import) +finances\.(views|web|cli)" -- src/finances/mcp_server` and `git grep -n --untracked -E "\.(debug|info|warning|error|exception|critical)\(|print\(" -- src/finances/mcp_server src/finances/cli/mcp.py`, no output.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 14b: the agent's transaction and spending tools (YYYY-MM-DD)`.
