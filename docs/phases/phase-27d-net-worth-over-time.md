# Phase 27d: net worth over time

## Goal

The Reports page shows how the household's net worth has moved: one point a month for the last 12 months (the month's last day, and today for this month), drawn as a line with 16k's chart library and listed in a table beside it. The phase also fixes the days check on 27c's Ahead page, which accepts digits other than 0 to 9.

Net worth on a day is the sum, over the active accounts, of each account's newest balance dated on or before that day; an account with no balance by then adds nothing, and the table shows how many accounts were counted. This finishes roadmap Phase 27.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-16k-charts.md` (the chart data shape and the scripts), `docs/phases/phase-27c-looking-ahead-on-the-web.md` (R4)
- `src/finances/analysis/balances.py`, `src/finances/views/charts.py`, `src/finances/web/routes/reports.py`, `src/finances/web/templates/reports.html`, `src/finances/web/static/charts.js`
- `src/finances/db/repositories.py`: `list_accounts`, `list_balance_snapshots` (newest first: by date, then by id)

## Starting state

N is `2997` when Phase 27c is the last phase built. The given diff removes one parametrized case from `tests/integration/test_web_charts.py`, so the suite gains 12 tests, not 13.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/routes/reports.py` | `_days` (R1); the Reports page's context (R7) |
| `src/finances/domain/networth.py` | new (R2, R3) |
| `src/finances/analysis/networth.py` | new (R4) |
| `src/finances/views/networth.py` | new (R5) |
| `src/finances/views/charts.py` | `net_worth_chart` (R6) |
| `src/finances/web/templates/reports.html` | given diff |
| `tests/integration/test_web_reports.py`, `tests/integration/test_web_charts.py` | given diff (Reports may now load the chart scripts) |
| `tests/unit/test_networth.py`, `tests/integration/test_web_net_worth.py` | new: given |
| `tests/integration/test_networth_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- A terminal command for net worth over time; a block on the dashboard; a choice of how many months on the page.
- Net worth by account type over time (cash, cards, other); closed accounts in past months (see the known limit); any change to `charts.js` or 16k's charts.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/domain/networth.py  (standard library and finances.domain only)
@dataclass(frozen=True)
class NetWorthPoint:
    day: date
    net_worth_cents: int
    accounts: int          # accounts with a balance on or before day


def point_days(today: date, months: int) -> list[date]: ...
def net_worth_points(
    balances: Iterable[Sequence[tuple[date, int]]], days: Iterable[date]
) -> list[NetWorthPoint]: ...

# src/finances/analysis/networth.py
def net_worth_over_time(session: Session, today: date, months: int = 12) -> list[NetWorthPoint]: ...

# src/finances/views/networth.py
@dataclass(frozen=True)
class NetWorthRow:     # Date, Net worth, Accounts
    date: str
    net_worth: str
    accounts: str


def net_worth_rows(points: list[NetWorthPoint]) -> list[NetWorthRow]: ...

