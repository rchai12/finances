# Phase 30d: export from the web

## Goal

30c's three CSVs reach the browser, which finishes Phase 30, with the owner's choices (2026-10-24): a download, a link beside what it exports, and the Transactions page's download holding exactly what its filters choose. After this phase:

- the Year page, the Reports spending card, and the Transactions page each have a Download link;
- each link is a GET that answers the CSV as a download named as the terminal names its file, byte for byte the same file `fin export` writes; it writes nothing and stores nothing;
- the Transactions page's download holds every transaction (and part) its filters match, whatever the page's row limit.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-30c-csv-export.md`
- `src/finances/analysis/export.py` (`transactions_for_export`), `src/finances/views/export.py`, `src/finances/cli/export.py` (the file names)
- `src/finances/web/routes/transactions.py` (`_FILTER_FIELDS`, `_search_query`, `_filter_query`), `src/finances/web/routes/reports.py` (`_spending_range`, `YEAR_REFUSED`, the `/year` route's reading of the year), `src/finances/web/app.py` (the areas), `src/finances/web/templates/error.html`

## Starting state

N is `3828` when Phase 30c is the last phase built. The newest migration is `0021`; this phase adds none. `web/routes/transactions.py` is 366 lines, so the downloads go in a new `export` router that imports the pages' own readers. The given templates were checked against every earlier integration and end-to-end test: all 2162 pass unchanged.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/templates/year.html`, `reports.html`, `transactions.html` | the given diff (R5) |
| `src/finances/analysis/export.py` | `export_lines`; `transactions_for_export` through it (R1) |
| `src/finances/web/routes/export.py` (new), `src/finances/web/app.py` | the `export` router: three GET routes (R2 to R4) |
| `tests/unit/test_web_split.py` | the given diff (R7) |
| `tests/integration/test_web_export.py` | new: given |
| `tests/integration/test_web_export_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Writing a file to the export folder from the web; any other report; a choice of columns or format.
- The filters in `fin export transactions` (the terminal keeps its date range).
- Any change to the CSVs themselves.

## Dependencies

None new. No migration.

## Design

```python
# src/finances/analysis/export.py
def export_lines(session: Session, query: TransactionQuery) -> list[ExportLine]: ...
# every transaction and part the query matches (query.limit is not used), in 30c's order
```

The `export` router (`src/finances/web/routes/export.py`, added to `create_app`'s areas). Each route checks the schema as the pages do, and answers a refusal (a `ValueError`) with the `error` page, 400, the message, and `back` the page the link came from:

| Route | Reads | Answers |
|---|---|---|
| `GET /export/transactions` | the Transactions page's filter fields, through `_search_query` (its `limit` checked as the page checks it, then not used) | `transactions_csv(export_lines(...))`, named `transactions-<from>-to-<to>.csv` when both dates are given, else `transactions.csv`; `back` `/transactions` |
| `GET /export/year` | `year` as `/year` reads it (blank: `web_app._today().year`; ASCII digits only, else `YEAR_REFUSED`) | `year_csv(year_report(...))`, named `year-<year>.csv`; `back` `/year` |
| `GET /export/spending` | `month`, `from`, `to`, `by` through `_spending_range` and `spending_report`, as the Reports page reads them (`by` blank is `category`) | `spending_csv(...)`, named `spending-by-<by>-<from>-to-<to>.csv`; `back` `/reports` |

Each CSV answer is `Response(text, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="<name>"'})`.

## Requirements

- **R1.** `export_lines` as designed; `transactions_for_export(session, start, end)` keeps its refusal and returns `export_lines` of a query with that range, so `fin export transactions` writes exactly as before.
- **R2.** `GET /export/transactions` as designed.
- **R3.** `GET /export/year` as designed.
- **R4.** `GET /export/spending` as designed.
- **R5.** Apply the given template diff exactly: the Year page links to `/export/year?year=<the year shown>`, the Reports spending card to `/export/spending?from=...&to=...&by=...` of the report shown, and the Transactions page to `/export/transactions` with the page's filter query.
- **R6.** The downloads write no file and change nothing; a POST to any of them answers 405.
- **R7.** Apply the given diff to `tests/unit/test_web_split.py`. No other earlier test changes.

## Given template diff

Applied to `src/finances/web/templates/` (do not change).

```text
diff --git a/src/finances/web/templates/reports.html b/src/finances/web/templates/reports.html
index 5b5a8a4..76fd7ba 100644
--- a/src/finances/web/templates/reports.html
+++ b/src/finances/web/templates/reports.html
@@ -64,6 +64,7 @@
 <p class="year-link"><a href="/year">The year's totals</a></p>
 {% if spending %}
 <p class="summary">{{ spending.heading }}</p>
+<p class="download"><a href="/export/spending?from={{ spending.start }}&amp;to={{ spending.end }}&amp;by={{ spending.by }}">Download CSV</a></p>
 {% if spending.rows %}
 <table>
 <thead><tr><th>{{ spending.by|capitalize }}</th><th class="amount">Spent</th><th class="amount">Refunds</th><th class="amount">Net</th><th class="amount">Count</th></tr></thead>
diff --git a/src/finances/web/templates/transactions.html b/src/finances/web/templates/transactions.html
index ee5bd9e..75baac0 100644
--- a/src/finances/web/templates/transactions.html
+++ b/src/finances/web/templates/transactions.html
@@ -46,6 +46,7 @@
   {% endfor %}<button type="submit">Show</button>
 </form>
 <p class="quick"><a href="/transactions?kind=refund">Only refunds</a></p>
+<p class="download"><a href="/export/transactions{% if back %}?{{ back }}{% endif %}">Download these as CSV</a></p>
 {% if kept %}<p class="hint">Also filtered by: {% for key in kept %}{{ key }} {{ chosen[key] }}{% if not loop.last %}, {% endif %}{% endfor %}. <a href="/transactions">Clear all filters</a></p>{% endif %}
 {% if rows %}
 <p class="selection"><a href="/transactions?{{ select_all_query }}">Select all shown</a> <a href="/transactions?{{ back }}">Clear the selection</a></p>
diff --git a/src/finances/web/templates/year.html b/src/finances/web/templates/year.html
index 29fc9a0..e260dd4 100644
--- a/src/finances/web/templates/year.html
+++ b/src/finances/web/templates/year.html
@@ -10,6 +10,7 @@
 {% if report %}
 <p class="years">{% if report.previous %}<a href="/year?year={{ report.previous }}">{{ report.previous }}</a>{% endif %}{% if report.previous and report.next %} · {% endif %}{% if report.next %}<a href="/year?year={{ report.next }}">{{ report.next }}</a>{% endif %}</p>
 <p class="summary">{{ report.heading }}</p>
+<p class="download"><a href="/export/year?year={{ chosen }}">Download CSV</a></p>
 {% for title, by, rows, empty in report.sections %}
 <section class="card">
 <h2>{{ title }}</h2>
```

## Given diff to earlier tests

```text
diff --git a/tests/unit/test_web_split.py b/tests/unit/test_web_split.py
index 40951f6..a71b8c7 100644
--- a/tests/unit/test_web_split.py
+++ b/tests/unit/test_web_split.py
@@ -16,6 +16,7 @@ AREAS = [
     "backups",
     "budgets",
     "categories",
+    "export",
     "history",
     "home",
     "people",
@@ -72,6 +73,9 @@ ROUTES = {
     ("POST", "/categories/rules/{rule_id}"),
     ("GET", "/reports"),
     ("GET", "/year"),
+    ("GET", "/export/transactions"),
+    ("GET", "/export/year"),
+    ("GET", "/export/spending"),
     ("GET", "/insights"),
     ("GET", "/ahead"),
     ("GET", "/transfers"),
```

## Given tests

10 tests in one file. Do not change them. One (`test_each_page_links_to_its_download`) is a guard on the given templates.

`tests/integration/test_web_export.py`

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_tags,
    create_account,
    set_category_by_hand,
    set_note,
    set_split,
)
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, texts

