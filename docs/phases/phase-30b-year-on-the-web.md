# Phase 30b: the year and the tax flag on the web

## Goal

30a's year and tax flag reach the browser, with the owner's choices (2026-10-24): a Year page of its own, linked from Reports; a year box with the years before and after; each line drilling down to its transactions; the flag managed in a card on Categories. After this phase:

- `/year` shows a calendar year (this year by default) by group, by category, and the tax-relevant categories, each line a link to the Transactions page filtered by it and the year's dates, so the rows add up to the line (split parts included, as 28e and 28g show them), and the year's summary;
- Reports links to it;
- Categories has a Tax-relevant card: the flagged categories, each with a Remove button, and a form to mark another.

CSV export is 30c (terminal) and 30d (web).

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-30a-tax-and-the-year.md`
- `src/finances/analysis/yearend.py`, `src/finances/views/yearend.py`, `src/finances/views/spending.py` (`line_rows`, `summary_lines`), `src/finances/db/repositories/categories.py` (`set_tax_relevant`)
- `src/finances/web/routes/reports.py` (the Reports page, `web_app._today()`), `src/finances/web/routes/categories.py` (`_categories_page`, the aliases routes of 28b), `src/finances/web/helpers.py` (`_WHOLE`), `src/finances/web/render.py` (`NOTICES`), `src/finances/web/templates/reports.html` (the spending drill-down links), `categories.html`

## Starting state

N is `3782` when Phase 30a is the last phase built. The newest migration is `0021`; this phase adds none. Two earlier Categories tests read rows by position (the aliases table's rows last; the rows after the category tree counted), so the Tax-relevant card lists its categories in a `<ul>`, not a table. The given templates were checked against every earlier integration and end-to-end test with `tax_categories` filled with the seeded three: all 2127 pass unchanged.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/templates/year.html` (new), `reports.html`, `categories.html` | the given diff (R1, R5, R6) |
| `src/finances/views/yearend.py` | `year_page` (R2) |
| `src/finances/web/routes/reports.py` | `GET /year` (R3, R4) |
| `src/finances/web/routes/categories.py` | `tax_categories` on the page, `POST /categories/tax` (R6, R7) |
| `src/finances/web/render.py` | two notices (R7) |
| `tests/unit/test_web_split.py` | the given diff (R9) |
| `tests/integration/test_web_year.py` | new: given |
| `tests/integration/test_web_year_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- A Year link in the menu; a chart of the year; comparing years; a Tax column in the Categories table.
- More than 1000 rows in a drill-down (the Transactions page's own limit).
- Any change to 30a's report, `fin year`, or `fin categories tax`.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/views/yearend.py
def year_page(report: YearReport) -> dict[str, object]: ...
# {"heading": year_heading(report), "start": "2026-01-01", "end": "2026-12-31",
#  "previous": 2025 or None (when the year is 1), "next": 2027 or None (when it is 9999),
#  "sections": [("By group", "group", line_rows(groups), "No spending."),
#               ("By category", "category", line_rows(categories), "No spending."),
#               ("Tax-relevant", "category", line_rows(tax), "No tax-relevant categories.")],
#  "summary": summary_lines(report.summary)}
```

| Route | Fields | Does | Answers |
|---|---|---|---|
| `GET /year` | `year` (query, optional) | blank: `web_app._today().year`; ASCII digits only (`_WHOLE`), else refused; then `year_report` | 200 with `report` `year_page(...)` and `chosen` the year's text; or 400 with `error` `year must be from 1 to 9999`, `report` None, `chosen` the typed text |
| `POST /categories/tax` | `csrf`, `category`, `tax` | `refused(request, csrf)`; `tax` is `on` or `off`, else `tax must be on or off`; then `set_tax_relevant(session, category, tax == "on")` | 303 to `/categories?notice=tax-set` (on) or `/categories?notice=tax-cleared` (off); a `ValueError` gives the Categories page, 400, the error |

`_categories_page` gains `tax_categories`: the names of the tax-relevant categories, by name, on every render.

## Requirements

### The Year page

- **R1.** Apply the given template diff exactly. `GET /year` checks the schema as the other pages do and renders `year`.
- **R2.** `year_page` as designed.
- **R3.** `GET /year` reads the year as designed: today's year through `web_app._today()` (looked up when the request runs) when blank; anything but one or more ASCII digits, or a year `year_report` refuses, answers 400 with the one message `year must be from 1 to 9999`.
- **R4.** Each line of the page links to `/transactions` with the year's `from` and `to`, the section's `group` or `category`, `kind=spending`, and `limit=1000` (the given template), so following it lists the transactions and parts of that line.
- **R5.** The Reports page links to `/year` (the given template).

