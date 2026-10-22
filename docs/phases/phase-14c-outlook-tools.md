# Phase 14c: the agent's outlook tools

## Goal

The agent can see what the app already works out about the household's habits and what is coming. After this phase the MCP server has five more read-only tools, each wrapping one existing report:

| Tool | Wraps | Gives |
|---|---|---|
| `get_insights` | `insights_report` (13b, 13d, 26a) | a month's findings and merchant statistics |
| `get_recurring` | `recurring_charges`, `recurring_income` (13a, 27a) | recurring charges, or income |
| `get_upcoming` | `upcoming_report` (27a) | bills and income expected in the next N days |
| `get_forecast` | `forecast_report` (27b) | each account's 30-day forecast, or one account's |
| `get_budgets` | `budget_report` (26a) | a month's budgets and their progress |

Data coverage moves to Phase 14e with `find_merchants` (it needs new combining logic, not a wrapper); 14d keeps the work queues.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-14a-mcp-server.md` (the SDK facts, `reading()`, the logging rule), `docs/phases/phase-14b-transactions-and-spending-tools.md`
- `src/finances/mcp_server/tools.py`, `src/finances/mcp_server/server.py`
- `src/finances/analysis/insights.py`, `analysis/recurring.py`, `analysis/upcoming.py`, `analysis/forecast.py`, `analysis/budgets.py`; `src/finances/domain/insights.py` (`Finding`, `MerchantStat`), `domain/recurring.py` (`Recurring`: amounts are sizes, never signed), `domain/upcoming.py`, `domain/forecast.py`, `domain/budgets.py` (`BudgetLine`: `spent_cents` is net)

## Starting state

N is `3182` when Phase 14b is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/mcp_server/tools.py` | five tools (R1 to R5) |
| `src/finances/mcp_server/server.py` | five descriptions and their registration (R6) |
| three earlier MCP test files | the given diff (R7) |
| `tests/integration/test_mcp_outlook.py` | new: given |
| `tests/integration/test_mcp_outlook_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Data coverage and `find_merchants` (14e); the work queues (14d); any write.
- Changes to the reports the tools wrap, to the web, or to the terminal.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/mcp_server/tools.py
def get_insights(month: str = "") -> dict[str, Any]: ...
def get_recurring(income: bool = False, include_inactive: bool = False) -> dict[str, Any]: ...
def get_upcoming(days: Annotated[int, Field(ge=1, le=90)] = 30) -> dict[str, Any]: ...
def get_forecast(
    days: Annotated[int, Field(ge=1, le=90)] = 30, account: str = ""
) -> dict[str, Any]: ...
def get_budgets(month: str = "") -> dict[str, Any]: ...
```

Descriptions, in `server.py`, exactly:

```python
GET_INSIGHTS_DESCRIPTION = (
    "Findings for a month (YYYY-MM, default this month): each with its type, severity (high, "
    "medium, low), subject (a category or merchant, or null), what acting on it could save a "
    "month in integer cents, and a sentence; and each merchant's visits, spending, average, "
    "baseline from earlier months, change, and weekend visits, in integer cents."
)
GET_RECURRING_DESCRIPTION = (
    "Recurring charges, or recurring income when income is true, found up to today: merchant, "
    "cadence (week, two_weeks, month, quarter, year), the last amount and its monthly cost in "
    "integer cents (charges negative, income positive), how many were seen, the first, last, "
    "and next day, and whether it is still active. Stopped series only when include_inactive "
    "is true."
)
GET_UPCOMING_DESCRIPTION = (
    "Bills and income expected in the next N days (1 to 90, default 30, today the first) from "
    "the active recurring series: day, bill or income, merchant, cadence, and amount in integer "
    "cents (bills negative), with the total of each."
)
GET_FORECAST_DESCRIPTION = (
    "Each account's balance walked forward through its own expected bills and income for the "
    "next N days (1 to 90, default 30): the starting balance and its date, expected in and out, "
    "the end, and the lowest point with its day, in integer cents, with each step; or one "
    "account when account is given. Accounts with no balance are listed by name."
)
GET_BUDGETS_DESCRIPTION = (
    "Each budget for a month (YYYY-MM, default this month): category or group, monthly target, "
    "net spending so far (purchases minus refunds), what is left, the share used, and the share "
    "of the month gone, in integer cents and whole percents."
)
```

