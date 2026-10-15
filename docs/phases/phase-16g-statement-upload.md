# Phase 16g: statement upload

## Goal

The household imports statements from the browser and sees which periods are missing. After this phase:

- the menu has **Statements**: a form to **upload a PDF statement** (the account found from the statement, or chosen; **Check only, write nothing** for a dry run), the result of the upload, the **statements** held, and the **gaps**: days between two statements of the same account that neither covers;
- an upload goes through the same import as `fin import statement`, and the rules and transfer pairing run afterwards, as they do in the terminal;
- the file is read in memory and never kept or sent anywhere; only its name (without any folder) and its fingerprint are stored, as today.

First, a fix from Phase 16j's review: the bulk form on the Transactions page broke when more than 996 rows were chosen, because the web framework refuses a form of more than 1000 fields before the route runs.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/ingest/service.py` (`import_statement`, `StatementImportResult`, `ImportStatus`), `src/finances/cli/importing.py` (`_report_statement`: the words for each status), `src/finances/cli/listing.py` (`_statement_cells`)
- `src/finances/db/repositories.py`: `list_statements`, `statement_periods`; `src/finances/domain/periods.py`
- `src/finances/web/app.py`: `POST /transactions/bulk`, `refused`, `categorize` after Sync now
- `tests/conftest.py`: `fake_bank`, `fake_statement_pdf`, `make_pdf`; `tests/support.py`

## Starting state

N is `2728` when Phase 16j is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/app.py` | the bulk route's form (R1); the Statements routes (R6 to R8) |
| `src/finances/domain/periods.py` | new: `statement_gaps` (R2) |
| `src/finances/analysis/statements.py` | new (R3) |
| `src/finances/views/statements.py` | new (R4, R5) |
| `src/finances/web/templates/layout.html` | replaced: given |
| `src/finances/web/templates/statements.html` | new: given |
| `tests/unit/test_statement_gaps.py`, `tests/integration/test_web_statements.py`, `tests/integration/test_web_bulk_limit.py` | new: given |
| `tests/integration/test_statements_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Uploading several files at once, a folder, or a ZIP; keeping the uploaded PDF; replacing or deleting an imported statement.
- Gaps before the first or after the last statement of an account, or for accounts that only use SimpleFIN (Phase 25 reports stale data).
- Any change to the import itself, its messages, or `fin import`.

## Dependencies

None new: uploads use `python-multipart`, which the forms already need.

## Design

```python
# src/finances/domain/periods.py
def statement_gaps(periods: Iterable[tuple[date, date]]) -> list[tuple[date, date]]: ...

# src/finances/analysis/statements.py
@dataclass(frozen=True)
class StatementGap:
    account: str
    start: date
    end: date


def statement_gap_lines(session: Session) -> list[StatementGap]: ...

# src/finances/views/statements.py
@dataclass(frozen=True)
class StatementRow:
    account: str
    file: str
    parser: str
    period: str    # "START to END"
    opening: str   # format_cents
    closing: str   # format_cents
    lines: str
    new: str       # rows inserted


@dataclass(frozen=True)
class GapRow:
    account: str
    start: str     # ISO
    end: str       # ISO


def statement_rows(statements: list[Statement], names: dict[int, str]) -> list[StatementRow]: ...
def gap_rows(gaps: list[StatementGap]) -> list[GapRow]: ...
def import_rows(result: StatementImportResult) -> list[tuple[str, str]]: ...
```

`UPLOAD_LIMIT` in `web/app.py` is 20 × 1024 × 1024 bytes.

