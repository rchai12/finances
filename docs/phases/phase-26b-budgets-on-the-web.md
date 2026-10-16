# Phase 26b: budgets on the web

## Goal

The household sets and follows its budgets in the browser. After this phase:

- the menu has **Budgets**: a month (this month unless another is chosen), each budget's target, spent, left, share used, and share of the month gone, with a **Remove** button, the number over budget, and a **Set a budget** form (a category or a group, and an amount a month);
- each budget's name opens the transactions it counts (Phase 16e);
- the Home page shows **Budgets this month**.

Everything goes through Phase 26a's functions and messages.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-26a-budgets.md`; `src/finances/analysis/budgets.py`, `src/finances/views/budgets.py`, `src/finances/cli/budgets.py`
- `src/finances/analysis/dashboard.py`; `src/finances/web/app.py`: `GET /`, the Categories page's forms, `_today`

## Starting state

N is `2868` when Phase 26a is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/analysis/dashboard.py` | `Dashboard` gains `budgets` (R1) |
| `src/finances/web/app.py` | two notices; `GET /budgets`, `POST /budgets/set`, `POST /budgets/remove` (R2 to R4); the Home page's budgets (R5) |
| `src/finances/web/templates/layout.html`, `dashboard.html` | replaced: given |
| `src/finances/web/templates/budgets.html` | new: given |
| `tests/integration/test_web_budgets.py` | new: given |
| `tests/integration/test_web_budgets_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Editing a budget's amount in its row (setting it again replaces it); budget history; charts of budgets.
- Any change to how budgets count.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/analysis/dashboard.py: one field added, last, with a default
    budgets: tuple[BudgetLine, ...] = ()