### The tax flag

- **R6.** `_categories_page` supplies `tax_categories` as designed, so the given card lists them, each with a Remove form.
- **R7.** `POST /categories/tax` as designed. `NOTICES` gains `"tax-set": "Marked tax-relevant."` and `"tax-cleared": "No longer tax-relevant."`.
- **R8.** GET on `/categories/tax` answers 405.
- **R9.** Apply the given diff to `tests/unit/test_web_split.py`. No other earlier test changes.

## Given template diff

Applied to `src/finances/web/templates/` (do not change).

```text
diff --git a/src/finances/web/templates/categories.html b/src/finances/web/templates/categories.html
index 96717ea..a6f8ea2 100644
--- a/src/finances/web/templates/categories.html
+++ b/src/finances/web/templates/categories.html
@@ -136,4 +136,23 @@
   <button type="submit">Merge</button>
 </form>
 </section>
+<section class="card">
+<h2>Tax-relevant categories</h2>
+<p class="hint">These are pulled out on the Year page for taxes.</p>
+{% if tax_categories %}
+<ul class="tax-list">
+{% for name in tax_categories %}<li>{{ name }} <form method="post" action="/categories/tax" class="inline"><input type="hidden" name="csrf" value="{{ csrf }}"><input type="hidden" name="category" value="{{ name }}"><input type="hidden" name="tax" value="off"><button type="submit">Remove</button></form></li>
+{% endfor %}</ul>
+{% else %}
+<p class="empty">No tax-relevant categories.</p>
+{% endif %}
+<form method="post" action="/categories/tax" class="fields">
+  <input type="hidden" name="csrf" value="{{ csrf }}">
+  <input type="hidden" name="tax" value="on">
+  <label>Category
+    {% with selected = "" %}{% include "category_select.html" %}{% endwith %}
+  </label>
+  <button type="submit">Mark tax-relevant</button>
+</form>
+</section>
 {% endblock %}
diff --git a/src/finances/web/templates/reports.html b/src/finances/web/templates/reports.html
index 100474f..5b5a8a4 100644
--- a/src/finances/web/templates/reports.html
+++ b/src/finances/web/templates/reports.html
@@ -61,6 +61,7 @@
   </label>
   <button type="submit">Show</button>
 </form>
+<p class="year-link"><a href="/year">The year's totals</a></p>
 {% if spending %}
 <p class="summary">{{ spending.heading }}</p>
 {% if spending.rows %}
diff --git a/src/finances/web/templates/year.html b/src/finances/web/templates/year.html
new file mode 100644
index 0000000..29fc9a0
--- /dev/null
+++ b/src/finances/web/templates/year.html
@@ -0,0 +1,34 @@
+{% extends "layout.html" %}
+{% block title %}Year · Finances{% endblock %}
+{% block content %}
+<h1>Year</h1>
+{% include "messages.html" %}
+<form method="get" action="/year" class="fields">
+  <label>Year <input name="year" inputmode="numeric" maxlength="4" value="{{ chosen }}"></label>
+  <button type="submit">Show</button>
+</form>
+{% if report %}
+<p class="years">{% if report.previous %}<a href="/year?year={{ report.previous }}">{{ report.previous }}</a>{% endif %}{% if report.previous and report.next %} · {% endif %}{% if report.next %}<a href="/year?year={{ report.next }}">{{ report.next }}</a>{% endif %}</p>
+<p class="summary">{{ report.heading }}</p>
+{% for title, by, rows, empty in report.sections %}
+<section class="card">
+<h2>{{ title }}</h2>
+{% if rows %}
+<table>
+<thead><tr><th>{{ by|capitalize }}</th><th class="amount">Spent</th><th class="amount">Refunds</th><th class="amount">Net</th><th class="amount">Count</th></tr></thead>
+<tbody>
+{% for row in rows %}<tr><td><a href="/transactions?from={{ report.start }}&amp;to={{ report.end }}&amp;{{ by }}={{ row.label|urlencode }}&amp;kind=spending&amp;limit=1000">{{ row.label }}</a></td><td class="{{ row.spent|amount_class }}">{{ row.spent }}</td><td class="{{ row.refunds|amount_class }}">{{ row.refunds }}</td><td class="{{ row.net|amount_class }}">{{ row.net }}</td><td class="{{ row.count|amount_class }}">{{ row.count }}</td></tr>
+{% endfor %}</tbody>
+</table>
+{% else %}
+<p class="empty">{{ empty }}</p>
+{% endif %}
+</section>
+{% endfor %}
+<section class="card">
+<h2>Summary</h2>
+{% for line in report.summary %}<p class="summary">{{ line }}</p>
+{% endfor %}
+</section>
+{% endif %}
+{% endblock %}
```

