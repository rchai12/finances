# Phase 27c: looking ahead on the web

## Goal

What 27a and 27b print in the terminal can be seen in the browser. After this phase:

- a read-only page `/ahead` ("Ahead" in the menu) shows 27b's forecast for every account and 27a's expected bills and income for the next N days, and one account day by day when a forecast row's name is pressed;
- the dashboard gains a "Coming up" block with the next 7 days' bills and income.

Nothing new is computed: the page and the block show `forecast_report` and `upcoming_report` as they are. Net worth over time as a chart is Phase 27d.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-27a-upcoming-bills-and-income.md`, `docs/phases/phase-27b-forecast-per-account.md`
- `src/finances/web/routes/reports.py` (the Insights page: a GET form, an error page), `src/finances/web/routes/home.py`, `src/finances/web/routes/accounts.py` (`_missing_account`), `src/finances/web/render.py`, `src/finances/analysis/dashboard.py`
- `src/finances/views/forecast.py`, `src/finances/views/upcoming.py`

## Starting state

N is `2976` when Phase 27b is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/analysis/dashboard.py` | `Dashboard.upcoming` (R1) |
| `src/finances/web/routes/home.py` | the block's context (R2) |
| `src/finances/web/routes/reports.py` | `GET /ahead` (R3 to R7) |
| `src/finances/web/templates/ahead.html` | new: given |
| `src/finances/web/templates/dashboard.html`, `src/finances/web/templates/layout.html` | given diff |
| `tests/unit/test_web_split.py` | given diff (one route added to the list) |
| `tests/integration/test_web_ahead.py` | new: given |
| `tests/integration/test_web_ahead_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

No new router module: `/ahead` goes in `routes/reports.py`, so the list of areas that `tests/unit/test_web_split.py` pins stays the same.

## Out of scope

- Net worth over time and any chart (27d); a forecast block on the dashboard.
- A form to choose the account (the forecast rows link to it); an `--as-of` on the web (the page uses today); any change to 27a's or 27b's functions or views.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/analysis/dashboard.py
@dataclass(frozen=True)
class Dashboard:
    today: date
    balance: BalanceReport
    months: list[MonthLine]
    insights: InsightsReport
    problems: list[Problem]
    uncategorized: int
    transfers_waiting: int
    upcoming: UpcomingReport               # new, before budgets
    budgets: tuple[BudgetLine, ...] = ()

# src/finances/web/routes/reports.py
DAYS_REFUSED = "days must be a whole number from 1 to 90"

@router.get("/ahead")
def ahead(request: Request) -> Response: ...
```

The context `ahead.html` reads (beside the shared values `_render` adds):

| Name | Value |
|---|---|
| `days` | the number of days, as text (`"30"`) |
| `forecast` | without an account: `{"heading": forecast_heading(report), "rows": forecast_rows(report), "no_balance": no_balance_line(report)}`; with one: not given |
| `upcoming` | without an account: `{"heading": upcoming_heading(found), "rows": upcoming_rows(found), "summary": upcoming_summary(found)}`; with one: not given |
| `detail` | with an account: `{"account": forecast.account, "heading": account_heading(report), "starting": starting_line(forecast), "steps": step_rows(forecast), "lowest": lowest_line(forecast)}` where `forecast` is `report.accounts[0]`; without one: `None` |

`dashboard.html` reads `upcoming` (`upcoming_rows(found.upcoming)`) and `upcoming_summary` (`upcoming_summary(found.upcoming)`).

## Requirements

### Part 1: the dashboard

- **R1.** `dashboard` fills `upcoming` with `upcoming_report(session, today, 7)` (today counted as the first of 7 days).
- **R2.** The home route adds `upcoming` and `upcoming_summary` to its context. The given `dashboard.html` shows the block after Budgets; its two paragraphs have the class `ahead`, so the tables and paragraph classes earlier tests read do not change (with nothing expected there is no table).

### Part 2: the page

