# Phase 16k: charts

## Goal

The account page draws its numbers. After this phase, beside its tables, an account's page shows a **pie** of the month's spending by group, **bars** of spent and income for the last 12 months, and a **line** of the balance over time. Every table stays, so the page still reads without scripts.

This is the site's first JavaScript (the owner's choice, 2026-10-15), so it comes with these rules:

- the chart library is **Chart.js 4.4.6** (MIT), the file `dist/chart.umd.js` of its npm package, kept in `static/vendor/`; a test pins its SHA-256;
- the security policy changes from `script-src 'none'` to `script-src 'self'`: only files the site serves itself run; no inline script, no `eval`, no CDN;
- the site's own script, `static/charts.js` (given), reads each chart's data from a `data-chart` attribute holding JSON, and draws it; money stays in **integer cents** until the script shows it;
- only the account page loads scripts.

A spike (2026-10-16) drew all three charts with this library under this policy in headless Chrome with no policy refusal.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-16i-account-pages.md`; `src/finances/analysis/account_page.py`, `src/finances/views/account_page.py`
- `src/finances/web/app.py`: `SECURITY_HEADERS`, `GET /account`

## Before you start (the owner)

The library comes from the npm registry, once, by the owner, and is committed with the phase. From the repository root:

```
curl -fL -o chart.js-4.4.6.tgz https://registry.npmjs.org/chart.js/-/chart.js-4.4.6.tgz
mkdir -p src/finances/web/static/vendor
tar -xzf chart.js-4.4.6.tgz -O package/dist/chart.umd.js > src/finances/web/static/vendor/chart.umd.js
rm chart.js-4.4.6.tgz
shasum -a 256 src/finances/web/static/vendor/chart.umd.js
```

The last line must print `3850656abbdc319141e6e8ce8eacde2622fc767c30e20d81704af2bf3159f92d`. If it does not, stop. The coder does not download anything.

## Starting state

N is `2813` when Phase 16i is the last phase built, and `src/finances/web/static/vendor/chart.umd.js` is in place (above).

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/app.py` | the policy (R1); the account page's chart data (R3) |
| `src/finances/views/charts.py` | new (R2) |
| `src/finances/web/templates/layout.html`, `account.html` | replaced: given |
| `src/finances/web/static/charts.js` | new: given |
| `src/finances/web/static/app.css` | one line added: `.chart { max-width: 32rem; margin: 0.5rem 0 1rem; }` |
| `src/finances/web/static/vendor/chart.umd.js` | added by the owner (above) |
| `tests/unit/test_chart_library.py`, `tests/integration/test_web_charts.py` | new: given |
| `tests/unit/test_web_security.py` | the policy line: given change (below) |
| `tests/unit/test_chart_views.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Charts on other pages (Reports, Insights, the dashboard); interactive filters; any other script or library.
- Loading anything from another site; a source map; changing the library file in any way.

## Dependencies

No Python dependency. One vendored file: Chart.js 4.4.6, added by the owner as above.

## Design

```python
# src/finances/views/charts.py
def pie_chart(lines: list[SpendingLine]) -> dict | None: ...
def months_chart(months: list[AccountMonth]) -> dict: ...
def balance_chart(balances: list[BalanceSnapshot]) -> dict | None: ...
```

Each returns the chart's data in one shape, which `charts.js` reads:

```json
{"kind": "pie" | "bar" | "line", "labels": ["..."], "series": [{"name": "...", "cents": [0]}]}
```

## Requirements

- **R1.** `SECURITY_HEADERS["content-security-policy"]` becomes `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`. Nothing else in the headers changes.
- **R2.** `pie_chart` keeps the lines whose spent amount is above zero (a pie cannot show a negative slice), in their order: kind `pie`, labels their names, one series `Spent` with their cents; `None` when none is left. `months_chart`: kind `bar`, labels the months as `YYYY-MM`, series `Spent` then `Income` with each month's cents. `balance_chart`: kind `line`, labels the snapshots' dates (ISO), oldest first, one series `Balance` with their cents; `None` when there are none.
- **R3.** `GET /account` passes `pie_chart` (only when spending is shown), `months_chart`, and `balance_chart` to the template as JSON text (`json.dumps`), or `None`. The template escapes it into the attribute.
- **R4.** The given templates, `charts.js`, and the CSS line are used as shown: the account page loads exactly the two scripts, both `defer`, from the site's own `/static/`; every other page loads none (the layout's `scripts` block is empty there).
- **R5.** `docs/architecture.md` already records the rule (the architect changed it with this spec): no change by the coder.

## Given files

`src/finances/web/templates/layout.html`

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}Finances{% endblock %}</title>
<link rel="stylesheet" href="/static/app.css">
{% block scripts %}{% endblock %}
</head>
<body>
<nav>
  <span class="brand">Finances</span>
  <a href="/"{% if section == "dashboard" %} aria-current="page"{% endif %}>Home</a>
  <a href="/accounts"{% if section == "accounts" %} aria-current="page"{% endif %}>Accounts</a>
  <a href="/people"{% if section == "people" %} aria-current="page"{% endif %}>People</a>
  <a href="/transactions"{% if section == "transactions" %} aria-current="page"{% endif %}>Transactions</a>
  <a href="/statements"{% if section == "statements" %} aria-current="page"{% endif %}>Statements</a>
  <a href="/categories"{% if section == "categories" %} aria-current="page"{% endif %}>Categories</a>
  <a href="/transfers"{% if section == "transfers" %} aria-current="page"{% endif %}>Transfers</a>
  <a href="/reports"{% if section == "reports" %} aria-current="page"{% endif %}>Reports</a>
  <a href="/insights"{% if section == "insights" %} aria-current="page"{% endif %}>Insights</a>
  <a href="/sync"{% if section == "sync" %} aria-current="page"{% endif %}>SimpleFIN</a>
  <a href="/backups"{% if section == "backups" %} aria-current="page"{% endif %}>Backups</a>
</nav>
<main>
{% block content %}{% endblock %}
</main>
</body>
</html>
```