## Requirements

Today is `finances.clock.today()`, looked up through the module when a tool runs. A `month` argument is read with `month_range` (its `ValueError` becomes a `ToolError` with the same message); empty means this month. Each tool reads through `reading()` and returns one JSON object; dates are ISO, months `YYYY-MM`.

- **R1.** `get_insights` returns `insights_report(session, first day of the month)` as `{"month", "findings": [...], "merchants": [...]}`: each finding `{"type", "severity", "subject", "savings_cents", "detail"}` with `subject` null when empty; each merchant `{"merchant", "visits", "spent_cents", "average_cents", "baseline_cents", "change_cents", "weekend_visits"}`, in the report's order.
- **R2.** `get_recurring` returns `recurring_income(session, today)` when `income` is true, else `recurring_charges(session, today)`, keeping inactive series only when `include_inactive` is true, as `{"as_of", "income", "series": [...]}`: each `{"merchant", "cadence", "amount_cents", "monthly_cents", "count", "first_day", "last_day", "next_day", "active", "previous_cents"}`, with the three amounts **signed as the account holder sees them**: below zero for charges, above zero for income (`previous_cents` null when there was no change).
- **R3.** `get_upcoming` returns `upcoming_report(session, today, days)` as `{"start", "end", "items": [...], "bills_cents", "income_cents"}`, each item `{"day", "kind", "merchant", "cadence", "amount_cents"}`.
- **R4.** `get_forecast` returns `forecast_report(session, today, days, account or None)` as `{"start", "end", "accounts": [...], "no_balance": [...]}`, each account `{"account", "balance_cents", "balance_day", "in_cents", "out_cents", "end_cents", "lowest_cents", "lowest_day", "steps": [{"day", "merchant", "amount_cents", "balance_cents"}]}`. Its `ValueError` (`account not found`, `NAME has no balance yet`) becomes a `ToolError` with the same message.
- **R5.** `get_budgets` returns `budget_report(session, first day of the month, today)` as `{"month", "budgets": [...]}`, each `{"name", "kind" ("group" or "category"), "target_cents", "net_cents" (the line's `spent_cents`), "left_cents", "used_percent", "month_gone_percent"}`.
- **R6.** `server.py` defines the five descriptions above and registers the five tools after 14b's, with `READ_ONLY` and `structured_output=True`. Nothing is logged.
- **R7.** Apply the given diff to three earlier test files: the tool lists and the description table gain the five tools, and 14b's `test_six_read_only_tools` becomes `test_the_read_only_tools`. No other earlier test changes.

## Given tests

16 tests in one file, on two fixtures whose results earlier phases already pin: Phase 27b's data (recurring, upcoming, forecast, and a budget) and the dashboard's May 2026 (findings, plus a gym that stopped in January). `finances.clock.today` is 2026-05-25.

`tests/integration/test_mcp_outlook.py`

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
    "get_balances",
    "get_budgets",
    "get_forecast",
    "get_insights",
    "get_net_worth",
    "get_recurring",
    "get_spending",
    "get_upcoming",
    "list_accounts",
    "list_transactions",
    "month_over_month",
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