HEADER = (
    "ID,Posted,Date,Account,Description,Merchant,Category,Group,Kind,Amount,Card,Person,Part,"
    "Tags,Note\r\n"
)
TRANSACTIONS = (
    HEADER
    + "1,2026-05-01,2026-05-01,Test Card,ACME COFFEE,ACME COFFEE,Coffee & Dessert,Food,spending,"
    "-12.34,,,,work,client lunch\r\n"
    "2,2026-05-03,2026-05-03,Test Card,FOOBAR GROCERY,FOOBAR GROCERY,Groceries,Food,spending,"
    "-12.00,,,1,,\r\n"
    "2,2026-05-03,2026-05-03,Test Card,FOOBAR GROCERY,FOOBAR GROCERY,Home & Garden,Home,"
    "spending,-8.00,,,2,,\r\n"
    "3,2026-05-05,2026-05-05,Test Card,ACME COFFEE,ACME COFFEE,Coffee & Dessert,Food,spending,"
    "5.00,,,,,\r\n"
)
YEAR = (
    "Section,Label,Spent,Refunds,Net,Count\r\n"
    "group,Food,24.34,5.00,19.34,3\r\n"
    "group,Home,8.00,0.00,8.00,1\r\n"
    "category,Groceries,12.00,0.00,12.00,1\r\n"
    "category,Home & Garden,8.00,0.00,8.00,1\r\n"
    "category,Coffee & Dessert,12.34,5.00,7.34,2\r\n"
    "tax,Gifts & Donations,0.00,0.00,0.00,0\r\n"
    "tax,Medical,0.00,0.00,0.00,0\r\n"
    "tax,Taxes,0.00,0.00,0.00,0\r\n"
)
SPENDING = (
    "Category,Spent,Refunds,Net,Count\r\n"
    "Groceries,12.00,0.00,12.00,1\r\n"
    "Home & Garden,8.00,0.00,8.00,1\r\n"
    "Coffee & Dessert,12.34,5.00,7.34,2\r\n"
)


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """The card of tests/e2e/test_cli_export.py: ACME COFFEE -$12.34 (1) tagged work with a
    note; FOOBAR GROCERY -$20.00 (2) split into Groceries -$12.00 and Home & Garden -$8.00; a
    refund of $5.00 (3); and -$9.99 on 2025-12-31 (4)."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [
            (date(2026, 5, 1), -1234, "ACME COFFEE"),
            (date(2026, 5, 3), -2000, "FOOBAR GROCERY"),
            (date(2026, 5, 5), 500, "ACME COFFEE"),
            (date(2025, 12, 31), -999, "ACME COFFEE"),
        ]
        for number, (day, cents, description) in enumerate(rows, start=1):
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
        for number in (1, 3, 4):
            set_category_by_hand(session, number, "Coffee & Dessert")
        set_split(session, 2, [(-1200, "Groceries"), (-800, "Home & Garden")])
        add_tags(session, [1], "work")
        set_note(session, 1, "client lunch")
    engine.dispose()
    return client


def download(client: TestClient, path: str) -> tuple[int, str, str, str]:
    response = client.get(path)
    return (
        response.status_code,
        response.headers.get("content-type", ""),
        response.headers.get("content-disposition", ""),
        response.content.decode("utf-8"),
    )


def test_the_year(home: TestClient) -> None:
    assert download(home, "/export/year?year=2026") == (
        200,
        "text/csv; charset=utf-8",
        'attachment; filename="year-2026.csv"',
        YEAR,
    )


def test_spending(home: TestClient) -> None:
    assert download(home, "/export/spending?month=2026-05") == (
        200,
        "text/csv; charset=utf-8",
        'attachment; filename="spending-by-category-2026-05-01-to-2026-05-31.csv"',
        SPENDING,
    )


def test_transactions_by_dates(home: TestClient) -> None:
    assert download(home, "/export/transactions?from=2026-01-01&to=2026-12-31") == (
        200,
        "text/csv; charset=utf-8",
        'attachment; filename="transactions-2026-01-01-to-2026-12-31.csv"',
        TRANSACTIONS,
    )


def test_transactions_as_the_filters_choose(home: TestClient) -> None:
    status, _, name, body = download(home, "/export/transactions?category=Groceries")
    assert (status, name) == (200, 'attachment; filename="transactions.csv"')
    assert body == (
        HEADER + "2,2026-05-03,2026-05-03,Test Card,FOOBAR GROCERY,FOOBAR GROCERY,Groceries,"
        "Food,spending,-12.00,,,1,,\r\n"
    )
    _, _, _, every = download(home, "/export/transactions?limit=1")
    assert every.count("\r\n") == 6
    assert every.splitlines()[1].startswith("4,2025-12-31,")


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("/export/year?year=abc", "year must be from 1 to 9999"),
        ("/export/year?year=0", "year must be from 1 to 9999"),
        (
            "/export/spending?month=2026-05&by=colour",
            "by must be one of: category, group, merchant, person, account, bank, card",
        ),
        ("/export/transactions?account=Nope", "account not found"),
    ],
)
def test_a_download_that_is_refused(home: TestClient, path: str, message: str) -> None:
    response = home.get(path)
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == [message]


def test_each_page_links_to_its_download(home: TestClient) -> None:
    assert "/export/year?year=2026" in page(home, "/year?year=2026").links
    assert "/export/spending?from=2026-05-01&to=2026-05-31&by=category" in (
        page(home, "/reports?month=2026-05").links
    )
    assert "/export/transactions?category=Groceries" in (
        page(home, "/transactions?category=Groceries").links
    )
    assert "/export/transactions" in page(home, "/transactions").links


def test_a_download_writes_nothing(home: TestClient, tmp_settings: Settings) -> None:
    home.get("/export/year?year=2026")
    assert not (tmp_settings.data_dir / "exports").exists()
    assert home.post("/export/year").status_code == 405
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_web_export_more.py`:

- `/export/year` with no year exports today's year, `finances.web.app._today` replaced after the app is created;
- `/export/spending` with no options exports this month by category;
- `/export/transactions?tag=work` holds transaction 1 only; `?from=2026-05-02&to=2026-05-31&kind=spending` is named `transactions-2026-05-02-to-2026-05-31.csv`;
- `/export/transactions?limit=x` answers 400 with the page's limit message;
- the downloads on a database that is not migrated answer as the pages do;
- `fin export transactions` writes the same bytes as before (R1), compared with 30c's given file.

## Rules for this phase

- The downloads are reads: no file, no row, no audit entry; they come from the local site only.
- The routes parse fields with the pages' own readers, call one gathering function and one CSV function, and answer; no CSV text is built in a route.
- Messages are the readers' and the reports' own, constant and echoing nothing typed.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file above, 10 tests; at least N + 10 passed in all;
- `git diff --stat HEAD -- tests` lists only the file of the given diff;
- `git grep -n "write_csv\|write_text\|open(" -- src/finances/web/routes/export.py` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.analysis.export --cov=finances.web.routes.export --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 30d: export from the web (YYYY-MM-DD)`.