`src/finances/web/templates/account.html`

```html
{% extends "layout.html" %}
{% block title %}{{ name }} · Finances{% endblock %}
{% block scripts %}<script src="/static/vendor/chart.umd.js" defer></script>
<script src="/static/charts.js" defer></script>
{% endblock %}
{% block content %}
<h1>{{ name }}{% if card %} · card ending {{ card }}{% endif %}</h1>
{% include "messages.html" %}
<p><a href="/accounts">All accounts</a>{% if card %} · <a href="/account?name={{ name|urlencode }}">All cards of this account</a>{% endif %}</p>
<table class="detail">
<tbody>
{% for label, value in detail %}<tr><th>{{ label }}</th><td>{{ value }}</td></tr>
{% endfor %}</tbody>
</table>
{% if cards %}<p class="cards">Cards: {% for digits in cards %}<a href="/account?name={{ name|urlencode }}&amp;card={{ digits }}">{{ digits }}</a>{% if not loop.last %}, {% endif %}{% endfor %}</p>{% endif %}
<h2>Spending in {{ month_label }}</h2>
<form method="get" action="/account" class="fields">
  <input type="hidden" name="name" value="{{ name }}">
  {% if card %}<input type="hidden" name="card" value="{{ card }}">{% endif %}
  <label>Month <input type="month" name="month" value="{{ month_text }}"></label>
  <button type="submit">Show</button>
</form>
{% if spending %}
{% if pie_chart %}<div class="chart"><canvas data-chart="{{ pie_chart }}" role="img" aria-label="Spending by group in {{ month_label }}"></canvas></div>{% endif %}
<table>
<thead><tr><th>Group</th><th class="amount">Spent</th><th class="amount">Count</th></tr></thead>
<tbody>
{% for row in spending %}<tr><td><a href="/transactions?account={{ name|urlencode }}{% if card %}&amp;card={{ card }}{% endif %}&amp;from={{ start }}&amp;to={{ end }}&amp;group={{ row.label|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.label }}</a></td><td class="amount">{{ row.spent }}</td><td class="amount">{{ row.count }}</td></tr>
{% endfor %}</tbody>
</table>
{% elif not error %}
<p class="empty">No spending in {{ month_label }}.</p>
{% endif %}
<h2>Months</h2>
<div class="chart"><canvas data-chart="{{ months_chart }}" role="img" aria-label="Spent and income by month"></canvas></div>
<table>
<thead><tr><th>Month</th><th class="amount">Spent</th><th class="amount">Income</th></tr></thead>
<tbody>
{% for row in months %}<tr><td><a href="/account?name={{ name|urlencode }}{% if card %}&amp;card={{ card }}{% endif %}&amp;month={{ row.month }}">{{ row.month }}</a></td><td class="amount">{{ row.spent }}</td><td class="amount">{{ row.income }}</td></tr>
{% endfor %}</tbody>
</table>
<h2>Balance history</h2>
{% if balances %}
<div class="chart"><canvas data-chart="{{ balance_chart }}" role="img" aria-label="Balance over time"></canvas></div>
<table>
<thead><tr><th>Date</th><th class="amount">Balance</th><th>From</th></tr></thead>
<tbody>
{% for row in balances %}<tr><td>{{ row.date }}</td><td class="amount">{{ row.balance }}</td><td>{{ row.source }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No balances yet.</p>
{% endif %}
<h2>Latest transactions</h2>
<p><a href="/transactions?account={{ name|urlencode }}{% if card %}&amp;card={{ card }}{% endif %}">Search and filter this account's transactions</a></p>
{% if transactions %}
<table>
<thead><tr><th>Date</th><th>Description</th><th>Category</th><th class="amount">Amount</th><th>Card</th><th>Person</th></tr></thead>
<tbody>
{% for id, row, category in transactions %}<tr><td><a href="/transactions/{{ id }}">{{ row.date }}</a></td><td>{{ row.description }}</td><td>{{ category }}</td><td class="amount">{{ row.amount }}</td><td>{{ row.card }}</td><td>{{ row.person }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No transactions.</p>
{% endif %}
{% endblock %}
```

