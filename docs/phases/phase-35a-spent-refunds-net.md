# Phase 35a: Spent, Refunds, and Net

## Goal

Spending stops using a sign that means two things. Today a category's Spent is its purchases minus its refunds, written as a positive number, so `$500.00` means money out; but when refunds exceed purchases in the period (a purchase last month, its refund this month) the same column shows `-$100.00`, meaning money back, while on the Transactions page a minus means money out. With 16n's colours that net refund also shows in red.

After this phase every spending table shows **Spent** (purchases only), **Refunds** (money back only), and **Net** (Spent minus Refunds), and no spending figure anywhere uses a minus to mean money back: a net refund reads `$5.99 back`, in green. Totals do not change: refunds keep reducing spending in reports, budgets, and insights exactly as now. Refund labels, the `refund` filter, and matching a refund to its purchase are Phase 35b.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/roadmap.md`, Phase 35
- `src/finances/domain/spending.py` (`SpendingLine`, `SpendingSummary`, `spending_lines`, `summarize`), `src/finances/views/spending.py`, `src/finances/views/account_page.py`, `src/finances/views/months.py`, `src/finances/views/budgets.py`, `src/finances/views/format.py` (`amount_class`), `src/finances/cli/reports.py` (`fin spending`), `src/finances/web/templates/reports.html`, `src/finances/web/templates/account.html`

## Starting state

N is `3093` when Phase 16n is the last phase built.

A refund is a flow of kind `SPENDING` above zero (money in with a spending category). `spending_lines` and `summarize` already net it into `spent_cents`; that stays.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/spending.py` | `refunds_cents`, `purchases_cents` (R1, R2) |
| `src/finances/views/format.py` | `net_text`; `amount_class` (R3, R4) |
| `src/finances/views/spending.py`, `src/finances/views/account_page.py` | rows and the summary (R5, R6, R7) |
| `src/finances/views/months.py`, `src/finances/views/budgets.py` | net text (R7, R8) |
| `src/finances/cli/reports.py` | `fin spending`'s headings (R9) |
| `src/finances/web/templates/reports.html`, `src/finances/web/templates/account.html` | the spending tables (R9) |
| six earlier test files | the given diff (R10) |
| `tests/unit/test_net_text.py`, `tests/e2e/test_cli_refunds.py`, `tests/integration/test_web_refunds.py` | new: given |
| `tests/integration/test_refunds_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Phase 35b: refund labels on transactions, a `refund` filter, matching a refund to its purchase, flags on uncategorized money in.
- Any change to a total, a budget's left or over-budget rule, the months table's Change column, insights, the pie chart, or the agent's tools.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/spending.py
@dataclass(frozen=True)
class SpendingLine:
    label: str
    spent_cents: int        # net, as today: purchases minus refunds
    count: int
    refunds_cents: int = 0  # new, last: money back, never below zero

    @property
    def purchases_cents(self) -> int: ...  # spent_cents + refunds_cents


@dataclass(frozen=True)
class SpendingSummary:
    spent_cents: int
    income_cents: int
    transfers: int
    unsorted_in_cents: int
    unsorted_in_count: int
    refunds_cents: int = 0  # new, last

# src/finances/views/format.py
def net_text(cents: int) -> str: ...  # "$15.00", or "$5.99 back" below zero

# src/finances/views/spending.py
@dataclass(frozen=True)
class SpendingRow:
    label: str
    spent: str     # purchases
    refunds: str
    net: str       # net_text
    count: str
```

## Requirements

### Part 1: the figures

- **R1.** `SpendingLine` gains `refunds_cents` (last, default 0) and the property `purchases_cents` (`spent_cents + refunds_cents`). `spending_lines` sets each line's `refunds_cents` to the sum of its `SPENDING` flows above zero; `spent_cents`, `count`, and the order of lines do not change.
- **R2.** `SpendingSummary` gains `refunds_cents` (last, default 0); `summarize` sets it the same way. Income, transfers, and money in without a category are never refunds.

### Part 2: the text