- **R3.** `GET /ahead` stops with the not-migrated page as the other pages do (`_not_migrated`). It reads today through `web_app._today()` when the request is handled, never at import, and opens one reading session (`_reading()`).
- **R4.** The query's `days` is empty or missing for 30; otherwise it must be written only with the digits 0 to 9 and be from 1 to 90 (`"07"` is 7). Anything else (`"0"`, `"91"`, `"ten"`, `"1.5"`, `"-3"`) renders `error.html` with status 400, the message `DAYS_REFUSED`, and `back` `/ahead`. `days` is checked before `account`.
- **R5.** With no `account` (missing, or only spaces), the page shows `forecast_report(session, today, days)` and `upcoming_report(session, today, days)` in the context above, status 200.
- **R6.** With an `account`, it shows `forecast_report(session, today, days, account=...)` as `detail`. A `ValueError` from it renders `error.html` with status 404, its message, and `back` `/ahead`.
- **R7.** The given `layout.html` adds "Ahead" to the menu (current on this page: `_render`'s section is `ahead`). Each forecast row links to `/ahead?account=NAME&days=N` (the name URL-encoded); the detail links back to `/ahead?days=N`; the days form keeps the account in a hidden field.

## Given tests

14 new tests in one file, and a one-line change to an earlier test. The fixture is 27b's (balances dated 2026-05-24, today 2026-05-25); `_today` is replaced **after** the app is created, so a page that reads the date when its module is imported fails.

`tests/integration/test_web_ahead.py`

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

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
)
from finances.domain.models import DataSource
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts

TODAY = date(2026, 5, 25)
FORECAST = [
    "Account",
    "Balance",
    "As of",
    "Expected in",
    "Expected out",
    "End",
    "Lowest",
    "Lowest on",
]
CARD = [
    "Test Card",
    "-$450.00",
    "2026-05-24",
    "$500.00",
    "-$63.99",
    "-$13.99",
    "-$462.00",
    "2026-05-29",
]
CHECKING = [
    "Test Checking",
    "$300.00",
    "2026-05-24",
    "$6,000.00",
    "-$620.00",
    "$5,680.00",
    "$180.00",
    "2026-05-27",
]
SAVINGS = [
    "Test Savings",
    "$1,000.00",
    "2026-05-24",
    "$1.00",
    "$0.00",
    "$1,001.00",
    "$1,000.00",
    "2026-05-25",
]
EXPECTED = ["Date", "What", "Merchant", "Every", "Amount"]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return found