## Given diff to earlier tests

```text
diff --git a/tests/unit/test_web_split.py b/tests/unit/test_web_split.py
index 56e9277..40951f6 100644
--- a/tests/unit/test_web_split.py
+++ b/tests/unit/test_web_split.py
@@ -65,11 +65,13 @@ ROUTES = {
     ("POST", "/categories/rules/delete"),
     ("POST", "/categories/aliases/add"),
     ("POST", "/categories/aliases/delete"),
+    ("POST", "/categories/tax"),
     ("POST", "/categories/rename"),
     ("POST", "/categories/delete"),
     ("GET", "/categories/rules/{rule_id}"),
     ("POST", "/categories/rules/{rule_id}"),
     ("GET", "/reports"),
+    ("GET", "/year"),
     ("GET", "/insights"),
     ("GET", "/ahead"),
     ("GET", "/transfers"),
```

## Given tests

14 tests in one file. Do not change them. Two (`test_reports_links_to_the_year`, and `test_the_tax_card` once R6 is in) are guards on the given templates.

`tests/integration/test_web_year.py`

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, set_category_by_hand, set_split
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts

HEADINGS = ["Spent", "Refunds", "Net", "Count"]
ROWS = [
    ["Group", *HEADINGS],
    ["Health", "$130.00", "$20.00", "$110.00", "3"],
    ["Personal", "$51.00", "$0.00", "$51.00", "2"],
    ["Food", "$20.00", "$0.00", "$20.00", "1"],
    ["Category", *HEADINGS],
    ["Medical", "$130.00", "$20.00", "$110.00", "3"],
    ["Gifts & Donations", "$51.00", "$0.00", "$51.00", "2"],
    ["Groceries", "$20.00", "$0.00", "$20.00", "1"],
    ["Category", *HEADINGS],
    ["Gifts & Donations", "$51.00", "$0.00", "$51.00", "2"],
    ["Medical", "$130.00", "$20.00", "$110.00", "3"],
    ["Taxes", "$0.00", "$0.00", "$0.00", "0"],
]
SUMMARY = [
    "Year 2026, from 2026-01-01 to 2026-12-31.",
    "Spent: $201.00. Refunds: $20.00. Net: $181.00. Income: $3,000.00.",
    "Transfers left out: 0.",
]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: date(2024, 8, 1))
    return found


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """The year of tests/e2e/test_cli_year.py: Medical, a refund, a split, Gifts & Donations
    on both edges' sides, and a paycheck."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [
            (date(2026, 2, 10), -12000, "ACME CLINIC", "Medical"),
            (date(2026, 3, 5), -5000, "BAZ CHARITY", "Gifts & Donations"),
            (date(2026, 4, 1), -3000, "FOOBAR GROCERY", None),
            (date(2026, 5, 1), 2000, "ACME CLINIC", "Medical"),
            (date(2026, 6, 1), 300000, "PAYCHECK EXAMPLE CORP", "Paycheck"),
            (date(2025, 12, 31), -9999, "ACME CLINIC", "Medical"),
            (date(2026, 12, 31), -100, "BAZ CHARITY", "Gifts & Donations"),
        ]
        for number, (day, cents, description, _) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for number, (_, _, _, category) in enumerate(rows, start=1):
            if category is not None:
                set_category_by_hand(session, number, category)
        set_split(session, 3, [(-2000, "Groceries"), (-1000, "Medical")])
    engine.dispose()
    client.get("/categories")
    return client


def test_the_year_page(home: TestClient) -> None:
    response = home.get("/year?year=2026")
    assert response.status_code == 200
    found = Page(response.text)
    assert texts(found, "summary") == SUMMARY
    assert found.rows == ROWS
    assert texts(found, "years") == ["2025 · 2027"]
    assert "/transactions?from=2026-01-01&to=2026-12-31&group=Health&kind=spending&limit=1000" in (
        found.links
    )
    assert (
        "/transactions?from=2026-01-01&to=2026-12-31&category=Gifts%20%26%20Donations"
        "&kind=spending&limit=1000"
    ) in found.links


def test_this_year_by_default(home: TestClient) -> None:
    found = page(home, "/year")
    assert texts(found, "summary")[0] == "Year 2024, from 2024-01-01 to 2024-12-31."
    assert found.find("/year")["inputs"]["year"] == ("text", "2024")
    assert texts(found, "empty") == ["No spending.", "No spending."]


@pytest.mark.parametrize(("year", "years"), [("1", "2"), ("9999", "9998")])
def test_the_first_and_last_years(home: TestClient, year: str, years: str) -> None:
    assert texts(page(home, f"/year?year={year}"), "years") == [years]


@pytest.mark.parametrize("year", ["abc", "0", "10000", "２０２６"])
def test_a_year_that_is_refused(home: TestClient, year: str) -> None:
    response = home.get(f"/year?year={year}")
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == ["year must be from 1 to 9999"]
    assert (found.rows, texts(found, "summary")) == ([], [])


def test_a_line_drills_down_to_its_transactions(home: TestClient) -> None:
    link = next(href for href in page(home, "/year?year=2026").links if "category=Medical" in href)
    rows = page(home, link).rows
    assert [row[4] for row in rows[1:]] == ["$20.00", "-$10.00", "-$120.00"]


def test_reports_links_to_the_year(home: TestClient) -> None:
    assert "/year" in page(home, "/reports").links


def tax_forms(found: Page) -> list[str]:
    return [
        form["inputs"]["category"][1]
        for form in found.all("/categories/tax")
        if form["inputs"]["tax"] == ("hidden", "off")
    ]


def test_the_tax_card(home: TestClient) -> None:
    assert tax_forms(page(home, "/categories")) == ["Gifts & Donations", "Medical", "Taxes"]


def test_marking_on_the_page(home: TestClient) -> None:
    on = post(home, "/categories/tax", category="groceries", tax="on")
    assert (on.status_code, on.headers["location"]) == (303, "/categories?notice=tax-set")
    found = page(home, "/categories?notice=tax-set")
    assert texts(found, "notice") == ["Marked tax-relevant."]
    assert tax_forms(found) == ["Gifts & Donations", "Groceries", "Medical", "Taxes"]
    off = post(home, "/categories/tax", category="Medical", tax="off")
    assert (off.status_code, off.headers["location"]) == (303, "/categories?notice=tax-cleared")
    found = page(home, "/categories?notice=tax-cleared")
    assert texts(found, "notice") == ["No longer tax-relevant."]
    assert tax_forms(found) == ["Gifts & Donations", "Groceries", "Taxes"]


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        (
            {"category": "Health", "tax": "on"},
            "a group cannot be tax-relevant; mark its categories",
        ),
        ({"category": "Medical", "tax": "maybe"}, "tax must be on or off"),
    ],
)
def test_marking_refused(home: TestClient, fields: dict, message: str) -> None:
    response = post(home, "/categories/tax", **fields)
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == [message]
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_web_year_more.py`:

- GET on `/categories/tax` answers 405; `/year` on a database that is not migrated answers as the other pages do;
- a year with every tax flag turned off shows `No tax-relevant categories.`;
- a refused tax form keeps the Categories page whole on the 400 (its tables and the Tax-relevant card);
- marking a category already tax-relevant redirects with `tax-set` and records nothing new in the audit trail (30a's rule);
- a form posted without a valid form token is refused, as on the other forms.

## Rules for this phase

- The routes parse fields, call one function, and render or redirect; the page's words come from `views/yearend.py`, `NOTICES`, or the templates.
- A year is read as ASCII digits only: `２０２６` is refused, not read as 2026.
- Earlier tests stay unchanged except the given diff; keep every module under `src/finances/web/routes/` under 400 lines.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file above, 14 tests; at least N + 14 passed in all;
- `git diff --stat HEAD -- tests` lists only the file of the given diff;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.views.yearend --cov=finances.web.routes.reports --cov=finances.web.routes.categories --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 30b: the year and the tax flag on the web (YYYY-MM-DD)`.