```

Notices added to `NOTICES`, in full: `budget-set` `Budget saved.`; `budget-removed` `Budget removed.`

No new messages: an amount `parse_money` refuses gives Phase 26a's `a budget must be an amount from $0.01 to $1,000,000.00`; every other message is Phase 26a's.

## Requirements

- **R1.** `dashboard` also fills `budgets` with `budget_report(session, first day of today's month, today)`.
- **R2.** `GET /budgets` checks the database as the other pages do. It reads `month` as text: empty means the month of `_today()`, otherwise `month_range`; a bad month renders the page with status `400`, the message as `error`, and no budgets. It renders `budgets.html` with `month_text` (as sent), `month_label` (`YYYY-MM`, or none after a bad month), `start` and `end` (ISO), `rows` (`budget_rows` of `budget_report(session, start, _today())`), `summary` (`budgets_summary`), `choices` (`category_choices`), `form` (`name` and `amount`, empty), and `error`.
- **R3.** `POST /budgets/set` (`name`, `amount`) runs the existing checks (origin, form token, database), reads the amount with `parse_money` (its error becomes the amount message), and calls `set_budget`. Done: `/budgets?notice=budget-set`. Refused: the Budgets page for the current month, status `400`, the message as `error`, and `form` holding what was sent.
- **R4.** `POST /budgets/remove` (`name`) calls `remove_budget`. Done: `/budgets?notice=budget-removed`. Refused: the Budgets page with status `400`.
- **R5.** `GET /` also passes `budgets` (`budget_rows` of the dashboard's `budgets`); the given template shows them, or `No budgets yet.` with the class `hint`, so the Home page's earlier tests read the same tables and paragraphs.
- **R6.** One session per request; the routes hold no rule.

## Given templates

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
  <a href="/budgets"{% if section == "budgets" %} aria-current="page"{% endif %}>Budgets</a>
  <a href="/sync"{% if section == "sync" %} aria-current="page"{% endif %}>SimpleFIN</a>
  <a href="/backups"{% if section == "backups" %} aria-current="page"{% endif %}>Backups</a>
</nav>
<main>
{% block content %}{% endblock %}
</main>
</body>
</html>
```

`src/finances/web/templates/budgets.html`

```html
{% extends "layout.html" %}
{% block title %}Budgets · Finances{% endblock %}
{% block content %}
<h1>Budgets</h1>
{% include "messages.html" %}
<form method="get" action="/budgets" class="fields">
  <label>Month <input type="month" name="month" value="{{ month_text }}"></label>
  <button type="submit">Show</button>
</form>
{% if month_label %}
<p class="summary">Budgets for {{ month_label }}.</p>
{% if rows %}
<table>
<thead><tr><th>Budget</th><th>Kind</th><th class="amount">Target</th><th class="amount">Spent</th><th class="amount">Left</th><th class="amount">Used</th><th class="amount">Month gone</th><th></th></tr></thead>
<tbody>
{% for row in rows %}<tr><td><a href="/transactions?from={{ start }}&amp;to={{ end }}&amp;{{ row.kind if row.kind == 'group' else 'category' }}={{ row.budget|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.budget }}</a></td><td>{{ row.kind }}</td><td class="amount">{{ row.target }}</td><td class="amount">{{ row.spent }}</td><td class="amount">{{ row.left }}</td><td class="amount">{{ row.used }}</td><td class="amount">{{ row.month_gone }}</td><td><form method="post" action="/budgets/remove" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="name" value="{{ row.budget }}"><button type="submit">Remove</button></form></td></tr>
{% endfor %}</tbody>
</table>
<p class="summary">{{ summary }}</p>
{% else %}
<p class="empty">No budgets.</p>
{% endif %}
{% endif %}
<h2>Set a budget</h2>
<p class="hint">One amount for every month; spending counts as in the reports (refunds reduce it, transfers and income do not count). A group's budget covers all of its categories.</p>
<form method="post" action="/budgets/set" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <label>Category or group
    <select name="name" required>
      <option value=""{% if not form.name %} selected{% endif %}>Choose</option>
      {% for group, names in choices %}<optgroup label="{{ group }}">
        <option value="{{ group }}"{% if group == form.name %} selected{% endif %}>{{ group }} (the group)</option>
        {% for name in names %}<option value="{{ name }}"{% if name == form.name %} selected{% endif %}>{{ name }}</option>
        {% endfor %}</optgroup>
      {% endfor %}
    </select>
  </label>
  <label>Amount a month <input name="amount" required inputmode="decimal" value="{{ form.amount }}"></label>
  <button type="submit">Save budget</button>
</form>
{% endblock %}
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
<h2>Budgets this month</h2>
{% if budgets %}
<table>
<thead><tr><th>Budget</th><th class="amount">Spent</th><th class="amount">Target</th><th class="amount">Used</th><th class="amount">Month gone</th></tr></thead>
<tbody>
{% for row in budgets %}<tr><td>{{ row.budget }}</td><td class="amount">{{ row.spent }}</td><td class="amount">{{ row.target }}</td><td class="amount">{{ row.used }}</td><td class="amount">{{ row.month_gone }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="hint">No budgets yet.</p>
{% endif %}
<p><a href="/budgets">Budgets</a></p>
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

## Given tests

`tests/integration/test_web_budgets.py` (16 tests). It sets `finances.web.app._today` to 25 May 2026, so this month's share gone is 81%.

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
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, post, texts

TODAY = date(2026, 5, 25)
HEADINGS = ["Budget", "Kind", "Target", "Spent", "Left", "Used", "Month gone", ""]
AMOUNT = "a budget must be an amount from $0.01 to $1,000,000.00"
MAY = [
    HEADINGS,
    ["Dining", "category", "$250.00", "$300.00", "-$50.00", "120%", "81%", "Remove"],
    ["Food", "group", "$400.00", "$404.50", "-$4.50", "101%", "81%", "Remove"],
    ["Groceries", "category", "$200.00", "$100.00", "$100.00", "50%", "81%", "Remove"],
    ["Travel", "group", "$100.00", "$0.00", "$100.00", "0%", "81%", "Remove"],
]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """The data of tests/e2e/test_cli_budgets.py, with its four budgets set."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (day, cents, description) in enumerate(
            (
                (5, -20000, "ACME DINER"),
                (12, -10000, "ACME DINER"),
                (6, -12000, "FOOBAR GROCERY"),
                (9, 2000, "FOOBAR GROCERY"),
                (7, -450, "ACME COFFEE"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for pattern, category in (
            ("ACME DINER", "Dining"),
            ("FOOBAR", "Groceries"),
            ("ACME COFFEE", "Coffee & Dessert"),
        ):
            create_rule(session, pattern, category)
        categorize(session)
        for name, cents in (
            ("Dining", 25000),
            ("Food", 40000),
            ("Groceries", 20000),
            ("Travel", 10000),
        ):
            set_budget(session, name, cents)
    engine.dispose()
    client.get("/budgets")
    return client


def test_the_menu_has_budgets(home: TestClient) -> None:
    html = home.get("/budgets").text
    assert 'href="/budgets" aria-current="page">Budgets</a>' in html
    assert html.count('aria-current="page"') == 1
    assert 'href="/budgets">Budgets</a>' in home.get("/accounts").text
    assert "<script" not in html


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get("/budgets")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_this_months_budgets(home: TestClient) -> None:
    found = page(home, "/budgets")
    assert found.rows == MAY
    assert texts(found, "summary") == ["Budgets for 2026-05.", "Over budget: 2."]
    assert found.find("/budgets")["inputs"]["month"] == ("month", "")
    assert [form["inputs"]["name"] for form in found.all("/budgets/remove")] == [
        ("hidden", "Dining"),
        ("hidden", "Food"),
        ("hidden", "Groceries"),
        ("hidden", "Travel"),
    ]
    links = [link for link in found.links if link.startswith("/transactions?")]
    assert links[:2] == [
        "/transactions?from=2026-05-01&to=2026-05-31&category=Dining&kind=spending&limit=1000",
        "/transactions?from=2026-05-01&to=2026-05-31&group=Food&kind=spending&limit=1000",
    ]


def test_another_month(home: TestClient) -> None:
    found = page(home, "/budgets?month=2026-04")
    assert found.rows[1] == [
        "Dining",
        "category",
        "$250.00",
        "$0.00",
        "$250.00",
        "0%",
        "100%",
        "Remove",
    ]
    assert texts(found, "summary") == ["Budgets for 2026-04.", "Over budget: 0."]
    response = home.get("/budgets?month=2026-13")
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", "month must be a year and month, like 2026-05") in found.paragraphs
    assert found.rows == []


def test_set_a_budget(home: TestClient) -> None:
    response = post(home, "/budgets/set", name="Coffee & Dessert", amount="45.50")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/budgets?notice=budget-set",
    )
    found = page(home, response.headers["location"])
    assert ("notice", "Budget saved.") in found.paragraphs
    assert [
        "Coffee & Dessert",
        "category",
        "$45.50",
        "$4.50",
        "$41.00",
        "10%",
        "81%",
        "Remove",
    ] in found.rows
    response = post(home, "/budgets/set", name="dining", amount="$300.00")
    assert response.status_code == 303
    assert page(home, "/budgets").rows[2][:3] == ["Dining", "category", "$300.00"]


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"name": "Nope", "amount": "10"}, "category not found"),
        ({"name": "Dining", "amount": "ten"}, AMOUNT),
        ({"name": "Dining", "amount": "0"}, AMOUNT),
        ({"name": "Dining", "amount": "1000000.01"}, AMOUNT),
    ],
)
def test_a_refused_budget_keeps_the_form(home: TestClient, fields: dict, message: str) -> None:
    response = post(home, "/budgets/set", **fields)
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", message) in found.paragraphs
    form = found.find("/budgets/set")
    assert form["inputs"]["amount"] == ("text", fields["amount"])
    assert found.rows == MAY


def test_remove_a_budget(home: TestClient) -> None:
    response = post(home, "/budgets/remove", name="Groceries")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/budgets?notice=budget-removed",
    )
    found = page(home, response.headers["location"])
    assert ("notice", "Budget removed.") in found.paragraphs
    assert [row[0] for row in found.rows[1:]] == ["Dining", "Food", "Travel"]


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("Nope", "category not found"),
        ("Coffee & Dessert", "there is no budget for Coffee & Dessert"),
    ],
)
def test_a_refused_removal(home: TestClient, name: str, message: str) -> None:
    response = post(home, "/budgets/remove", name=name)
    assert response.status_code == 400
    assert ("error", message) in Page(response.text).paragraphs


@pytest.mark.parametrize("path", ["/budgets/set", "/budgets/remove"])
def test_a_form_without_the_token_is_refused(home: TestClient, path: str) -> None:
    response = home.post(path, data={"name": "Dining", "amount": "1"}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")
    assert home.get(path).status_code == 405


def test_the_dashboard_shows_this_months_budgets(home: TestClient) -> None:
    found = page(home, "/")
    start = found.rows.index(["Budget", "Spent", "Target", "Used", "Month gone"])
    assert found.rows[start : start + 5] == [
        ["Budget", "Spent", "Target", "Used", "Month gone"],
        ["Dining", "$300.00", "$250.00", "120%", "81%"],
        ["Food", "$404.50", "$400.00", "101%", "81%"],
        ["Groceries", "$100.00", "$200.00", "50%", "81%"],
        ["Travel", "$0.00", "$100.00", "0%", "81%"],
    ]
    assert "/budgets" in found.links


def test_the_dashboard_without_budgets(client: TestClient) -> None:
    upgrade_to_head()
    assert ("hint", "No budgets yet.") in page(client, "/").paragraphs
```

## Tests to write

`tests/integration/test_web_budgets_more.py`: `dashboard` with a budget whose month has no spending; a group's link uses `group=` and a category's `category=` for names with `&` in them (encoded); `POST /budgets/remove` then `GET /budgets` for a month in which no budget is left (`No budgets.`).

## Rules for this phase

- **No JavaScript.** **Thin**, as R6.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/integration/test_web_budgets.py`, 16 tests;
- also `.venv/bin/python -m pytest tests/integration/test_web_dashboard.py tests/integration/test_web_pages.py tests/e2e/test_cli_budgets.py --no-cov`: all pass;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.analysis.dashboard --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|timedelta" -- src/finances/web` and `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates/budgets.html src/finances/web/templates/dashboard.html`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 26b: budgets on the web (YYYY-MM-DD)`.