- **R3.** `net_text(cents)` is `format_cents(cents)` for zero and above, and `format_cents(-cents) + " back"` below zero (`-599` gives `$5.99 back`).
- **R4.** `amount_class` gives `"amount pos"` also for text ending in ` back`; everything else as in 16n.
- **R5.** `SpendingRow` is `label, spent, refunds, net, count`: `spent` is `format_cents(purchases_cents)`, `refunds` is `format_cents(refunds_cents)`, `net` is `net_text(spent_cents)`. `spending_rows` and the account page's `group_rows` both build it.
- **R6.** `spending_summary`'s first line is `Spent: $P. Refunds: $R. Net: N. Income: $I.` (P purchases, R refunds, N `net_text` of the net); the other lines do not change.
- **R7.** The months tables say `back` instead of a minus: `month_rows`' and `account_month_rows`' spent use `net_text`. The Change column does not change.
- **R8.** `budget_rows`' spent uses `net_text`, and its used percentage is never shown below `0%`. Left, the over-budget count, and every stored figure do not change.

### Part 3: the tables

- **R9.** `fin spending` prints the columns `<By>`, `Spent`, `Refunds`, `Net`, `Count`. The spending tables of `reports.html` and `account.html` have the heading cells `<th class="amount">Spent</th><th class="amount">Refunds</th><th class="amount">Net</th><th class="amount">Count</th>` after the label, and one body cell for each, written as 16n's other amount cells (`<td class="{{ row.X|amount_class }}">{{ row.X }}</td>`), in that order. The label cell and its link do not change.
- **R10.** Apply the given diff to six earlier test files: their spending rows gain the two columns (values worked from each test's data), the Reports test's table reader stops at a spending heading, and the drill-down test reads the count from the fifth cell. No other earlier test changes.

## Given tests

14 new tests in three files, and the diff to earlier tests. The new tests share one case: groceries bought in May for $25.99 and $5.99 of it refunded in June, so June's spending is money back.

`tests/unit/test_net_text.py`

```python
import pytest

from finances.domain.spending import SpendingLine
from finances.views.format import amount_class, net_text


@pytest.mark.parametrize(
    ("cents", "text"),
    [(0, "$0.00"), (1500, "$15.00"), (-599, "$5.99 back"), (-123456, "$1,234.56 back")],
)
def test_net_spending_never_shows_a_minus(cents: int, text: str) -> None:
    assert net_text(cents) == text


@pytest.mark.parametrize(
    ("text", "classes"),
    [("$5.99 back", "amount pos"), ("$5.99", "amount"), ("-$5.99", "amount neg")],
)
def test_money_back_reads_as_a_gain(text: str, classes: str) -> None:
    assert amount_class(text) == classes


def test_purchases_are_net_spending_plus_refunds() -> None:
    assert SpendingLine("QUUX", -500, 2, 700).purchases_cents == 200
    assert SpendingLine("Food", 500, 2).purchases_cents == 500
```

`tests/e2e/test_cli_refunds.py`

```python
from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from tests.support import plain_lines, run, table_rows

JUNE = ("--month", "2026-06")


@pytest.fixture
def refunded(tmp_settings: Settings) -> Settings:
    """Groceries bought in May and partly refunded in June; a box bought in May; nothing else
    in June. A Groceries budget of $100.00."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [
            (date(2026, 5, 10), -2599, "FOOBAR GROCERY"),
            (date(2026, 5, 14), -1200, "BAZ BOX"),
            (date(2026, 6, 12), 599, "FOOBAR GROCERY"),
        ]
        for number, (day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    assert run("rules", "add", "--pattern", "FOOBAR", "--category", "Groceries").exit_code == 0
    assert run("budgets", "set", "--name", "Groceries", "--amount", "100").exit_code == 0
    return tmp_settings


def test_a_month_where_refunds_win(refunded: Settings) -> None:
    result = run("spending", *JUNE)
    assert table_rows(result.stdout) == [
        ["Category", "Spent", "Refunds", "Net", "Count"],
        ["Groceries", "$0.00", "$5.99", "$5.99 back", "1"],
    ]
    assert plain_lines(result.stdout) == [
        "Spending from 2026-06-01 to 2026-06-30, by category.",
        "Spent: $0.00. Refunds: $5.99. Net: $5.99 back. Income: $0.00.",
        "Transfers left out: 0.",
    ]


def test_the_months_table_says_back(refunded: Settings) -> None:
    rows = table_rows(run("months", "--to", "2026-06", "--count", "2").stdout)
    assert rows == [
        ["Month", "Spent", "Income", "Change", "Covered"],
        ["2026-05", "$37.99", "$0.00", "", "partly"],
        ["2026-06", "$5.99 back", "$0.00", "-$43.98", "partly"],
    ]


def test_a_budget_with_money_back_is_not_below_zero_used(refunded: Settings) -> None:
    rows = table_rows(run("budgets", "list", *JUNE).stdout)
    assert [row[:6] for row in rows] == [
        ["Budget", "Kind", "Target", "Spent", "Left", "Used"],
        ["Groceries", "category", "$100.00", "$5.99 back", "$105.99", "0%"],
    ]
```

`tests/integration/test_web_refunds.py`

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule, set_budget
from finances.web.app import create_app
from tests.support import WEB_PORT, page, texts

SPENDING = ["Category", "Spent", "Refunds", "Net", "Count"]
GROUPS = ["Group", "Spent", "Refunds", "Net", "Count"]
BACK = '<td class="amount pos">$5.99 back</td>'


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: date(2026, 6, 20))
    return found


