# Phase 16h: dashboard

## Goal

The site opens on a page that says how things stand and what needs doing. After this phase `/` is the **Home** page (first in the menu), with:

- **Needs attention**: how many transactions have no category (linking to Categories), how many transfers wait for review (linking to Transfers), and Phase 25's data-health problems, each linking to the page that fixes it;
- **Money**: cash, cards, other, and net worth (Phase 12b), linking to Reports;
- **This month and last**: spent, income, change, and coverage (Phase 12b), each month linking to its spending;
- **Top findings**: the month's three most serious findings (Phase 13b) and the total of all of them, linking to Insights.

It only reads, through the functions those phases built. `/` no longer redirects to Accounts.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/analysis/balances.py`, `months.py`, `insights.py`, `health.py`; `src/finances/categorize/transfers.py` (`transfer_suggestions`); `src/finances/db/repositories.py` (`list_uncategorized`)
- `src/finances/views/balances.py`, `months.py`, `insights.py`, `health.py`
- `src/finances/web/app.py`: `GET /`, `_today`, `GET /reports`, `GET /insights`

## Starting state

N is `2791` when Phase 25 is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/repositories.py` | new: `count_uncategorized` (R1) |
| `src/finances/analysis/dashboard.py` | new (R2) |
| `src/finances/web/app.py` | `GET /` (R3, R4) |
| `src/finances/web/templates/layout.html` | replaced: given |
| `src/finances/web/templates/dashboard.html` | new: given |
| `tests/integration/test_web_dashboard.py` | new: given |
| `tests/integration/test_web_pages.py` | `test_home_goes_to_accounts` removed: given change (below) |
| `tests/integration/test_dashboard_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Charts (16i brings the chart library); choosing another month; anything that writes.
- Storing the dashboard, or anything new in the reports, findings, or health it shows.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/db/repositories.py
def count_uncategorized(session: Session) -> int: ...  # the transactions list_uncategorized would list, all of them

# src/finances/analysis/dashboard.py
@dataclass(frozen=True)
class Dashboard:
    today: date
    balance: BalanceReport
    months: list[MonthLine]       # the previous month, then this one
    insights: InsightsReport      # this month's
    problems: list[Problem]
    uncategorized: int
    transfers_waiting: int


def dashboard(session: Session, today: date, backup_folder: Path) -> Dashboard: ...
```

## Requirements

- **R1.** `count_uncategorized` counts exactly the transactions `list_uncategorized` returns (no category, in no transfer pair), without a limit.
- **R2.** `dashboard` builds: `balance_report`; `month_report(session, today, 2)`; `insights_report(session, first day of today's month)`; `gather_health(session, backup_folder, today)`; `count_uncategorized`; and the number of `transfer_suggestions`.
- **R3.** `GET /` checks the database as the other pages do (`503` when it is not up to date; no redirect), then renders `dashboard.html` from `dashboard(session, _today(), effective_backup_dir)` with: `today` (ISO), `month_label` (`YYYY-MM` of today), `uncategorized`, `transfers_waiting`, `problems` (`health_rows`), `problem_links` (`backup` to `/backups`, `sync` and `drift` to `/sync`, `statements` and `gap` to `/statements`), `has_accounts` (the balance report has lines), `balance_summary`, `months` (`month_rows`), `findings` (`finding_rows`, the first three), and `findings_summary` (of all the month's findings).
- **R4.** One read session; the route holds no rule (it only picks the first three rows). The page has no form and no `POST` route.

## Given template and the change to an earlier test

`src/finances/web/templates/layout.html`

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}Finances{% endblock %}</title>
<link rel="stylesheet" href="/static/app.css">
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

`src/finances/web/templates/dashboard.html`