def test_eleven_read_only_tools(tmp_settings: Settings) -> None:
    async def go():
        async with Client(build_server()) as client:
            return (await client.list_tools()).tools

    found = anyio.run(go)
    assert sorted(tool.name for tool in found) == TOOLS
    assert all(tool.annotations.read_only_hint for tool in found)


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
```

The diff to earlier tests (apply it exactly):

```text
diff --git a/tests/integration/test_mcp_accounts.py b/tests/integration/test_mcp_accounts.py
index cd3ae47..1e806ec 100644
--- a/tests/integration/test_mcp_accounts.py
+++ b/tests/integration/test_mcp_accounts.py
@@ -73,8 +73,13 @@ def test_the_server_and_its_tools(tmp_settings: Settings) -> None:
     assert (name, instructions) == ("finances", INSTRUCTIONS)
     assert sorted(tool.name for tool in tools) == [
         "get_balances",
+        "get_budgets",
+        "get_forecast",
+        "get_insights",
         "get_net_worth",
+        "get_recurring",
         "get_spending",
+        "get_upcoming",
         "list_accounts",
         "list_transactions",
         "month_over_month",
diff --git a/tests/integration/test_mcp_more.py b/tests/integration/test_mcp_more.py
index 5d0205e..afaebc2 100644
--- a/tests/integration/test_mcp_more.py
+++ b/tests/integration/test_mcp_more.py
@@ -14,8 +14,13 @@ from finances.domain.models import DataSource
 from finances.mcp_server.access import reading
 from finances.mcp_server.server import (
     GET_BALANCES_DESCRIPTION,
+    GET_BUDGETS_DESCRIPTION,
+    GET_FORECAST_DESCRIPTION,
+    GET_INSIGHTS_DESCRIPTION,
     GET_NET_WORTH_DESCRIPTION,
+    GET_RECURRING_DESCRIPTION,
     GET_SPENDING_DESCRIPTION,
+    GET_UPCOMING_DESCRIPTION,
     LIST_ACCOUNTS_DESCRIPTION,
     LIST_TRANSACTIONS_DESCRIPTION,
     MONTH_OVER_MONTH_DESCRIPTION,
@@ -126,6 +131,11 @@ def test_each_tool_description_matches_the_table(tmp_settings: Settings) -> None
         "list_transactions": LIST_TRANSACTIONS_DESCRIPTION,
         "get_spending": GET_SPENDING_DESCRIPTION,
         "month_over_month": MONTH_OVER_MONTH_DESCRIPTION,
+        "get_insights": GET_INSIGHTS_DESCRIPTION,
+        "get_recurring": GET_RECURRING_DESCRIPTION,
+        "get_upcoming": GET_UPCOMING_DESCRIPTION,
+        "get_forecast": GET_FORECAST_DESCRIPTION,
+        "get_budgets": GET_BUDGETS_DESCRIPTION,
     }
 
 
diff --git a/tests/integration/test_mcp_spending.py b/tests/integration/test_mcp_spending.py
index d31d674..8a32afb 100644
--- a/tests/integration/test_mcp_spending.py
+++ b/tests/integration/test_mcp_spending.py
@@ -15,8 +15,13 @@ from finances.mcp_server.server import build_server
 
 TOOLS = [
     "get_balances",
+    "get_budgets",
+    "get_forecast",
+    "get_insights",
     "get_net_worth",
+    "get_recurring",
     "get_spending",
+    "get_upcoming",
     "list_accounts",
     "list_transactions",
     "month_over_month",
@@ -96,7 +101,7 @@ def money(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
     return tmp_settings
 
 
-def test_six_read_only_tools(tmp_settings: Settings) -> None:
+def test_the_read_only_tools(tmp_settings: Settings) -> None:
     async def go():
         async with Client(build_server()) as client:
             return (await client.list_tools()).tools
```

## Tests to write

`tests/integration/test_mcp_outlook_more.py`: a recurring charge whose price changed (`previous_cents` signed); `get_upcoming` and `get_forecast` with defaults (30 days); a group budget; `get_insights` for a month with no data (empty lists); `get_budgets` for a past month.

## Rules for this phase

- The tools are thin: they call one report each, filter inactive series, sign recurring amounts, and rename fields; no other arithmetic.
- Refusals are `ToolError`s with the report's own constant message.
- Nothing is logged; `mcp_server` imports nothing from `views`, `web`, or `cli`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file: `tests/integration/test_mcp_outlook.py`, 16 tests; at least N + 16 passed in all;
- `git diff --stat HEAD -- tests` lists only the three files of the given diff;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.mcp_server --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches from Phase 14a: `git grep -n --untracked -E "^ *(from|import) +finances\.(views|web|cli)" -- src/finances/mcp_server` and `git grep -n --untracked -E "\.(debug|info|warning|error|exception|critical)\(|print\(" -- src/finances/mcp_server src/finances/cli/mcp.py`, no output.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 14c: the agent's outlook tools (YYYY-MM-DD)`.