`src/finances/web/static/charts.js`

```text
// Draws each <canvas data-chart="..."> with Chart.js (static/vendor/chart.umd.js).
// The page sends plain data: {"kind": "pie" | "bar" | "line", "labels": [...],
// "series": [{"name": ..., "cents": [...]}]}. Money stays in whole cents until it is shown.
(function () {
  "use strict";
  var dollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
  var colors = ["#2f6f9f", "#c0612b", "#4b8b3b", "#8a5aa8", "#b8963a", "#3a8f8a", "#a8485a", "#6b6b6b"];

  function money(cents) {
    return dollars.format(cents / 100);
  }

  function config(chart) {
    var pie = chart.kind === "pie";
    var datasets = chart.series.map(function (series, index) {
      return {
        label: series.name,
        data: series.cents.map(function (cents) { return cents / 100; }),
        backgroundColor: pie ? colors : colors[index % colors.length],
        borderColor: pie ? "#ffffff" : colors[index % colors.length],
      };
    });
    var options = {
      animation: false,
      plugins: {
        tooltip: {
          callbacks: {
            label: function (item) {
              var name = pie ? item.label : item.dataset.label;
              return name + ": " + money(Math.round(item.raw * 100));
            },
          },
        },
      },
    };
    if (!pie) {
      options.scales = { y: { ticks: { callback: function (value) { return money(Math.round(value * 100)); } } } };
    }
    return { type: chart.kind, data: { labels: chart.labels, datasets: datasets }, options: options };
  }

  document.querySelectorAll("canvas[data-chart]").forEach(function (canvas) {
    try {
      new Chart(canvas, config(JSON.parse(canvas.dataset.chart)));
      canvas.dataset.drawn = "yes";
    } catch (error) {
      canvas.dataset.drawn = "error";
    }
  });
})();
```

## Given tests

13 tests in two files. Five of them (`test_other_pages_load_no_script`) already pass and must keep passing; the rest fail until the phase is built.

`tests/unit/test_chart_library.py`

```python
import hashlib
from pathlib import Path

import finances.web

STATIC = Path(finances.web.__file__).parent / "static"
LIBRARY = STATIC / "vendor" / "chart.umd.js"
# dist/chart.umd.js from the npm package chart.js 4.4.6 (the same bytes jsDelivr serves).
SHA256 = "3850656abbdc319141e6e8ce8eacde2622fc767c30e20d81704af2bf3159f92d"


def test_the_chart_library_is_the_pinned_file() -> None:
    content = LIBRARY.read_bytes()
    assert hashlib.sha256(content).hexdigest() == SHA256
    assert content.startswith(b"/*!\n * Chart.js v4.4.6\n")


def test_the_vendor_folder_holds_only_the_library() -> None:
    assert sorted(path.name for path in LIBRARY.parent.iterdir()) == ["chart.umd.js"]


def test_our_chart_script_sends_nothing_anywhere() -> None:
    script = (STATIC / "charts.js").read_text(encoding="utf-8")
    for word in (
        "fetch",
        "XMLHttpRequest",
        "http",
        "eval",
        "Function(",
        "innerHTML",
        "localStorage",
    ):
        assert word not in script, word
```

`tests/integration/test_web_charts.py`