New messages, in full (each shown on the Statements page with status `400`; the import's own messages are shown the same way):

| When | Message |
|---|---|
| no file, or an empty one | `choose a PDF statement` |
| the file does not start with `%PDF-` | `the file is not a PDF` |
| the file is larger than `UPLOAD_LIMIT` | `a statement must be at most 20 MB` |

## Requirements

### Part 1: the bulk form

- **R1.** `POST /transactions/bulk` reads its form itself with room for 1100 fields (`await request.form(max_fields=1100)`), so a full page of 1000 chosen rows plus the form's own fields reaches the route; everything else about the route is as Phase 16j made it. The route may become `async` and run its database work with `starlette.concurrency.run_in_threadpool`.

### Part 2: gaps and views

- **R2.** `statement_gaps` sorts the periods by start, joins those that overlap or touch (one ends the day before the next starts), and returns each run of days between two joined periods as `(first missing day, last missing day)`, in date order.
- **R3.** `statement_gap_lines` gives, for every account with statements (inactive ones too), the gaps of its `statement_periods`, ordered by account name ignoring case, then by start.
- **R4.** `statement_rows` gives each statement as `fin statements list` shows it (the same cells, in `list_statements` order). `gap_rows` formats the dates.
- **R5.** `import_rows` gives the upload's result as label and value pairs, in the words of `fin import statement`: for an import or a dry run `File`, `Parser`, `Account`, `Period` (`START to END`), `Lines`, `Inserted`, `Duplicates`, `Status` (`imported`, or `dry run, nothing written`); for a file already imported `File` and `Status` (`already imported`). A failed import has no rows; its message is the page's error.

### Part 3: the page

- **R6.** `GET /statements` checks the database as the other pages do, then renders `statements.html` with `accounts` (the active accounts' names), `chosen_account` (empty), `dry_run` (false), `result` (none), `statements` (`statement_rows`), `gaps` (`gap_rows(statement_gap_lines)`), and `error`.
- **R7.** `POST /statements/upload` (multipart: `csrf`, `file`, `account`, `dry_run`) runs the existing checks (origin, form token, database). It reads at most `UPLOAD_LIMIT` + 1 bytes of the file and checks, in the table's order, that there is a non-empty file, that it is not too large, and that it starts with `%PDF-`. The stored name is the part of the sent file name after its last `/` or `\`, cut to 255 characters. It calls `import_statement` (with `account_name` the chosen account, or none when empty, and `dry_run` when the box is ticked, in one session); after an import that wrote rows (status `imported`), it runs `categorize` and `pair_transfers` in a session of their own.
- **R8.** The page is rendered again (not redirected) with the result: status `200` with `result` (`import_rows`) for an import, a dry run, or a file already imported; status `400` with `error` for a refused upload or a failed import. `chosen_account` and `dry_run` keep what was sent. The upload's bytes are never written to disk or logged.

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
</head>
<body>
<nav>
  <span class="brand">Finances</span>
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

`src/finances/web/templates/statements.html`

```html
{% extends "layout.html" %}
{% block title %}Statements · Finances{% endblock %}
{% block content %}
<h1>Statements</h1>
{% include "messages.html" %}
<h2>Upload a statement</h2>
<p class="hint">A PDF statement from a supported bank. It is read here and not kept or sent anywhere; only its name and a fingerprint are stored.</p>
<form method="post" action="/statements/upload" enctype="multipart/form-data" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <label>PDF <input type="file" name="file" accept="application/pdf,.pdf" required></label>
  <label>Account
    <select name="account">
      <option value=""{% if not chosen_account %} selected{% endif %}>Find it from the statement</option>
      {% for name in accounts %}<option value="{{ name }}"{% if name == chosen_account %} selected{% endif %}>{{ name }}</option>
      {% endfor %}
    </select>
  </label>
  <label><input type="checkbox" name="dry_run" value="yes"{% if dry_run %} checked{% endif %}> Check only, write nothing</label>
  <button type="submit">Upload</button>
</form>
{% if result %}
<h2>Result</h2>
<table class="detail">
<tbody>
{% for label, value in result %}<tr><th>{{ label }}</th><td>{{ value }}</td></tr>
{% endfor %}</tbody>
</table>
{% endif %}
<h2>Statements</h2>
{% if statements %}
<table>
<thead><tr><th>Account</th><th>File</th><th>Parser</th><th>Period</th><th class="amount">Opening</th><th class="amount">Closing</th><th class="amount">Lines</th><th class="amount">New</th></tr></thead>
<tbody>
{% for row in statements %}<tr><td>{{ row.account }}</td><td>{{ row.file }}</td><td>{{ row.parser }}</td><td>{{ row.period }}</td><td class="amount">{{ row.opening }}</td><td class="amount">{{ row.closing }}</td><td class="amount">{{ row.lines }}</td><td class="amount">{{ row.new }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No statements.</p>
{% endif %}
<h2>Gaps</h2>
<p class="hint">Days between two statements of the same account that neither covers.</p>
{% if gaps %}
<table>
<thead><tr><th>Account</th><th>Missing from</th><th>Missing to</th></tr></thead>
<tbody>
{% for row in gaps %}<tr><td>{{ row.account }}</td><td>{{ row.start }}</td><td>{{ row.end }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No gaps between statements.</p>
{% endif %}
{% endblock %}
```

## Given tests

23 tests in three files. The page tests use `tests/conftest.py`'s fake bank: its statement for last four digits 1111 has four rows and imports as the expected values show (those values come from today's import).

`tests/unit/test_statement_gaps.py`

```python
from datetime import date

import pytest

from finances.domain.periods import statement_gaps


def d(month: int, day: int) -> date:
    return date(2026, month, day)


@pytest.mark.parametrize(
    ("periods", "gaps"),
    [
        ([], []),
        ([(d(1, 1), d(1, 31))], []),
        ([(d(1, 1), d(1, 31)), (d(2, 1), d(2, 28))], []),
        ([(d(1, 1), d(1, 31)), (d(3, 1), d(3, 31))], [(d(2, 1), d(2, 28))]),
        ([(d(3, 5), d(4, 4)), (d(1, 5), d(2, 4))], [(d(2, 5), d(3, 4))]),
        ([(d(1, 1), d(1, 31)), (d(1, 15), d(2, 14)), (d(2, 16), d(3, 1))], [(d(2, 15), d(2, 15))]),
        ([(d(1, 1), d(3, 31)), (d(2, 1), d(2, 28)), (d(4, 2), d(4, 30))], [(d(4, 1), d(4, 1))]),
    ],
    ids=[
        "none",
        "one",
        "back-to-back",
        "a-month-missing",
        "unsorted",
        "overlap-then-one-day",
        "inside-another",
    ],
)
def test_statement_gaps(periods: list[tuple[date, date]], gaps: list[tuple[date, date]]) -> None:
    assert statement_gaps(periods) == gaps
```

`tests/integration/test_web_statements.py`

```python
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import create_account, create_rule
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts

STATEMENTS = ["Account", "File", "Parser", "Period", "Opening", "Closing", "Lines", "New"]
JANUARY = [
    "Test Card",
    "jan.pdf",
    "fake_bank",
    "2026-01-01 to 2026-01-31",
    "-$100.00",
    "-$84.99",
    "4",
    "4",
]
IMPORTED = [
    ["File", "jan.pdf"],
    ["Parser", "fake_bank"],
    ["Account", "Test Card"],
    ["Period", "2026-01-01 to 2026-01-31"],
    ["Lines", "4"],
    ["Inserted", "4"],
    ["Duplicates", "0"],
    ["Status", "imported"],
]
MARCH_ROW = "2026-03-05|-|purchases|-10.00|2222|-|ACME COFFEE #12"


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient, fake_bank) -> TestClient:
    """Test Card ends in 1111 (the fake statement's card); a rule sends ACME COFFEE to Dining."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
        create_rule(session, "ACME COFFEE", "Dining")
    engine.dispose()
    client.get("/statements")
    return client


def upload(client: TestClient, name: str, content: bytes, **fields: str):
    return client.post(
        "/statements/upload",
        data={"csrf": client.cookies["fin_csrf"], "account": "", **fields},
        files={"file": (name, content, "application/pdf")},
    )


def test_the_menu_has_statements(home: TestClient) -> None:
    html = home.get("/statements").text
    assert 'href="/statements" aria-current="page">Statements</a>' in html
    assert html.count('aria-current="page"') == 1
    assert 'href="/statements">Statements</a>' in home.get("/accounts").text
    assert "<script" not in html


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get("/statements")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_the_empty_page(home: TestClient) -> None:
    found = page(home, "/statements")
    assert ("empty", "No statements.") in found.paragraphs
    assert ("empty", "No gaps between statements.") in found.paragraphs
    form = found.find("/statements/upload")
    assert form["inputs"]["file"] == ("file", "")
    assert form["inputs"]["dry_run"] == ("checkbox", "yes")
    assert form["selects"]["account"] == [("", True), ("Test Card", False)]
    assert 'enctype="multipart/form-data"' in home.get("/statements").text


def test_upload_a_statement(home: TestClient, fake_statement_pdf: Callable[..., bytes]) -> None:
    response = upload(home, "jan.pdf", fake_statement_pdf())
    assert response.status_code == 200
    found = Page(response.text)
    assert found.rows == [*IMPORTED, STATEMENTS, JANUARY]
    acme = page(home, "/transactions?text=acme").rows
    assert [row[3] for row in acme[1:]] == ["Dining", "Dining"]


def test_a_dry_run_writes_nothing(
    home: TestClient, fake_statement_pdf: Callable[..., bytes]
) -> None:
    response = upload(home, "jan.pdf", fake_statement_pdf(), dry_run="yes")
    assert response.status_code == 200
    found = Page(response.text)
    assert found.rows == [*IMPORTED[:-1], ["Status", "dry run, nothing written"]]
    assert ("empty", "No statements.") in found.paragraphs
    assert found.find("/statements/upload")["inputs"]["dry_run"] == ("checkbox", "yes")
    assert 'value="yes" checked' in response.text


def test_the_same_file_twice(home: TestClient, fake_statement_pdf: Callable[..., bytes]) -> None:
    upload(home, "jan.pdf", fake_statement_pdf())
    response = upload(home, "again.pdf", fake_statement_pdf())
    assert response.status_code == 200
    assert Page(response.text).rows == [
        ["File", "again.pdf"],
        ["Status", "already imported"],
        STATEMENTS,
        JANUARY,
    ]


def test_only_the_file_name_is_kept(
    home: TestClient, fake_statement_pdf: Callable[..., bytes]
) -> None:
    upload(home, "../../elsewhere/jan.pdf", fake_statement_pdf())
    upload(
        home,
        "C:\\Users\\someone\\mar.pdf",
        fake_statement_pdf(
            start="2026-03-01",
            end="2026-03-31",
            opening="-84.99",
            closing="-94.99",
            rows=(MARCH_ROW,),
        ),
    )
    files = [row[1] for row in page(home, "/statements").rows[1:3]]
    assert files == ["mar.pdf", "jan.pdf"]


def test_gaps_between_statements(
    home: TestClient, fake_statement_pdf: Callable[..., bytes]
) -> None:
    upload(home, "jan.pdf", fake_statement_pdf())
    upload(
        home,
        "mar.pdf",
        fake_statement_pdf(
            start="2026-03-01",
            end="2026-03-31",
            opening="-84.99",
            closing="-94.99",
            rows=(MARCH_ROW,),
        ),
    )
    found = page(home, "/statements")
    assert found.rows[-2:] == [
        ["Account", "Missing from", "Missing to"],
        ["Test Card", "2026-02-01", "2026-02-28"],
    ]
    assert (
        texts(found, "hint")[-1]
        == "Days between two statements of the same account that neither covers."
    )


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("jan.pdf", b"", "choose a PDF statement"),
        ("notes.txt", b"just some text", "the file is not a PDF"),
        ("big.pdf", b"%PDF-" + b"0" * (20 * 1024 * 1024), "a statement must be at most 20 MB"),
    ],
)
def test_a_refused_upload(home: TestClient, name: str, content: bytes, message: str) -> None:
    response = upload(home, name, content)
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", message) in found.paragraphs
    assert ("empty", "No statements.") in found.paragraphs


def test_no_file_at_all(home: TestClient) -> None:
    response = home.post(
        "/statements/upload", data={"csrf": home.cookies["fin_csrf"], "account": ""}
    )
    assert response.status_code == 400
    assert ("error", "choose a PDF statement") in Page(response.text).paragraphs


def test_a_statement_the_import_refuses(
    home: TestClient, fake_statement_pdf: Callable[..., bytes], make_pdf
) -> None:
    response = upload(home, "x.pdf", fake_statement_pdf(last4="9999"))
    assert response.status_code == 400
    assert (
        "error",
        'no account ends in 9999; add one with: fin accounts add --name "NAME" --institution'
        ' "Fake Bank" --type credit_card --last4 9999',
    ) in Page(response.text).paragraphs
    response = upload(home, "bad.pdf", make_pdf([["NOT A STATEMENT"]]))
    assert response.status_code == 400
    assert ("error", "unrecognized statement format") in Page(response.text).paragraphs
    assert ("empty", "No statements.") in Page(response.text).paragraphs


def test_the_form_needs_its_token(
    home: TestClient, fake_statement_pdf: Callable[..., bytes]
) -> None:
    response = home.post(
        "/statements/upload", files={"file": ("jan.pdf", fake_statement_pdf(), "application/pdf")}
    )
    assert (response.status_code, response.text) == (403, "Bad form token")
    assert home.get("/statements/upload").status_code == 405
```

`tests/integration/test_web_bulk_limit.py`

```python
import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.web.app import create_app
from tests.support import WEB_PORT, Page


@pytest.fixture
def home(tmp_settings: Settings) -> TestClient:
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    upgrade_to_head()
    client.get("/transactions")
    return client


@pytest.mark.parametrize(
    ("count", "message"),
    [(1000, "transaction not found"), (1001, "at most 1000 transactions at once")],
)
def test_a_page_of_1000_rows_reaches_the_app(home: TestClient, count: int, message: str) -> None:
    """A full page of 1000 rows plus the form's own fields passes the framework's field limit."""
    response = home.post(
        "/transactions/bulk",
        data={
            "csrf": home.cookies["fin_csrf"],
            "id": [str(number) for number in range(1, count + 1)],
            "category": "Dining",
            "action": "set",
            "back": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert ("error", message) in Page(response.text).paragraphs
```

## Tests to write

`tests/integration/test_statements_more.py`:

- `statement_gap_lines` with two accounts (ordered by name) and an inactive account with a gap;
- `import_rows` for each status, and none for a failed import;
- an upload with an account chosen in the form, and with one that does not exist (the import's message);
- a file name of 300 characters is stored cut to 255;
- no file is written under the data folder by an upload (compare the folder's files before and after).

## Rules for this phase

- **Thin.** The routes call the import service, `categorize`, `pair_transfers`, `analysis`, and `views`; the gap rule lives in `domain`.
- **No JavaScript.** Nothing from an upload is logged at INFO or above.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_statement_gaps.py tests/integration/test_web_statements.py tests/integration/test_web_bulk_limit.py`, 23 tests;
- also `.venv/bin/python -m pytest tests/integration/test_web_accounts_and_bulk.py tests/e2e/test_cli_import.py --no-cov`: all pass;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.views --cov=finances.analysis --cov=finances.domain.periods --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|timedelta" -- src/finances/web`, `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static`, and `git grep -n --untracked -E "write_bytes|NamedTemporaryFile|mkstemp|open\(" -- src/finances/web/app.py` (no output).

## Report

As in `docs/phase-conventions.md`, headed `## Phase 16g: statement upload (YYYY-MM-DD)`.