@pytest.fixture
def refunded(client: TestClient) -> TestClient:
    """Groceries bought in May and partly refunded in June; a box bought in May."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [
            (date(2026, 5, 10), -2599, "FOOBAR GROCERY"),
            (date(2026, 5, 14), -1200, "BAZ BOX"),
            (date(2026, 6, 12), 599, "FOOBAR GROCERY"),
        ]
        for number, (day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=card.id,
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
        set_budget(session, "Groceries", 10000)
    engine.dispose()
    return client


def test_the_reports_page(refunded: TestClient) -> None:
    html = refunded.get("/reports?month=2026-06").text
    found = page(refunded, "/reports?month=2026-06")
    start = found.rows.index(SPENDING)
    assert found.rows[start : start + 2] == [
        SPENDING,
        ["Groceries", "$0.00", "$5.99", "$5.99 back", "1"],
    ]
    assert ["2026-06", "$5.99 back", "$0.00", "-$43.98", "partly"] in found.rows
    assert "Spent: $0.00. Refunds: $5.99. Net: $5.99 back. Income: $0.00." in texts(
        found, "summary"
    )
    assert html.count(BACK) == 2


def test_the_account_page(refunded: TestClient) -> None:
    path = "/account?name=Test%20Card&month=2026-06"
    found = page(refunded, path)
    start = found.rows.index(GROUPS)
    assert found.rows[start : start + 2] == [GROUPS, ["Food", "$0.00", "$5.99", "$5.99 back", "1"]]
    assert ["2026-06", "$5.99 back", "$0.00"] in found.rows
    assert refunded.get(path).text.count(BACK) == 2


def test_the_budgets_page(refunded: TestClient) -> None:
    found = page(refunded, "/budgets?month=2026-06")
    row = next(row for row in found.rows if row and row[0] == "Groceries")
    assert row[:6] == ["Groceries", "category", "$100.00", "$5.99 back", "$105.99", "0%"]
```

The diff to earlier tests (apply it exactly):

```text
diff --git a/tests/e2e/test_cli_spending.py b/tests/e2e/test_cli_spending.py
index 9d9793b..5091d63 100644
--- a/tests/e2e/test_cli_spending.py
+++ b/tests/e2e/test_cli_spending.py
@@ -115,15 +115,15 @@ def test_a_month_by_category(money: Settings) -> None:
     result = run("spending", *MAY)
     assert result.exit_code == 0
     assert table_rows(result.stdout) == [
-        ["Category", "Spent", "Count"],
-        ["Utilities & Internet", "$120.00", "1"],
-        ["Groceries", "$20.00", "2"],
-        ["Coffee & Dessert", "$17.00", "2"],
-        ["Uncategorized", "$15.00", "1"],
+        ["Category", "Spent", "Refunds", "Net", "Count"],
+        ["Utilities & Internet", "$120.00", "$0.00", "$120.00", "1"],
+        ["Groceries", "$25.99", "$5.99", "$20.00", "2"],
+        ["Coffee & Dessert", "$17.00", "$0.00", "$17.00", "2"],
+        ["Uncategorized", "$15.00", "$0.00", "$15.00", "1"],
     ]
     assert plain_lines(result.stdout) == [
         "Spending from 2026-05-01 to 2026-05-31, by category.",
-        "Spent: $172.00. Income: $3,000.00.",
+        "Spent: $177.99. Refunds: $5.99. Net: $172.00. Income: $3,000.00.",
         "Transfers left out: 2.",
         "Money in without a category: $25.00 (count: 1).",
     ]
@@ -135,52 +135,52 @@ def test_a_month_by_category(money: Settings) -> None:
         (
             "group",
             [
-                ["Group", "Spent", "Count"],
-                ["Home", "$120.00", "1"],
-                ["Food", "$37.00", "4"],
-                ["Uncategorized", "$15.00", "1"],
+                ["Group", "Spent", "Refunds", "Net", "Count"],
+                ["Home", "$120.00", "$0.00", "$120.00", "1"],
+                ["Food", "$42.99", "$5.99", "$37.00", "4"],
+                ["Uncategorized", "$15.00", "$0.00", "$15.00", "1"],
             ],
         ),
         (
             "merchant",
             [
-                ["Merchant", "Spent", "Count"],
-                ["ACME UTILITY", "$120.00", "1"],
-                ["FOOBAR GROCERY", "$20.00", "2"],
-                ["ACME COFFEE", "$17.00", "2"],
-                ["BAZ BOOKS", "$15.00", "1"],
+                ["Merchant", "Spent", "Refunds", "Net", "Count"],
+                ["ACME UTILITY", "$120.00", "$0.00", "$120.00", "1"],
+                ["FOOBAR GROCERY", "$25.99", "$5.99", "$20.00", "2"],
+                ["ACME COFFEE", "$17.00", "$0.00", "$17.00", "2"],
+                ["BAZ BOOKS", "$15.00", "$0.00", "$15.00", "1"],
             ],
         ),
         (
             "person",
             [
-                ["Person", "Spent", "Count"],
-                ["Unassigned", "$120.00", "1"],
-                ["Pat Example", "$52.00", "5"],
+                ["Person", "Spent", "Refunds", "Net", "Count"],
+                ["Unassigned", "$120.00", "$0.00", "$120.00", "1"],
+                ["Pat Example", "$57.99", "$5.99", "$52.00", "5"],
             ],
         ),
         (
             "account",
             [
-                ["Account", "Spent", "Count"],
-                ["Test Checking", "$120.00", "1"],
-                ["Test Card", "$52.00", "5"],
+                ["Account", "Spent", "Refunds", "Net", "Count"],
+                ["Test Checking", "$120.00", "$0.00", "$120.00", "1"],
+                ["Test Card", "$57.99", "$5.99", "$52.00", "5"],
             ],
         ),
         (
             "bank",
             [
-                ["Bank", "Spent", "Count"],
-                ["Test Bank", "$120.00", "1"],
-                ["Example Card Co", "$52.00", "5"],
+                ["Bank", "Spent", "Refunds", "Net", "Count"],
+                ["Test Bank", "$120.00", "$0.00", "$120.00", "1"],
+                ["Example Card Co", "$57.99", "$5.99", "$52.00", "5"],
             ],
         ),
         (
             "card",
             [
-                ["Card", "Spent", "Count"],
-                ["No card", "$147.50", "3"],
-                ["1111", "$24.50", "3"],
+                ["Card", "Spent", "Refunds", "Net", "Count"],
+                ["No card", "$147.50", "$0.00", "$147.50", "3"],
+                ["1111", "$30.49", "$5.99", "$24.50", "3"],
             ],
         ),
     ],
@@ -194,19 +194,19 @@ def test_a_month_by_another_field(money: Settings, by: str, rows: list[list[str]
 def test_the_day_bought_decides_the_month(money: Settings) -> None:
     result = run("spending", "--month", "2026-04")
     assert table_rows(result.stdout) == [
-        ["Category", "Spent", "Count"],
-        ["Uncategorized", "$8.00", "1"],
+        ["Category", "Spent", "Refunds", "Net", "Count"],
+        ["Uncategorized", "$8.00", "$0.00", "$8.00", "1"],
     ]
     assert plain_lines(result.stdout) == [
         "Spending from 2026-04-01 to 2026-04-30, by category.",
-        "Spent: $8.00. Income: $0.00.",
+        "Spent: $8.00. Refunds: $0.00. Net: $8.00. Income: $0.00.",
         "Transfers left out: 0.",
     ]
     result = run("spending", "--month", "2026-06")
     assert result.stdout == (
         "Spending from 2026-06-01 to 2026-06-30, by category.\n"
         "No spending.\n"
-        "Spent: $0.00. Income: $0.00.\n"
+        "Spent: $0.00. Refunds: $0.00. Net: $0.00. Income: $0.00.\n"
         "Transfers left out: 0.\n"
     )
 
@@ -214,13 +214,13 @@ def test_the_day_bought_decides_the_month(money: Settings) -> None:
 def test_a_range_where_refunds_win(money: Settings) -> None:
     result = run("spending", "--from", "2026-05-10", "--to", "2026-05-20")
     assert table_rows(result.stdout) == [
-        ["Category", "Spent", "Count"],
-        ["Uncategorized", "$15.00", "1"],
-        ["Groceries", "-$5.99", "1"],
+        ["Category", "Spent", "Refunds", "Net", "Count"],
+        ["Uncategorized", "$15.00", "$0.00", "$15.00", "1"],
+        ["Groceries", "$0.00", "$5.99", "$5.99 back", "1"],
     ]
     assert plain_lines(result.stdout) == [
         "Spending from 2026-05-10 to 2026-05-20, by category.",
-        "Spent: $9.01. Income: $3,000.00.",
+        "Spent: $15.00. Refunds: $5.99. Net: $9.01. Income: $3,000.00.",
         "Transfers left out: 1.",
         "Money in without a category: $25.00 (count: 1).",
     ]
diff --git a/tests/integration/test_account_and_bulk_repositories.py b/tests/integration/test_account_and_bulk_repositories.py
index 4d5abe6..58862e6 100644
--- a/tests/integration/test_account_and_bulk_repositories.py
+++ b/tests/integration/test_account_and_bulk_repositories.py
@@ -114,5 +114,5 @@ def test_a_closed_account_leaves_balances_and_still_counts_in_spending(
     balances = table_rows(run("balances").stdout)
     assert [row[0] for row in balances[1:]] == ["Test Checking"]
     spending = table_rows(run("spending", "--month", "2026-05", "--by", "account").stdout)
-    assert ["Test Card", "$1.00", "1"] in spending
-    assert ["Test Checking", "$1.00", "1"] in spending
+    assert ["Test Card", "$1.00", "$0.00", "$1.00", "1"] in spending
+    assert ["Test Checking", "$1.00", "$0.00", "$1.00", "1"] in spending
diff --git a/tests/integration/test_web_account_page.py b/tests/integration/test_web_account_page.py
index a37103a..a426bc0 100644
--- a/tests/integration/test_web_account_page.py
+++ b/tests/integration/test_web_account_page.py
@@ -22,7 +22,7 @@ from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts
 
 TODAY = date(2026, 5, 25)
 CARD = "/account?name=Test%20Card"
-SPENDING = ["Group", "Spent", "Count"]
+SPENDING = ["Group", "Spent", "Refunds", "Net", "Count"]
 MONTHS = ["Month", "Spent", "Income"]
 BALANCES = ["Date", "Balance", "From"]
 LATEST = ["Date", "Description", "Category", "Amount", "Card", "Person"]
@@ -126,8 +126,8 @@ def test_the_account_page(home: TestClient) -> None:
     assert texts(found, "cards") == ["Cards: 1111, 2222"]
     assert table(found, SPENDING) == [
         SPENDING,
-        ["Food", "$199.01", "3"],
-        ["Uncategorized", "$50.00", "2"],
+        ["Food", "$205.00", "$5.99", "$199.01", "3"],
+        ["Uncategorized", "$50.00", "$0.00", "$50.00", "2"],
     ]
     months = table(found, MONTHS)
     assert len(months) == 13
@@ -164,8 +164,8 @@ def test_one_card_of_the_account(home: TestClient) -> None:
     assert found.rows[:7] == DETAIL
     assert table(found, SPENDING) == [
         SPENDING,
-        ["Uncategorized", "$15.00", "1"],
-        ["Food", "$5.00", "1"],
+        ["Uncategorized", "$15.00", "$0.00", "$15.00", "1"],
+        ["Food", "$5.00", "$0.00", "$5.00", "1"],
     ]
     assert table(found, MONTHS)[-1] == ["2026-05", "$20.00", "$0.00"]
     assert [row[1] for row in table(found, LATEST)[1:]] == ["ACME COFFEE", "BAZ BOOKS"]
@@ -181,7 +181,7 @@ def test_a_group_line_opens_exactly_its_transactions(home: TestClient) -> None:
 
 def test_another_month(home: TestClient) -> None:
     found = page(home, f"{CARD}&month=2026-04")
-    assert table(found, SPENDING) == [SPENDING, ["Food", "$30.00", "1"]]
+    assert table(found, SPENDING) == [SPENDING, ["Food", "$30.00", "$0.00", "$30.00", "1"]]
     assert found.find("/account")["inputs"]["month"] == ("month", "2026-04")
     assert table(found, MONTHS)[-1] == ["2026-05", "$249.01", "$0.00"]
     found = page(home, f"{CARD}&month=2026-02")
diff --git a/tests/integration/test_web_reports.py b/tests/integration/test_web_reports.py
index fcfc37a..cb0640a 100644
--- a/tests/integration/test_web_reports.py
+++ b/tests/integration/test_web_reports.py
@@ -23,6 +23,7 @@ PORT = 8765
 NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"
 BALANCES = ["Account", "Type", "Balance", "As of", "From"]
 MONTHS = ["Month", "Spent", "Income", "Change", "Covered"]
+SPENDING = ["Spent", "Refunds", "Net", "Count"]
 BY = ["category", "group", "merchant", "person", "account", "bank", "card"]
 
 
@@ -195,7 +196,10 @@ def section(rows: list[list[str]], heading: list[str]) -> list[list[str]]:
     start = rows.index(heading)
     end = start + 1
     while (
-        end < len(rows) and len(rows[end]) == len(heading) and rows[end] not in (BALANCES, MONTHS)
+        end < len(rows)
+        and len(rows[end]) == len(heading)
+        and rows[end] not in (BALANCES, MONTHS)
+        and rows[end][1:] != SPENDING
     ):
         end += 1
     return rows[start:end]
@@ -247,12 +251,15 @@ def test_a_month(home: TestClient) -> None:
         ["2026-04", "$150.00", "$3,000.00", "+$130.00", "yes"],
         ["2026-05", "$15.00", "$0.00", "-$135.00", "partly"],
     ]
-    assert found.rows[-2:] == [["Category", "Spent", "Count"], ["Uncategorized", "$15.00", "1"]]
+    assert found.rows[-2:] == [
+        ["Category", "Spent", "Refunds", "Net", "Count"],
+        ["Uncategorized", "$15.00", "$0.00", "$15.00", "1"],
+    ]
     assert texts(found, "summary") == [
         "Cash: $13,100.00. Cards: -$612.34. Other: $0.00.",
         "Net worth: $12,487.66.",
         "Spending from 2026-05-01 to 2026-05-31, by category.",
-        "Spent: $15.00. Income: $0.00.",
+        "Spent: $15.00. Refunds: $0.00. Net: $15.00. Income: $0.00.",
         "Transfers left out: 0.",
     ]
     assert texts(found, "hint") == [
@@ -285,13 +292,13 @@ def test_the_form_keeps_what_was_asked(home: TestClient) -> None:
 def test_a_range_by_merchant_and_months_ending_with_it(home: TestClient) -> None:
     found = page(home, "/reports?from=2026-04-01&to=2026-04-30&by=merchant")
     assert found.rows[-3:] == [
-        ["Merchant", "Spent", "Count"],
-        ["ACME UTILITY", "$120.00", "1"],
-        ["FOOBAR GROCERY", "$30.00", "1"],
+        ["Merchant", "Spent", "Refunds", "Net", "Count"],
+        ["ACME UTILITY", "$120.00", "$0.00", "$120.00", "1"],
+        ["FOOBAR GROCERY", "$30.00", "$0.00", "$30.00", "1"],
     ]
     assert texts(found, "summary")[2:] == [
         "Spending from 2026-04-01 to 2026-04-30, by merchant.",
-        "Spent: $150.00. Income: $3,000.00.",
+        "Spent: $150.00. Refunds: $0.00. Net: $150.00. Income: $3,000.00.",
         "Transfers left out: 0.",
     ]
     assert [row[0] for row in section(found.rows, MONTHS)] == [
@@ -315,7 +322,7 @@ def test_a_month_without_spending(home: TestClient) -> None:
     assert ("empty", "No spending.") in found.paragraphs
     assert texts(found, "summary")[2:] == [
         "Spending from 2026-06-01 to 2026-06-30, by category.",
-        "Spent: $0.00. Income: $0.00.",
+        "Spent: $0.00. Refunds: $0.00. Net: $0.00. Income: $0.00.",
         "Transfers left out: 0.",
     ]
 
diff --git a/tests/integration/test_web_search.py b/tests/integration/test_web_search.py
index ed24918..f9f3e7a 100644
--- a/tests/integration/test_web_search.py
+++ b/tests/integration/test_web_search.py
@@ -236,10 +236,12 @@ def test_a_spending_line_opens_its_transactions(home: TestClient) -> None:
 )
 def test_every_line_opens_exactly_its_transactions(home: TestClient, by: str) -> None:
     found = page(home, f"/reports?month=2026-05&by={by}")
-    spending = found.rows[found.rows.index([by.capitalize(), "Spent", "Count"]) + 1 :]
+    spending = found.rows[
+        found.rows.index([by.capitalize(), "Spent", "Refunds", "Net", "Count"]) + 1 :
+    ]
     assert len(links(found)) == len(spending) > 0
     for link, row in zip(links(found), spending, strict=True):
-        assert len(page(home, link).rows) - 1 == int(row[2]), (link, row)
+        assert len(page(home, link).rows) - 1 == int(row[4]), (link, row)
 
 
 def test_insights_open_their_transactions(home: TestClient) -> None:
diff --git a/tests/unit/test_spending.py b/tests/unit/test_spending.py
index 96e83e5..48f5b7a 100644
--- a/tests/unit/test_spending.py
+++ b/tests/unit/test_spending.py
@@ -85,7 +85,7 @@ def test_refunds_net_and_the_largest_comes_first() -> None:
     ]
     assert spending_lines(flows, "category") == [
         SpendingLine("Utilities & Internet", 12000, 1),
-        SpendingLine("Groceries", 2000, 2),
+        SpendingLine("Groceries", 2000, 2, refunds_cents=599),
         SpendingLine("Coffee & Dessert", 1700, 2),
     ]
 
@@ -100,7 +100,7 @@ def test_a_tie_goes_by_name_ignoring_case_and_a_refund_can_win() -> None:
     assert spending_lines(flows, "merchant") == [
         SpendingLine("Alpha", 500, 1),
         SpendingLine("beta", 500, 1),
-        SpendingLine("QUUX", -500, 2),
+        SpendingLine("QUUX", -500, 2, refunds_cents=700),
     ]
 
 
@@ -132,6 +132,7 @@ def test_summarize() -> None:
         transfers=2,
         unsorted_in_cents=2500,
         unsorted_in_count=1,
+        refunds_cents=599,
     )
     assert summarize([]) == SpendingSummary(0, 0, 0, 0, 0)
 
```

## Tests to write

`tests/integration/test_refunds_more.py`: `fin spending --by merchant` and `--by card` in a month with a refund (Spent, Refunds, Net per line); the dashboard's months table in a month that is money back; a budget group whose categories net to money back; a month with purchases and a refund larger than them in one category but net spending overall (the line says `back`, the summary does not).

## Rules for this phase

- `domain/spending.py` imports nothing new from the project; money stays integer cents.
- No total changes: `spent_cents` keeps its meaning everywhere it is read (budgets, insights, the pie chart, months).
- Earlier tests change only by the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_net_text.py tests/e2e/test_cli_refunds.py tests/integration/test_web_refunds.py`, 14 tests; at least N + 14 passed in all;
- `git diff --stat HEAD -- tests` lists only the six files of the given diff;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.spending --cov=finances.views.spending --cov=finances.views.format --cov=finances.views.months --cov=finances.views.budgets --cov=finances.views.account_page --cov=finances.cli.reports --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 35a: Spent, Refunds, and Net (YYYY-MM-DD)`.