@pytest.fixture
def money(client: TestClient) -> TestClient:
    """Checking: a utility on the 27th, pay every two weeks, a card payment on the 2nd.
    Card: streaming, a weekly box, the payment arriving on the 3rd. Savings: monthly interest.
    Brokerage: no balance."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        create_account(session, "Test Brokerage", "Test Bank", "other")
        set_balance_snapshot(session, checking.id, date(2026, 5, 24), 30000, DataSource.AGGREGATOR)
        set_balance_snapshot(session, card.id, date(2026, 5, 24), -45000, DataSource.AGGREGATOR)
        add_balance_snapshot(session, savings.id, date(2026, 5, 24), 100000, DataSource.STATEMENT)
        rows = [
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
        pair_transfers(session)
        create_rule(session, "PAYCHECK", "Paycheck")
        create_rule(session, "INTEREST PAID", "Interest Income")
        categorize(session)
    engine.dispose()
    return client


def test_not_migrated(client: TestClient) -> None:
    response = client.get("/ahead")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_every_account_and_what_is_expected(money: TestClient) -> None:
    response = money.get("/ahead")
    assert response.status_code == 200
    assert 'href="/ahead" aria-current="page">Ahead</a>' in response.text
    found = Page(response.text)
    assert found.rows == [
        FORECAST,
        CARD,
        CHECKING,
        SAVINGS,
        EXPECTED,
        ["2026-05-27", "bill", "ACME UTILITY", "month", "-$120.00"],
        ["2026-05-29", "income", "PAYCHECK EXAMPLE CORP", "two_weeks", "$3,000.00"],
        ["2026-05-29", "bill", "BAZ BOX", "week", "-$12.00"],
        ["2026-05-30", "income", "INTEREST PAID", "month", "$1.00"],
        ["2026-06-05", "bill", "BAZ BOX", "week", "-$12.00"],
        ["2026-06-05", "bill", "QUUX STREAMING", "month", "-$15.99"],
        ["2026-06-12", "income", "PAYCHECK EXAMPLE CORP", "two_weeks", "$3,000.00"],
        ["2026-06-12", "bill", "BAZ BOX", "week", "-$12.00"],
        ["2026-06-19", "bill", "BAZ BOX", "week", "-$12.00"],
    ]
    assert texts(found, "summary") == [
        "Forecast from 2026-05-25 to 2026-06-23.",
        "Expected from 2026-05-25 to 2026-06-23.",
        "Bills: -$183.99. Income: $6,001.00.",
    ]
    assert texts(found, "hint") == ["No balance yet: Test Brokerage."]
    assert "/ahead?account=Test%20Checking&days=30" in found.links
    assert found.forms[0]["inputs"] == {"days": ("number", "30")}


def test_one_account_day_by_day(money: TestClient) -> None:
    found = page(money, "/ahead?account=test+checking&days=30")
    assert found.rows == [
        ["Date", "Merchant", "Amount", "Balance"],
        ["2026-05-27", "ACME UTILITY", "-$120.00", "$180.00"],
        ["2026-05-29", "PAYCHECK EXAMPLE CORP", "$3,000.00", "$3,180.00"],
        ["2026-06-02", "PAYMENT TO TEST CARD", "-$500.00", "$2,680.00"],
        ["2026-06-12", "PAYCHECK EXAMPLE CORP", "$3,000.00", "$5,680.00"],
    ]
    assert texts(found, "summary") == [
        "Forecast for Test Checking from 2026-05-25 to 2026-06-23.",
        "Starting balance: $300.00 (as of 2026-05-24).",
        "Lowest: $180.00 on 2026-05-27.",
    ]
    assert "/ahead?days=30" in found.links
    assert found.forms[0]["inputs"] == {
        "days": ("number", "30"),
        "account": ("hidden", "Test Checking"),
    }


def test_a_shorter_window(money: TestClient) -> None:
    found = page(money, "/ahead?days=7")
    assert found.rows[2] == [
        "Test Checking",
        "$300.00",
        "2026-05-24",
        "$3,000.00",
        "-$120.00",
        "$3,180.00",
        "$180.00",
        "2026-05-27",
    ]
    assert texts(found, "summary")[-1] == "Bills: -$132.00. Income: $3,001.00."
    assert "/ahead?account=Test%20Card&days=7" in found.links


def test_nothing_yet(client: TestClient) -> None:
    upgrade_to_head()
    found = page(client, "/ahead")
    assert found.rows == []
    assert texts(found, "empty") == ["No accounts with a balance.", "Nothing expected."]
    assert texts(found, "hint") == []


@pytest.mark.parametrize("days", ["0", "91", "ten", "1.5", "-3"])
def test_refused_days(money: TestClient, days: str) -> None:
    response = money.get(f"/ahead?days={days}")
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == ["days must be a whole number from 1 to 90"]
    assert "/ahead" in found.links


@pytest.mark.parametrize(
    ("account", "message"),
    [("Nope", "account not found"), ("Test+Brokerage", "Test Brokerage has no balance yet")],
)
def test_refused_account(money: TestClient, account: str, message: str) -> None:
    response = money.get(f"/ahead?account={account}")
    assert response.status_code == 404
    assert texts(Page(response.text), "error") == [message]


def test_coming_up_on_the_dashboard(money: TestClient) -> None:
    found = page(money, "/")
    start = found.rows.index(["Date", "What", "Merchant", "Amount"])
    assert found.rows[start:] == [
        ["Date", "What", "Merchant", "Amount"],
        ["2026-05-27", "bill", "ACME UTILITY", "-$120.00"],
        ["2026-05-29", "income", "PAYCHECK EXAMPLE CORP", "$3,000.00"],
        ["2026-05-29", "bill", "BAZ BOX", "-$12.00"],
        ["2026-05-30", "income", "INTEREST PAID", "$1.00"],
    ]
    assert texts(found, "ahead") == ["Bills: -$132.00. Income: $3,001.00."]
    assert "/ahead" in found.links


def test_nothing_coming_up_on_the_dashboard(client: TestClient) -> None:
    upgrade_to_head()
    assert texts(page(client, "/"), "ahead") == [
        "Nothing expected in the next 7 days.",
        "Bills: $0.00. Income: $0.00.",
    ]
```

## Given templates and diffs

`src/finances/web/templates/ahead.html` (new; do not change)

```html
{% extends "layout.html" %}
{% block title %}Looking ahead · Finances{% endblock %}
{% block content %}
<h1>Looking ahead</h1>
<form method="get" action="/ahead" class="fields">
  <label>Days <input type="number" name="days" min="1" max="90" value="{{ days }}"></label>
  {% if detail %}<input type="hidden" name="account" value="{{ detail.account }}">{% endif %}
  <button type="submit">Show</button>
</form>
{% if detail %}
<h2>{{ detail.account }}</h2>
<p class="summary">{{ detail.heading }}</p>
<p class="summary">{{ detail.starting }}</p>
{% if detail.steps %}
<table>
<thead><tr><th>Date</th><th>Merchant</th><th class="amount">Amount</th><th class="amount">Balance</th></tr></thead>
<tbody>
{% for row in detail.steps %}<tr><td>{{ row.date }}</td><td>{{ row.merchant }}</td><td class="amount">{{ row.amount }}</td><td class="amount">{{ row.balance }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">Nothing expected.</p>
{% endif %}
<p class="summary">{{ detail.lowest }}</p>
<p><a href="/ahead?days={{ days }}">All accounts</a></p>
{% else %}
<h2>Forecast</h2>
<p class="summary">{{ forecast.heading }}</p>
{% if forecast.rows %}
<table>
<thead><tr><th>Account</th><th class="amount">Balance</th><th>As of</th><th class="amount">Expected in</th><th class="amount">Expected out</th><th class="amount">End</th><th class="amount">Lowest</th><th>Lowest on</th></tr></thead>
<tbody>
{% for row in forecast.rows %}<tr><td><a href="/ahead?account={{ row.account|urlencode }}&amp;days={{ days }}">{{ row.account }}</a></td><td class="amount">{{ row.balance }}</td><td>{{ row.as_of }}</td><td class="amount">{{ row.expected_in }}</td><td class="amount">{{ row.expected_out }}</td><td class="amount">{{ row.end }}</td><td class="amount">{{ row.lowest }}</td><td>{{ row.lowest_on }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No accounts with a balance.</p>
{% endif %}
{% if forecast.no_balance %}<p class="hint">{{ forecast.no_balance }}</p>{% endif %}
<h2>Expected</h2>
<p class="summary">{{ upcoming.heading }}</p>
{% if upcoming.rows %}
<table>
<thead><tr><th>Date</th><th>What</th><th>Merchant</th><th>Every</th><th class="amount">Amount</th></tr></thead>
<tbody>
{% for row in upcoming.rows %}<tr><td>{{ row.date }}</td><td>{{ row.what }}</td><td>{{ row.merchant }}</td><td>{{ row.every }}</td><td class="amount">{{ row.amount }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">Nothing expected.</p>
{% endif %}
<p class="summary">{{ upcoming.summary }}</p>
{% endif %}
{% endblock %}
```

Apply this diff exactly (`dashboard.html`, `layout.html`, and the route list in `tests/unit/test_web_split.py`):

```text
diff --git a/src/finances/web/templates/dashboard.html b/src/finances/web/templates/dashboard.html
index 062ad39..39b2051 100644
--- a/src/finances/web/templates/dashboard.html
+++ b/src/finances/web/templates/dashboard.html
@@ -47,6 +47,19 @@
 <p class="hint">No budgets yet.</p>
 {% endif %}
 <p><a href="/budgets">Budgets</a></p>
+<h2>Coming up</h2>
+{% if upcoming %}
+<table>
+<thead><tr><th>Date</th><th>What</th><th>Merchant</th><th class="amount">Amount</th></tr></thead>
+<tbody>
+{% for row in upcoming %}<tr><td>{{ row.date }}</td><td>{{ row.what }}</td><td>{{ row.merchant }}</td><td class="amount">{{ row.amount }}</td></tr>
+{% endfor %}</tbody>
+</table>
+{% else %}
+<p class="ahead">Nothing expected in the next 7 days.</p>
+{% endif %}
+<p class="ahead">{{ upcoming_summary }}</p>
+<p><a href="/ahead">Looking ahead</a></p>
 <h2>Top findings</h2>
 {% if findings %}
 <table>
diff --git a/src/finances/web/templates/layout.html b/src/finances/web/templates/layout.html
index ae4288a..156c87b 100644
--- a/src/finances/web/templates/layout.html
+++ b/src/finances/web/templates/layout.html
@@ -20,6 +20,7 @@
   <a href="/reports"{% if section == "reports" %} aria-current="page"{% endif %}>Reports</a>
   <a href="/insights"{% if section == "insights" %} aria-current="page"{% endif %}>Insights</a>
   <a href="/budgets"{% if section == "budgets" %} aria-current="page"{% endif %}>Budgets</a>
+  <a href="/ahead"{% if section == "ahead" %} aria-current="page"{% endif %}>Ahead</a>
   <a href="/sync"{% if section == "sync" %} aria-current="page"{% endif %}>SimpleFIN</a>
   <a href="/backups"{% if section == "backups" %} aria-current="page"{% endif %}>Backups</a>
 </nav>
diff --git a/tests/unit/test_web_split.py b/tests/unit/test_web_split.py
index 2c63a87..60eee13 100644
--- a/tests/unit/test_web_split.py
+++ b/tests/unit/test_web_split.py
@@ -55,6 +55,7 @@ ROUTES = {
     ("POST", "/categories/rules/{rule_id}"),
     ("GET", "/reports"),
     ("GET", "/insights"),
+    ("GET", "/ahead"),
     ("GET", "/transfers"),
     ("POST", "/transfers/find"),
     ("POST", "/transfers/confirm"),
```

## Tests to write

`tests/integration/test_web_ahead_more.py`: `days=07` is 7; `days=0&account=Nope` gives the days message (R4's order); `account=` with only spaces shows every account; one account with a balance and nothing expected ("Nothing expected."); an inactive account found through its link; the dashboard's 7 days end on today + 6 (an item on day 7 shows, one on day 8 does not); a GET on `/ahead` with an unknown query field is ignored.

## Rules for this phase

- The routes hold no rule: they read the query, call 27a's and 27b's functions, and pass their views to the template. No sums, sorting, or date arithmetic in `routes/`.
- `routes/reports.py` stays under 400 lines (Phase 32's test).
- Every earlier test passes unchanged, apart from the given line in `tests/unit/test_web_split.py`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/integration/test_web_ahead.py tests/unit/test_web_split.py`, 30 tests;
- also `.venv/bin/python -m pytest tests/integration/test_web_dashboard.py tests/integration/test_dashboard_more.py tests/integration/test_web_budgets.py tests/integration/test_web_budgets_more.py tests/integration/test_one_today.py --no-cov`: all pass;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.analysis.dashboard --cov=finances.web.routes.reports --cov=finances.web.routes.home --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the search: `git grep -n --untracked -E "sum\(|sorted\(|timedelta|select\(|session\.(add|execute|delete)" -- src/finances/web/routes/reports.py src/finances/web/routes/home.py`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 27c: looking ahead on the web (YYYY-MM-DD)`.