```html
{% extends "layout.html" %}
{% block title %}Finances{% endblock %}
{% block content %}
<h1>Home</h1>
<p class="summary">Today is {{ today }}.</p>
<h2>Needs attention</h2>
{% if uncategorized %}<p class="attention"><a href="/categories">{{ uncategorized }} transactions without a category.</a></p>
{% else %}<p class="empty">Every transaction has a category.</p>
{% endif %}
{% if transfers_waiting %}<p class="attention"><a href="/transfers">{{ transfers_waiting }} transfers waiting for review.</a></p>
{% else %}<p class="empty">No transfers wait for review.</p>
{% endif %}
{% if problems %}
<table>
<thead><tr><th>Kind</th><th>Account</th><th>Problem</th><th>What to do</th></tr></thead>
<tbody>
{% for row in problems %}<tr><td>{{ row.kind }}</td><td>{{ row.account }}</td><td><a href="{{ problem_links[row.kind] }}">{{ row.problem }}</a></td><td>{{ row.action }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No data problems found.</p>
{% endif %}
<h2>Money</h2>
{% if has_accounts %}
{% for line in balance_summary %}<p class="summary">{{ line }}</p>
{% endfor %}
{% else %}
<p class="empty">No accounts.</p>
{% endif %}
<p><a href="/reports">Balances, months, and spending</a></p>
<h2>This month and last</h2>
<table>
<thead><tr><th>Month</th><th class="amount">Spent</th><th class="amount">Income</th><th class="amount">Change</th><th>Covered</th></tr></thead>
<tbody>
{% for row in months %}<tr><td><a href="/reports?month={{ row.month }}">{{ row.month }}</a></td><td class="amount">{{ row.spent }}</td><td class="amount">{{ row.income }}</td><td class="amount">{{ row.change }}</td><td>{{ row.covered }}</td></tr>
{% endfor %}</tbody>
</table>
<h2>Top findings</h2>
{% if findings %}
<table>
<thead><tr><th>Severity</th><th>Type</th><th>About</th><th class="amount">Saves a month</th><th>Detail</th></tr></thead>
<tbody>
{% for row in findings %}<tr><td>{{ row.severity }}</td><td>{{ row.type }}</td><td>{{ row.about }}</td><td class="amount">{{ row.saves }}</td><td>{{ row.detail }}</td></tr>
{% endfor %}</tbody>
</table>
<p class="summary">{{ findings_summary }}</p>
{% else %}
<p class="empty">No findings this month.</p>
{% endif %}
<p><a href="/insights?month={{ month_label }}">All insights for {{ month_label }}</a></p>
{% endblock %}
```

`tests/integration/test_web_pages.py`, exactly this diff (`/` is now the dashboard; `tests/integration/test_web_dashboard.py` tests it):

```diff
diff --git a/tests/integration/test_web_pages.py b/tests/integration/test_web_pages.py
index e12c701..5545563 100644
--- a/tests/integration/test_web_pages.py
+++ b/tests/integration/test_web_pages.py
@@ -126,11 +126,6 @@ def household(tmp_settings: Settings, client: TestClient) -> TestClient:
     return client
 
 
-def test_home_goes_to_accounts(client: TestClient) -> None:
-    response = client.get("/", follow_redirects=False)
-    assert (response.status_code, response.headers["location"]) == (303, "/accounts")
-
-
 @pytest.mark.parametrize("path", ["/accounts", "/people", "/transactions", "/sync"])
 def test_every_page_needs_a_migrated_database(client: TestClient, path: str) -> None:
     response = client.get(path)
```

## Given tests

`tests/integration/test_web_dashboard.py` (5 tests). It sets `finances.web.app._today` to 25 May 2026. Its expected values come from running Phases 12b, 13b, and 25's own functions on its data.

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
from finances.db.repositories import add_balance_snapshot, create_account, create_rule
from finances.domain.models import DataSource
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts

TODAY = date(2026, 5, 25)
PROBLEMS = ["Kind", "Account", "Problem", "What to do"]
MONTHS = ["Month", "Spent", "Income", "Change", "Covered"]
FINDINGS = ["Severity", "Type", "About", "Saves a month", "Detail"]
NO_BACKUP = [
    "backup",
    "",
    "No backup yet.",
    "Run fin backup run, or press Back up now on the Backups page.",
]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """April and May 2026 on a card, checking, and savings: a card payment that pairs, a move
    to savings with two possible matches, coffee eight times, a grocery jump, interest, a fee."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        add_balance_snapshot(session, card.id, date(2026, 5, 20), -61234, DataSource.STATEMENT)
        add_balance_snapshot(session, checking.id, date(2026, 4, 30), 310000, DataSource.STATEMENT)
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
        ] + [(card, date(2026, 5, day), -500, "ACME COFFEE") for day in (1, 2, 4, 6, 8, 11, 13, 15)]
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
        for pattern, category in (
            ("FOOBAR", "Groceries"),
            ("PAYCHECK", "Paycheck"),
            ("ACME COFFEE", "Coffee & Dessert"),
        ):
            create_rule(session, pattern, category)
        categorize(session)
        pair_transfers(session)
    engine.dispose()
    return client


def test_home_is_the_dashboard(home: TestClient) -> None:
    response = home.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert 'href="/" aria-current="page">Home</a>' in response.text
    assert response.text.count('aria-current="page"') == 1
    assert 'href="/">Home</a>' in home.get("/accounts").text
    assert "<script" not in response.text


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_the_dashboard(home: TestClient) -> None:
    found = page(home, "/")
    assert found.rows == [
        PROBLEMS,
        NO_BACKUP,
        MONTHS,
        ["2026-04", "$30.00", "$3,000.00", "", "partly"],
        ["2026-05", "$333.45", "$0.00", "+$303.45", "partly"],
        FINDINGS,
        ["high", "interest", "", "$23.45", "Interest charged: $23.45."],
        [
            "medium",
            "spike",
            "Groceries",
            "$190.00",
            "Groceries: $200.00 this month, against $10.00 a month before.",
        ],
        ["medium", "fees", "", "$35.00", "Fees charged: $35.00."],
    ]
    assert texts(found, "attention") == [
        "6 transactions without a category.",
        "2 transfers waiting for review.",
    ]
    assert texts(found, "summary") == [
        "Today is 2026-05-25.",
        "Cash: $3,100.00. Cards: -$612.34. Other: $0.00.",
        "Net worth: $2,487.66.",
        "No balance yet: Test Savings.",
        "Findings: 4. Could save up to $268.45 a month.",
    ]


def test_every_part_links_to_its_page(home: TestClient) -> None:
    links = page(home, "/").links
    for link in (
        "/categories",
        "/transfers",
        "/backups",
        "/reports",
        "/reports?month=2026-04",
        "/reports?month=2026-05",
        "/insights?month=2026-05",
    ):
        assert link in links, link


def test_a_fresh_backup_and_an_empty_database(client: TestClient, tmp_settings: Settings) -> None:
    upgrade_to_head()
    folder = tmp_settings.effective_backup_dir
    folder.mkdir(parents=True)
    (folder / "finances-20260525-020000.db").write_bytes(b"")
    found = page(client, "/")
    assert texts(found, "empty") == [
        "Every transaction has a category.",
        "No transfers wait for review.",
        "No data problems found.",
        "No accounts.",
        "No findings this month.",
    ]
    assert found.rows == [
        MONTHS,
        ["2026-04", "$0.00", "$0.00", "", "yes"],
        ["2026-05", "$0.00", "$0.00", "$0.00", "yes"],
    ]
```

## Tests to write

`tests/integration/test_dashboard_more.py`:

- `count_uncategorized` equals `len(list_uncategorized(session, 1000))` with a paired, a categorized, and a pending transaction among the data;
- `dashboard` on the first day of a month (the previous month is last year's December when today is in January);
- a `sync`, a `statements`, and a `gap` problem each link to their page.

## Rules for this phase

- **No JavaScript.** **Thin**, as R4.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/integration/test_web_dashboard.py`, 5 tests;
- also `.venv/bin/python -m pytest tests/integration/test_web_pages.py --no-cov`: all pass;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.analysis --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|timedelta|sum\(" -- src/finances/web` and `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 16h: dashboard (YYYY-MM-DD)`.