# src/finances/views/charts.py
def net_worth_chart(points: list[NetWorthPoint]) -> dict | None: ...
```

## Requirements

### Part 1: the days check

- **R1.** 27c's `_days` accepts only text made of the ASCII digits `0` to `9` (`"07"` is still 7). Other digits that `str.isdigit` accepts (`"٣"`, `"²"`) are refused with `DAYS_REFUSED` and status 400, like any other refused value; no other message can reach the page.

### Part 2: the rules (pure)

- **R2.** `point_days(today, months)` gives one day for each of the `months` calendar months ending with today's month, oldest first: the month's last day, except today's month, which gives `today`. Across a year end and in February of a leap year as the calendar says.
- **R3.** `net_worth_points` takes one sequence per account, each ordered **newest first** (as `list_balance_snapshots` returns them: two balances on one date keep that order), and for each day sums, per account, the **first** entry dated on or before the day; accounts with none add nothing and are not counted. Days on which no account is counted are left out. The result is in the order of `days`.

### Part 3: loading and views

- **R4.** `net_worth_over_time` reads the **active** accounts (`list_accounts`), their `list_balance_snapshots`, and returns `net_worth_points` over `point_days(today, months)`. Balances dated after today never count, because every day is on or before today.
- **R5.** `net_worth_rows` gives one row per point: the ISO date, `format_cents` of the net worth (signed), and the count as text.
- **R6.** `net_worth_chart` gives `{"kind": "line", "labels": [ISO dates], "series": [{"name": "Net worth", "cents": [...]}]}`, oldest first, or `None` for no points. Cents stay whole numbers.

### Part 4: the page

- **R7.** The Reports page adds `net_worth` (`net_worth_rows`) and `net_worth_chart` (`json.dumps` of the chart, or `None`) to its context, from `net_worth_over_time(session, web_app._today())` in the page's one reading session, with 12 months whatever month the page shows. The given `reports.html` draws the chart and the table after Balances, and loads the two chart scripts only when there is a chart; with no balances it shows `No balances yet.`

**Known limit (record it, do not fix it):** a closed account leaves past months too, so closing an account changes the history shown.

## Given tests

13 tests in two files. `_today` is replaced after the app is created.

`tests/unit/test_networth.py`

```python
from datetime import date

import pytest

from finances.domain.networth import NetWorthPoint, net_worth_points, point_days
from finances.views.charts import net_worth_chart
from finances.views.networth import NetWorthRow, net_worth_rows


@pytest.mark.parametrize(
    ("today", "months", "days"),
    [
        (date(2026, 5, 25), 3, [date(2026, 3, 31), date(2026, 4, 30), date(2026, 5, 25)]),
        (date(2026, 2, 10), 3, [date(2025, 12, 31), date(2026, 1, 31), date(2026, 2, 10)]),
        (date(2024, 3, 1), 2, [date(2024, 2, 29), date(2024, 3, 1)]),
        (date(2026, 4, 30), 1, [date(2026, 4, 30)]),
    ],
)
def test_one_day_a_month_ending_today(today: date, months: int, days: list[date]) -> None:
    assert point_days(today, months) == days


CHECKING = [(date(2026, 5, 20), 300000), (date(2026, 4, 30), 250000), (date(2026, 3, 15), 200000)]
CARD = [(date(2026, 5, 24), -45000), (date(2026, 4, 30), -30000)]
SAVINGS = [(date(2026, 5, 1), 100000)]
DAYS = [date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30), date(2026, 5, 25)]


def test_each_account_counts_its_newest_balance_on_or_before_the_day() -> None:
    assert net_worth_points([CHECKING, CARD, SAVINGS], DAYS) == [
        NetWorthPoint(date(2026, 3, 31), 200000, 1),
        NetWorthPoint(date(2026, 4, 30), 220000, 2),
        NetWorthPoint(date(2026, 5, 25), 355000, 3),
    ]


def test_two_balances_on_one_day_take_the_first_listed() -> None:
    same_day = [(date(2026, 5, 20), 310000), (date(2026, 5, 20), 300000)]
    assert net_worth_points([same_day], [date(2026, 5, 25)]) == [
        NetWorthPoint(date(2026, 5, 25), 310000, 1)
    ]


def test_nothing_before_the_first_balance() -> None:
    assert net_worth_points([CARD], [date(2026, 3, 31)]) == []
    assert net_worth_points([], DAYS) == []


def test_rows_and_chart() -> None:
    points = [
        NetWorthPoint(date(2026, 4, 30), -30000, 1),
        NetWorthPoint(date(2026, 5, 25), 355000, 3),
    ]
    assert net_worth_rows(points) == [
        NetWorthRow("2026-04-30", "-$300.00", "1"),
        NetWorthRow("2026-05-25", "$3,550.00", "3"),
    ]
    assert net_worth_chart(points) == {
        "kind": "line",
        "labels": ["2026-04-30", "2026-05-25"],
        "series": [{"name": "Net worth", "cents": [-30000, 355000]}],
    }
    assert net_worth_chart([]) is None