```python
import html
import json
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import add_balance_snapshot, create_account, create_rule
from finances.domain.models import DataSource
from finances.web.app import SECURITY_HEADERS, create_app
from tests.support import WEB_PORT

TODAY = date(2026, 5, 25)
CARD = "/account?name=Test%20Card"
MONTHS = [
    "2025-06",
    "2025-07",
    "2025-08",
    "2025-09",
    "2025-10",
    "2025-11",
    "2025-12",
    "2026-01",
    "2026-02",
    "2026-03",
    "2026-04",
    "2026-05",
]
SCRIPTS = [
    '<script src="/static/vendor/chart.umd.js" defer></script>',
    '<script src="/static/charts.js" defer></script>',
]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Test Card: groceries in April and May, a book, and a refund that leaves Shopping below
    zero in May; two balances. Test Checking has nothing."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        create_account(session, "Test Checking", "Test Bank", "checking")
        add_balance_snapshot(session, card.id, date(2026, 4, 30), -45000, DataSource.STATEMENT)
        add_balance_snapshot(session, card.id, date(2026, 5, 20), -61234, DataSource.AGGREGATOR)
        for number, (day, cents, description) in enumerate(
            (
                (date(2026, 4, 12), -3000, "FOOBAR GROCERY"),
                (date(2026, 5, 10), -20000, "FOOBAR GROCERY"),
                (date(2026, 5, 12), -1500, "BAZ BOOKS"),
                (date(2026, 5, 14), 2000, "BAZ TECH"),
            ),
            start=1,
        ):
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
        create_rule(session, "BAZ TECH", "Electronics")
        categorize(session)
    engine.dispose()
    return client


def charts(text: str) -> list[dict]:
    return [json.loads(html.unescape(found)) for found in re.findall(r'data-chart="([^"]*)"', text)]


def test_the_policy_allows_only_the_sites_own_scripts(home: TestClient) -> None:
    response = home.get(CARD)
    assert (
        response.headers["content-security-policy"] == SECURITY_HEADERS["content-security-policy"]
    )
    assert "script-src 'self';" in response.headers["content-security-policy"]


def test_the_account_page_loads_two_scripts_and_no_inline_script(home: TestClient) -> None:
    text = home.get(CARD).text
    assert re.findall(r"<script[^>]*>[^<]*</script>", text) == SCRIPTS
    for path, kind in (
        ("/static/vendor/chart.umd.js", "javascript"),
        ("/static/charts.js", "javascript"),
    ):
        response = home.get(path)
        assert response.status_code == 200
        assert kind in response.headers["content-type"]


@pytest.mark.parametrize("path", ["/", "/accounts", "/transactions", "/reports", "/insights"])
def test_other_pages_load_no_script(home: TestClient, path: str) -> None:
    assert "<script" not in home.get(path).text


def test_the_charts_carry_cents(home: TestClient) -> None:
    assert charts(home.get(CARD).text) == [
        {
            "kind": "pie",
            "labels": ["Food", "Uncategorized"],
            "series": [{"name": "Spent", "cents": [20000, 1500]}],
        },
        {
            "kind": "bar",
            "labels": MONTHS,
            "series": [
                {"name": "Spent", "cents": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3000, 19500]},
                {"name": "Income", "cents": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
            ],
        },
        {
            "kind": "line",
            "labels": ["2026-04-30", "2026-05-20"],
            "series": [{"name": "Balance", "cents": [-45000, -61234]}],
        },
    ]


def test_each_chart_keeps_its_table(home: TestClient) -> None:
    text = home.get(CARD).text
    assert text.count('<div class="chart">') == 3
    for heading in ("<th>Group</th>", "<th>Month</th>", "<th>Date</th>"):
        assert heading in text


def test_no_chart_without_something_to_draw(home: TestClient) -> None:
    text = home.get("/account?name=Test%20Checking").text
    assert [chart["kind"] for chart in charts(text)] == ["bar"]
    april = home.get(f"{CARD}&month=2026-04").text
    assert charts(april)[0] == {
        "kind": "pie",
        "labels": ["Food"],
        "series": [{"name": "Spent", "cents": [3000]}],
    }
    march = home.get(f"{CARD}&month=2026-03").text
    assert [chart["kind"] for chart in charts(march)] == ["bar", "line"]
```

The change to `tests/unit/test_web_security.py`, exactly this diff:

```diff
diff --git a/tests/unit/test_web_security.py b/tests/unit/test_web_security.py
index 25e2e87..7f61cc7 100644
--- a/tests/unit/test_web_security.py
+++ b/tests/unit/test_web_security.py
@@ -19,7 +19,7 @@ def test_the_host_is_this_machine_only() -> None:
 def test_the_security_headers() -> None:
     assert SECURITY_HEADERS == {
         "content-security-policy": (
-            "default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self'; "
+            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
             "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
         ),
         "x-content-type-options": "nosniff",
```

## Tests to write

`tests/unit/test_chart_views.py`: `pie_chart` with only negative lines (`None`) and with a zero line (left out); `months_chart` of 12 empty months; `balance_chart` with two snapshots on one day (both kept, in the order given oldest first).

## Rules for this phase

- No inline script, no `eval`, nothing from another site. Money in the chart data is integer cents.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_chart_library.py tests/integration/test_web_charts.py`, 13 tests;
- also `.venv/bin/python -m pytest tests/unit/test_web_security.py tests/integration/test_web_account_page.py --no-cov`: all pass;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.views --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "<script>|<script [^>]*>[^<]+</script>|on(click|load|error)=" -- src/finances/web/templates` (no output) and `git grep -n --untracked -E "https?://|//cdn|integrity=" -- src/finances/web/templates src/finances/web/static/charts.js src/finances/web/static/app.css` (no output).

## Report

As in `docs/phase-conventions.md`, headed `## Phase 16k: charts (YYYY-MM-DD)`.
