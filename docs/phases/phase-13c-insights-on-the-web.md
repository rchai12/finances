# Phase 13c: insights on the web

## Goal

The household reads its insights in the browser. After this phase the menu has **Insights**: one page for a month (this month unless another is chosen) with the findings and what they could save, the active recurring charges and what they cost a month, and the merchants of the month. It only reads, through the functions of Phases 13a and 13b, and shows their words.

Two smaller changes come with it:

- **A fix from Phase 13b's follow-up.** A subscription overlap could not include a yearly plan last charged before the four months the report reads, because the merchant's category was taken only from those months. The category now comes from the merchant's latest charge on or before the month's last day, however old.
- **Shared test helpers.** `tests/support.py` (given) holds the helpers that given tests have been copying: running `fin` and reading its tables, and reading web pages. New tests import them; `docs/testing.md` says so.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-13a-recurring-charges.md`, `docs/phases/phase-13b-findings-and-merchant-stats.md`
- `src/finances/analysis/insights.py`, `src/finances/views/insights.py`, `src/finances/views/recurring.py`, `src/finances/cli/reports.py` (`insights_command`)
- `src/finances/web/app.py`: the Reports page (`GET /reports`), its use of `_today` and of a refused request

## Starting state

N is `2523` when Phase 13b is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/analysis/insights.py` | the merchant categories for overlaps (R1) |
| `src/finances/views/insights.py` | new: `insights_heading` (R2) |
| `src/finances/cli/reports.py` | `fin insights` prints `insights_heading` (R2) |
| `src/finances/web/app.py` | `GET /insights` (R3 to R6) |
| `src/finances/web/templates/layout.html` | replaced: given |
| `src/finances/web/templates/insights.html` | new: given |
| `tests/support.py` | new: given |
| `tests/integration/test_web_insights.py` | new: given |
| `docs/testing.md` | one rule added: given (below) |
| `docs/progress.md` | one new entry |

## Out of scope