```

`tests/integration/test_web_net_worth.py`

```python
import html
import json
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import add_balance_snapshot, create_account, set_account_active
from finances.domain.models import DataSource
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, texts

TODAY = date(2026, 5, 25)
HEADING = ["Date", "Net worth", "Accounts"]
SCRIPTS = [
    '<script src="/static/vendor/chart.umd.js" defer></script>',
    '<script src="/static/charts.js" defer></script>',
]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return found


@pytest.fixture
def money(client: TestClient) -> TestClient:
    """Checking from March, the card from April, savings from May; a closed account; and a
    checking balance dated after today."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        closed = create_account(session, "Test Old", "Test Bank", "checking")
        for account, day, cents in (
            (checking, date(2026, 3, 15), 200000),
            (checking, date(2026, 4, 30), 250000),
            (checking, date(2026, 5, 20), 300000),
            (checking, date(2026, 6, 1), 999900),
            (card, date(2026, 4, 30), -30000),
            (card, date(2026, 5, 24), -45000),
            (savings, date(2026, 5, 1), 100000),
            (closed, date(2026, 1, 31), 500000),
        ):
            add_balance_snapshot(session, account.id, day, cents, DataSource.STATEMENT)
        set_account_active(session, closed.id, False)
    engine.dispose()
    return client


def section(rows: list[list[str]]) -> list[list[str]]:
    start = rows.index(HEADING)
    end = start + 1
    while end < len(rows) and len(rows[end]) == len(HEADING):
        end += 1
    return rows[start:end]


def charts(text: str) -> list[dict]:
    return [json.loads(html.unescape(found)) for found in re.findall(r'data-chart="([^"]*)"', text)]


def test_net_worth_over_time(money: TestClient) -> None:
    response = money.get("/reports")
    assert response.status_code == 200
    assert section(Page(response.text).rows) == [
        HEADING,
        ["2026-03-31", "$2,000.00", "1"],
        ["2026-04-30", "$2,200.00", "2"],
        ["2026-05-25", "$3,550.00", "3"],
    ]
    assert charts(response.text) == [
        {
            "kind": "line",
            "labels": ["2026-03-31", "2026-04-30", "2026-05-25"],
            "series": [{"name": "Net worth", "cents": [200000, 220000, 355000]}],
        }
    ]
    assert re.findall(r"<script[^>]*>[^<]*</script>", response.text) == SCRIPTS
    assert response.text.count('<div class="chart">') == 1


def test_the_months_follow_today_not_the_month_shown(money: TestClient) -> None:
    rows = section(Page(money.get("/reports?month=2026-03").text).rows)
    assert rows[-1] == ["2026-05-25", "$3,550.00", "3"]


def test_no_balances_yet(client: TestClient) -> None:
    upgrade_to_head()
    response = client.get("/reports")
    assert texts(Page(response.text), "empty")[:2] == ["No accounts.", "No balances yet."]
    assert "<script" not in response.text
    assert "data-chart" not in response.text


@pytest.mark.parametrize("days", ["٣", "²"])
def test_days_take_only_the_digits_0_to_9(money: TestClient, days: str) -> None:
    response = money.get("/ahead", params={"days": days})
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["days must be a whole number from 1 to 90"]
```

## Given diff

Apply exactly (`reports.html`; two earlier tests that said Reports loads no script):

```text
diff --git a/src/finances/web/templates/reports.html b/src/finances/web/templates/reports.html
index 1f9f5e2..cb6285f 100644
--- a/src/finances/web/templates/reports.html
+++ b/src/finances/web/templates/reports.html
@@ -1,5 +1,7 @@
 {% extends "layout.html" %}
 {% block title %}Reports · Finances{% endblock %}
+{% block scripts %}{% if net_worth_chart %}<script src="/static/vendor/chart.umd.js" defer></script>
+<script src="/static/charts.js" defer></script>{% endif %}{% endblock %}
 {% block content %}
 <h1>Reports</h1>
 {% include "messages.html" %}
@@ -16,6 +18,18 @@
 {% else %}
 <p class="empty">No accounts.</p>
 {% endif %}
+<h2>Net worth over time</h2>
+{% if net_worth %}
+<div class="chart"><canvas data-chart="{{ net_worth_chart }}" role="img" aria-label="Net worth at the end of each month"></canvas></div>
+<table>
+<thead><tr><th>Date</th><th class="amount">Net worth</th><th class="amount">Accounts</th></tr></thead>
+<tbody>
+{% for row in net_worth %}<tr><td>{{ row.date }}</td><td class="amount">{{ row.net_worth }}</td><td class="amount">{{ row.accounts }}</td></tr>
+{% endfor %}</tbody>
+</table>
+{% else %}
+<p class="empty">No balances yet.</p>
+{% endif %}
 <h2>Months</h2>
 {% if months %}
 <table>
diff --git a/tests/integration/test_web_charts.py b/tests/integration/test_web_charts.py
index 889fcea..6a876ef 100644
--- a/tests/integration/test_web_charts.py
+++ b/tests/integration/test_web_charts.py
@@ -106,7 +106,7 @@ def test_the_account_page_loads_two_scripts_and_no_inline_script(home: TestClien
         assert kind in response.headers["content-type"]
 
 
-@pytest.mark.parametrize("path", ["/", "/accounts", "/transactions", "/reports", "/insights"])
+@pytest.mark.parametrize("path", ["/", "/accounts", "/transactions", "/insights"])
 def test_other_pages_load_no_script(home: TestClient, path: str) -> None:
     assert "<script" not in home.get(path).text
 
diff --git a/tests/integration/test_web_reports.py b/tests/integration/test_web_reports.py
index 85a5b58..fcfc37a 100644
--- a/tests/integration/test_web_reports.py
+++ b/tests/integration/test_web_reports.py
@@ -213,7 +213,6 @@ def test_the_menu_has_reports(home: TestClient) -> None:
     assert 'href="/reports" aria-current="page">Reports</a>' in html
     assert html.count('aria-current="page"') == 1
     assert 'href="/reports">Reports</a>' in home.get("/transfers").text
-    assert "<script" not in html
 
 
 def test_a_database_that_is_not_migrated(client: TestClient) -> None:
```

## Tests to write

`tests/integration/test_networth_more.py`: `point_days` with 12 months from January (the first day is in the year before); a negative net worth (only a card); an account whose only balance is after today (not counted, not shown); two snapshots on one date from different sources through `net_worth_over_time` (the later-added counts, by `list_balance_snapshots`' order); `/ahead?days=07` still 7.

## Rules for this phase

- `domain/networth.py` imports only the standard library and `finances.domain`; money stays integer cents, also in the chart data.
- The route holds no rule: no sums, sorting, or date arithmetic in `routes/reports.py`.
- Every earlier test passes unchanged apart from the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_networth.py tests/integration/test_web_net_worth.py`, 13 tests; at least N + 12 passed in all;
- also `.venv/bin/python -m pytest tests/integration/test_web_reports.py tests/integration/test_web_charts.py tests/integration/test_web_ahead.py tests/integration/test_one_today.py --no-cov`: all pass;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.networth --cov=finances.analysis.networth --cov=finances.views.networth --cov=finances.views.charts --cov=finances.web.routes.reports --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(from|import) +finances\.(db|sync|web|cli|ingest|analysis|views|categorize)" -- src/finances/domain` and `git grep -n --untracked -E "sum\(|sorted\(|timedelta|select\(|session\.(add|execute|delete)" -- src/finances/web/routes/reports.py`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 27d: net worth over time (YYYY-MM-DD)`.