- Changing existing tests to use `tests/support.py`; they keep their copies until a later phase changes them.
- Dismissing findings (Phase 19), a page per merchant, charts, JavaScript, any form that writes.
- Any other change to the findings, recurring charges, or merchant stats.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/views/insights.py
def insights_heading(report: InsightsReport) -> str: ...  # "Insights for YYYY-MM."
```

No new messages: a month that is not one gives Phase 12a's `month must be a year and month, like 2026-05`.

The rule added to `docs/testing.md`, as item 8 of "Rules":

8. **Shared helpers live in `tests/support.py`** (from Phase 13c): running `fin` and reading its tables (`run`, `table_rows`, `plain_lines`, `failed_cleanly`) and reading web pages (`Page`, `page`, `post`, `texts`). New tests import them instead of copying them; older tests keep their copies until they are next changed.

## Requirements

- **R1.** `insights_report` maps each merchant to the category of its latest charge on or before M's last day among **all** charges, not only the four months it reads for the findings (the latest by day, then by the order loaded). It may read the charges a second time for this. Nothing else in the report changes.
- **R2.** `insights_heading` returns `Insights for YYYY-MM.`; `fin insights` prints it instead of building the line itself (its output is unchanged).
- **R3.** `GET /insights` checks the database as the other pages do (`503` when it is not up to date). It reads `month` as text: empty means the current month (`month_bounds(_today())`), otherwise `month_range`. It renders `insights.html` with `form` (`month` exactly as sent) and `report`.
- **R4.** `report` holds `heading` (`insights_heading`), `findings` (`finding_rows`), `findings_summary` (`findings_summary`), `recurring` (`recurring_rows` of `recurring_charges(session, M's last day)`, active only), `recurring_summary` (`recurring_summary` of the same list), and `merchants` (`merchant_rows`), all from one `insights_report` of M.
- **R5.** A month that is not one renders the same page with status `400`, the message as `error`, and `report` `None`.
- **R6.** One read session for the page; no `POST` route. The route holds no rule.

## Given files

`tests/support.py`

```python
"""Helpers shared by tests: running a command and reading its output, and reading web pages.

New tests import these instead of copying them. Tests written before Phase 13c keep their own
copies.
"""

from html.parser import HTMLParser

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from finances.cli.main import app

CLI_NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
WEB_NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"
WEB_PORT = 8765

runner = CliRunner(env={"COLUMNS": "250"})


def run(*args: object):
    """Run `fin` with these arguments, each turned into text."""
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    """The heading and the rows of every table in the output, as lists of cell texts."""
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def plain_lines(output: str) -> list[str]:
    """The lines of the output that are not part of a table, without empty ones."""
    tables = ("│", "┃", "┏", "┡", "└")
    return [line for line in output.splitlines() if line and not line.startswith(tables)]


def failed_cleanly(result, message: str) -> bool:
    """Whether the command ended with exit code 1 and only this error message."""
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


class Page(HTMLParser):
    """The parts of a page the tests read: table rows, paragraphs, and forms."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.paragraphs: list[tuple[str, str]] = []
        self.forms: list[dict] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.paragraph: str | None = None
        self.text: list[str] = []
        self.form: dict | None = None
        self.select: str | None = None
        self.links: list[str] = []
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag == "a":
            self.links.append(values.get("href", ""))
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag == "p":
            self.paragraph = values.get("class", "")
            self.text = []
        elif tag == "form":
            self.form = {
                "action": values.get("action", ""),
                "method": values.get("method", "get"),
                "inputs": {},
                "selects": {},
            }
            self.forms.append(self.form)
        elif tag == "input" and self.form is not None:
            self.form["inputs"][values.get("name", "")] = (
                values.get("type", "text"),
                values.get("value", ""),
            )
        elif tag == "select" and self.form is not None:
            self.select = values.get("name", "")
            self.form["selects"][self.select] = []
        elif tag == "option" and self.form is not None and self.select is not None:
            self.form["selects"][self.select].append(
                (values.get("value", ""), "selected" in values)
            )

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "p" and self.paragraph is not None:
            self.paragraphs.append((self.paragraph, "".join(self.text).strip()))
            self.paragraph = None
        elif tag == "form":
            self.form = None
        elif tag == "select":
            self.select = None

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)
        if self.paragraph is not None:
            self.text.append(data)

    def all(self, action: str) -> list[dict]:
        return [form for form in self.forms if form["action"] == action]

    def find(self, action: str) -> dict:
        found = [form for form in self.forms if form["action"] == action]
        assert len(found) == 1, action
        return found[0]


def page(client: TestClient, path: str) -> Page:
    return Page(client.get(path).text)


def post(client: TestClient, path: str, **fields: str):
    """Post a form with the client's form token, without following the redirect."""
    return client.post(
        path, data={"csrf": client.cookies["fin_csrf"], **fields}, follow_redirects=False
    )


def texts(found: Page, kind: str) -> list[str]:
    """The texts of the page's paragraphs of this class, in order."""
    return [text for name, text in found.paragraphs if name == kind]
```

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
  <a href="/accounts"{% if section == "accounts" %} aria-current="page"{% endif %}>Accounts</a>
  <a href="/people"{% if section == "people" %} aria-current="page"{% endif %}>People</a>
  <a href="/transactions"{% if section == "transactions" %} aria-current="page"{% endif %}>Transactions</a>
  <a href="/categories"{% if section == "categories" %} aria-current="page"{% endif %}>Categories</a>
  <a href="/transfers"{% if section == "transfers" %} aria-current="page"{% endif %}>Transfers</a>
  <a href="/reports"{% if section == "reports" %} aria-current="page"{% endif %}>Reports</a>
  <a href="/insights"{% if section == "insights" %} aria-current="page"{% endif %}>Insights</a>
  <a href="/sync"{% if section == "sync" %} aria-current="page"{% endif %}>SimpleFIN</a>
</nav>
<main>
{% block content %}{% endblock %}
</main>
</body>
</html>
```

`src/finances/web/templates/insights.html`

```html
{% extends "layout.html" %}
{% block title %}Insights · Finances{% endblock %}
{% block content %}
<h1>Insights</h1>
{% include "messages.html" %}
<form method="get" action="/insights" class="fields">
  <label>Month <input type="month" name="month" value="{{ form.month }}"></label>
  <button type="submit">Show</button>
</form>
{% if report %}
<p class="summary">{{ report.heading }}</p>
<h2>Findings</h2>
{% if report.findings %}
<table>
<thead><tr><th>Severity</th><th>Type</th><th>About</th><th class="amount">Saves a month</th><th>Detail</th></tr></thead>
<tbody>
{% for row in report.findings %}<tr><td>{{ row.severity }}</td><td>{{ row.type }}</td><td>{{ row.about }}</td><td class="amount">{{ row.saves }}</td><td>{{ row.detail }}</td></tr>
{% endfor %}</tbody>
</table>
<p class="summary">{{ report.findings_summary }}</p>
{% else %}
<p class="empty">No findings.</p>
{% endif %}
<h2>Recurring charges</h2>
{% if report.recurring %}
<table>
<thead><tr><th>Merchant</th><th>Every</th><th class="amount">Amount</th><th class="amount">Monthly</th><th class="amount">Count</th><th>Last</th><th>Next</th></tr></thead>
<tbody>
{% for row in report.recurring %}<tr><td>{{ row.merchant }}</td><td>{{ row.every }}</td><td class="amount">{{ row.amount }}</td><td class="amount">{{ row.monthly }}</td><td class="amount">{{ row.count }}</td><td>{{ row.last }}</td><td>{{ row.next }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No recurring charges.</p>
{% endif %}
<p class="summary">{{ report.recurring_summary }}</p>
<h2>Merchants</h2>
{% if report.merchants %}
<table>
<thead><tr><th>Merchant</th><th class="amount">Visits</th><th class="amount">Spent</th><th class="amount">Average</th><th class="amount">Baseline</th><th class="amount">Change</th><th class="amount">Weekend</th></tr></thead>
<tbody>
{% for row in report.merchants %}<tr><td>{{ row.merchant }}</td><td class="amount">{{ row.visits }}</td><td class="amount">{{ row.spent }}</td><td class="amount">{{ row.average }}</td><td class="amount">{{ row.baseline }}</td><td class="amount">{{ row.change }}</td><td class="amount">{{ row.weekend }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No spending.</p>
{% endif %}
{% endif %}
{% endblock %}
```

## Given tests

`tests/integration/test_web_insights.py` (9 tests). It imports from `tests/support.py`. `test_a_yearly_plan_charged_before_the_window_still_overlaps` and the overlap row of `test_a_month` are the failing-first tests of R1.

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts

FINDINGS = ["Severity", "Type", "About", "Saves a month", "Detail"]
RECURRING = ["Merchant", "Every", "Amount", "Monthly", "Count", "Last", "Next"]
MERCHANTS = ["Merchant", "Visits", "Spent", "Average", "Baseline", "Change", "Weekend"]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """The data of tests/e2e/test_cli_insights.py, plus a yearly cloud plan last charged in
    January 2026, before the four months a May report reads."""
    rows = [
        (date(2026, 2, 3), -6000, "ACME DINER"),
        (date(2026, 3, 17), -6000, "ACME DINER"),
        (date(2026, 4, 9), -6000, "ACME DINER"),
        (date(2026, 5, 22), -20000, "ACME DINER"),
        (date(2026, 2, 5), -1599, "QUUX STREAMING"),
        (date(2026, 3, 5), -1599, "QUUX STREAMING"),
        (date(2026, 4, 5), -1599, "QUUX STREAMING"),
        (date(2026, 5, 5), -1799, "QUUX STREAMING"),
        (date(2026, 3, 12), -999, "BAZ VIDEO"),
        (date(2026, 4, 12), -999, "BAZ VIDEO"),
        (date(2026, 5, 12), -999, "BAZ VIDEO"),
        (date(2026, 5, 28), -2345, "PURCHASE INTEREST CHARGE"),
        (date(2025, 1, 8), -9900, "QUUX CLOUD"),
        (date(2026, 1, 8), -9900, "QUUX CLOUD"),
    ] + [(date(2026, 5, day), -500, "ACME COFFEE") for day in (2, 3, 6, 9, 10, 13, 16, 17)]
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Example Card Co", "credit_card")
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
        for pattern, category in (
            ("ACME DINER", "Dining"),
            ("QUUX STREAMING", "Subscriptions & Digital"),
            ("BAZ VIDEO", "Subscriptions & Digital"),
            ("QUUX CLOUD", "Subscriptions & Digital"),
            ("ACME COFFEE", "Coffee & Dessert"),
        ):
            create_rule(session, pattern, category)
        categorize(session)
    engine.dispose()
    return client


def table(found: Page, heading: list[str]) -> list[list[str]]:
    """The rows of the table that starts with this heading row."""
    start = found.rows.index(heading)
    end = start + 1
    while end < len(found.rows) and len(found.rows[end]) == len(heading):
        if found.rows[end] in (FINDINGS, RECURRING, MERCHANTS):
            break
        end += 1
    return found.rows[start:end]


def test_the_menu_has_insights(home: TestClient) -> None:
    html = home.get("/insights?month=2026-05").text
    assert 'href="/insights" aria-current="page">Insights</a>' in html
    assert html.count('aria-current="page"') == 1
    assert 'href="/insights">Insights</a>' in home.get("/reports?month=2026-05").text
    assert "<script" not in html


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get("/insights")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_a_month(home: TestClient) -> None:
    response = home.get("/insights?month=2026-05")
    assert response.status_code == 200
    found = Page(response.text)
    assert table(found, FINDINGS) == [
        FINDINGS,
        ["high", "interest", "", "$23.45", "Interest charged: $23.45."],
        [
            "medium",
            "spike",
            "Dining",
            "$140.00",
            "Dining: $200.00 this month, against $60.00 a month before.",
        ],
        [
            "medium",
            "price_increase",
            "QUUX STREAMING",
            "$2.00",
            "QUUX STREAMING went from $15.99 to $17.99.",
        ],
        [
            "low",
            "frequent_small",
            "ACME COFFEE",
            "$20.00",
            "ACME COFFEE: 8 visits averaging $5.00.",
        ],
        [
            "low",
            "subscription_overlap",
            "Subscriptions & Digital",
            "$8.25",
            "Subscriptions & Digital: QUUX STREAMING ($17.99), BAZ VIDEO ($9.99),"
            " QUUX CLOUD ($8.25).",
        ],
    ]
    assert table(found, RECURRING) == [
        RECURRING,
        ["QUUX STREAMING", "month", "$17.99", "$17.99", "4", "2026-05-05", "2026-06-05"],
        ["BAZ VIDEO", "month", "$9.99", "$9.99", "3", "2026-05-12", "2026-06-12"],
        ["QUUX CLOUD", "year", "$99.00", "$8.25", "2", "2026-01-08", "2027-01-08"],
    ]
    assert table(found, MERCHANTS) == [
        MERCHANTS,
        ["ACME DINER", "1", "$200.00", "$200.00", "$60.00", "+$140.00", "0"],
        ["ACME COFFEE", "8", "$40.00", "$5.00", "$0.00", "+$40.00", "6"],
        ["PURCHASE INTEREST CHARGE", "1", "$23.45", "$23.45", "$0.00", "+$23.45", "0"],
        ["QUUX STREAMING", "1", "$17.99", "$17.99", "$15.99", "+$2.00", "0"],
        ["BAZ VIDEO", "1", "$9.99", "$9.99", "$6.66", "+$3.33", "0"],
    ]
    assert texts(found, "summary") == [
        "Insights for 2026-05.",
        "Findings: 5. Could save up to $193.70 a month.",
        "Recurring: 3 active, $36.23 a month.",
    ]
    assert found.find("/insights")["inputs"]["month"] == ("month", "2026-05")


def test_a_yearly_plan_charged_before_the_window_still_overlaps(home: TestClient) -> None:
    found = page(home, "/insights?month=2026-04")
    assert table(found, FINDINGS)[1:] == [
        [
            "low",
            "subscription_overlap",
            "Subscriptions & Digital",
            "$8.25",
            "Subscriptions & Digital: QUUX STREAMING ($15.99), QUUX CLOUD ($8.25).",
        ]
    ]


def test_a_month_with_nothing(home: TestClient) -> None:
    found = page(home, "/insights?month=2024-05")
    assert texts(found, "empty") == ["No findings.", "No recurring charges.", "No spending."]
    assert texts(found, "summary") == [
        "Insights for 2024-05.",
        "Recurring: 0 active, $0.00 a month.",
    ]


def test_no_month_means_this_month(home: TestClient) -> None:
    response = home.get("/insights")
    assert response.status_code == 200
    assert texts(Page(response.text), "summary")[0].startswith("Insights for ")


@pytest.mark.parametrize("month", ["2026-13", "May", "2026-5"])
def test_a_month_that_is_not_one(home: TestClient, month: str) -> None:
    response = home.get(f"/insights?month={month}")
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", "month must be a year and month, like 2026-05") in found.paragraphs
    assert texts(found, "summary") == []
    assert found.find("/insights")["inputs"]["month"] == ("month", month)
```

## Tests to write

None beyond the given file, unless your code has a branch it does not reach (the coverage command shows it); add such tests to `tests/integration/test_web_insights_more.py`, importing from `tests/support.py`, and list that file in your report.

## Rules for this phase

- **No JavaScript**; the page keeps the security headers. It has no form token because it only reads.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/integration/test_web_insights.py`, 9 tests;
- also `.venv/bin/python -m pytest tests/e2e/test_cli_insights.py tests/unit/test_insights.py --no-cov`: `21 passed` (Phase 13b unchanged);
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.views --cov=finances.analysis --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|format_cents\(|spikes\(|merchant_stats\(" -- src/finances/web` and `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 13c: insights on the web (YYYY-MM-DD)`.
