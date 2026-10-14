# Phase 16a: the web interface, foundation

## Goal

Give the household a web page instead of a terminal. After this phase, `fin web serve` starts a local web site at `http://127.0.0.1:8765` with a menu and four read-only pages:

- **Accounts**: every account with its owner (closed ones on request);
- **People**: each person, the accounts they own, and their cardholder names;
- **Transactions**: filtered by account, person (or Joint, or Unassigned), dates, and number of rows;
- **SimpleFIN**: each mapped account's link, Keychain entry, last pull, and drift.

Phase 16b adds the forms and buttons: adding accounts and people, setting owners and cardholder names, linking SimpleFIN, mapping its accounts, and syncing. This phase builds what those forms stand on and makes the site safe to run on the household's machine.

**Where it can be reached.** Only from this machine: the server listens on `127.0.0.1` and nowhere else. When the household moves to the Mac Studio, the whole system will be reached remotely through a private VPN; a login for this site comes then (Phase 20). Nothing here may make that harder: no other address, no open port, no external asset.

**Why the extra protection on a local site.** Any web page open in the household's browser can make the browser send requests to `127.0.0.1`. This site therefore answers only requests addressed to itself by name (`127.0.0.1:PORT` or `localhost:PORT`), which defeats DNS rebinding; sends headers that forbid scripts, framing, and outside resources; and has no JavaScript at all. Phase 16b adds CSRF tokens before the first form that changes anything.

## Read first

- `AGENTS.md`: "Privacy rules" (rule 1: the web UI binds to 127.0.0.1 only), "Architecture rules" (`web` is thin)
- `docs/architecture.md`: "Privacy boundary", "People"
- `src/finances/analysis/people.py`, `src/finances/cli/accounts.py`, `src/finances/cli/listing.py`, `src/finances/cli/people.py`, `src/finances/cli/sync.py` (`status`): the web pages show the same things
- `tests/conftest.py`: the in-memory Keychain and the network guard

## Starting state

- Phase 21 is committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `1528` when Phase 21 is the last phase built.
- There is no `src/finances/web/` package, and no web dependency is installed.
- `finances.cli`, `finances.analysis`, and `finances.config` are at 100% line and branch coverage.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `pyproject.toml` | dependencies and package data (below) |
| `src/finances/config.py` | one setting added: `web_port` |
| `src/finances/web/__init__.py` | new: a docstring only |
| `src/finances/web/app.py` | new: `HOST`, `SECURITY_HEADERS`, `NOT_MIGRATED`, `create_app` |
| `src/finances/web/templates/*.html`, `src/finances/web/static/app.css` | new: given, do not change |
| `src/finances/cli/web.py` | new: `fin web serve` |
| `src/finances/cli/main.py` | the `web` group registered |
| `tests/unit/test_web_security.py`, `tests/integration/test_web_pages.py`, `tests/e2e/test_cli_web.py` | given, do not change |
| `docs/progress.md` | one new entry |

You may add private helpers to `app.py`. Do not change any other production file or any existing test.

## Out of scope

- Any form, button, or request that changes data. Phase 16b.
- JavaScript of any kind, HTMX included, and any font, script, style, or image from outside the app.
- A login, sessions, HTTPS, or any address other than `127.0.0.1`. Phase 20.
- Statement upload, a dashboard, charts, or categories.
- Changing the commands or the functions they call.

## Dependencies

Add to `dependencies` in `pyproject.toml`, after `"keyring>=25"`:

```toml
    "fastapi>=0.143",
    "uvicorn>=0.30",
    "jinja2>=3.1",
```

Add `"httpx2>=2.0",` to the `dev` extras, after `"pytest-cov>=5"`. FastAPI's test client needs it; with the older `httpx` instead, Starlette prints a deprecation warning on every test run.

Add, after `[tool.setuptools.packages.find]`:

```toml
[tool.setuptools.package-data]
"finances.web" = ["templates/*.html", "static/*.css"]
```

Then install:

`.venv/bin/python -m pip install -e ".[dev]"`

## Design

```python
# src/finances/web/app.py
HOST = "127.0.0.1"
SECURITY_HEADERS: dict[str, str]   # exactly as in tests/unit/test_web_security.py
NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"


def create_app(port: int) -> ASGIApp: ...
```

`create_app(port)` returns a FastAPI application, without its API documentation (`docs_url`, `redoc_url`, and `openapi_url` all `None`), wrapped in a small ASGI middleware that does the host check and adds the headers (R3, R4). It serves `static/` at `/static` and renders the given templates with `fastapi.templating.Jinja2Templates`, whose `.html` templates escape every value. Every template gets a `section` value: the template's name without `.html`, which the menu uses to mark the current page.

```python
# src/finances/config.py, in Settings
    web_port: int = 8765        # FIN_WEB_PORT
```

```python
# src/finances/cli/web.py
app = typer.Typer(help="Serve the web interface on this machine.", no_args_is_help=True)


@app.command()
def serve(port: int | None = None) -> None: ...   # --port, 1024 to 65535
```

Registered in `main.py` as `app.add_typer(web_app, name="web")`, after `people`.

## Requirements

### Part 1: serving

- **R1.** `fin web serve` prints `Serving on http://127.0.0.1:PORT (press Ctrl+C to stop)` and calls `uvicorn.run(create_app(PORT), host="127.0.0.1", port=PORT, access_log=False, log_level="warning")`, through the module attribute `uvicorn.run` so that tests can replace it. `PORT` is `--port` when given, otherwise the setting `web_port`. `--port` accepts 1024 to 65535; Typer refuses anything else with exit code 2. There is no `--host` option and no other way to choose the address.
- **R2.** `Settings.web_port` is an `int`, default `8765`, read from `FIN_WEB_PORT`.
- **R3.** The access log is off because a request line can hold an account or person name (privacy rule 4). The server logs warnings and errors only.

### Part 2: safety

- **R4.** Every HTTP request whose `Host` header is not exactly `127.0.0.1:PORT` or `localhost:PORT` is answered `400` with the body `Bad host` (`text/plain`), before any route runs. Other ASGI messages (the server's start-up and shut-down) pass through unchanged.
- **R5.** Every HTTP response, including the `400` of R4, redirects, `404`s, and static files, carries exactly the headers in `SECURITY_HEADERS`, replacing any earlier value of the same header.
- **R6.** No API documentation is served: `/docs`, `/redoc`, and `/openapi.json` answer `404`.
- **R7.** The given templates and stylesheet hold no JavaScript and refer to nothing outside the app. Every value from the database reaches the page escaped.

### Part 3: pages

All pages extend `layout.html`, which holds the menu. Each page first checks the database: when `current_revision()` is not `head_revision()`, it renders `error.html` with `NOT_MIGRATED` and status `503`.

- **R8.** `GET /` redirects to `/accounts` with status `303`.
- **R9.** `GET /accounts` renders `accounts.html` with one row per account from `list_accounts`, active accounts only unless the query `closed=true` is given. Each row: `name`, `institution`, `type` (the type's value), `last4` (`••` and the four digits, or empty), `active` (`yes` or `no`), `owner` (from `load_attribution`: the person's name, `Joint`, or empty), and `closed` (whether closed accounts are shown).
- **R10.** `GET /people` renders `people.html` with one row per person in `list_people` order: `name`; `owns`, the names of the accounts, active or closed, that the person owns, in `list_accounts` order, joined with `, `; and `cardholders`, the person's cardholder names, sorted, joined with `, `.
- **R11.** `GET /transactions` reads the query values `account`, `person`, `from`, `to`, and `limit`, each optional text; `limit` defaults to `50`. An empty value means no filter. It renders `transactions.html` with:
  - `choices`: `accounts`, the names of every account, closed included, in `list_accounts` order; and `people`, the names in `list_people` order;
  - `special`: the pair (`JOINT_FILTER`, `UNASSIGNED_FILTER`);
  - `chosen`: the five query values as given, keyed `account`, `person`, `from`, `to`, `limit`;
  - `rows`: from `list_transactions_with_people`, each with `date` (ISO), `account` (its name), `description`, `amount` (`format_cents`), `card` (`••` and four digits, or empty), `section` (or empty), and `person` (or empty);
  - `error`: `None`, or the message of a refused filter.

  A filter is refused, with status `400`, an `error`, and no rows, when: the account is not found by `get_account_by_name` (`account not found`); `from` or `to` is not a date in ISO form (`from must be a date as YYYY-MM-DD`, `to must be a date as YYYY-MM-DD`); `limit` is not a whole number from 1 to 1000 (`limit must be a whole number from 1 to 1000`); or `list_transactions_with_people` raises its `ValueError` (its message).
- **R12.** `GET /sync` renders `sync.html` with one row per mapping from `list_feed_accounts`, in its order: `link`, `account` (its name), `feed_account` (the SimpleFIN account id), `keychain` (`yes` or `no` from `load_access_url`, or `unknown` when it raises `SyncError`), `last_pull` (the latest pull's `pulled_at` as `YYYY-MM-DD HH:MM UTC`, or `never`), and `balance_date` and `drift` from the latest pull that has a balance (ISO date and `format_cents`, each empty when there is none). The page never shows an access URL.
- **R13.** `GET /static/app.css` serves the given stylesheet. A missing path answers `404`.

### Part 4: the code

- **R14.** `web/app.py` reads only through `db` repository functions, `analysis/people.py`, `db.migrate`, `domain.money`, and `sync.links.load_access_url`. It writes nothing, holds no query, and does not import `keyring`.

## Given templates and stylesheet

Create these files exactly as shown. The tests read their markup.

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
  <a href="/sync"{% if section == "sync" %} aria-current="page"{% endif %}>SimpleFIN</a>
</nav>
<main>
{% block content %}{% endblock %}
</main>
</body>
</html>
```

`src/finances/web/templates/error.html`

```html
{% extends "layout.html" %}
{% block content %}
<p class="error">{{ message }}</p>
{% endblock %}
```

`src/finances/web/templates/accounts.html`

```html
{% extends "layout.html" %}
{% block title %}Accounts · Finances{% endblock %}
{% block content %}
<h1>Accounts</h1>
{% if closed %}<p><a href="/accounts">Hide closed accounts</a></p>{% else %}<p><a href="/accounts?closed=true">Show closed accounts</a></p>{% endif %}
{% if rows %}
<table>
<thead><tr><th>Name</th><th>Institution</th><th>Type</th><th>Last 4</th><th>Active</th><th>Owner</th></tr></thead>
<tbody>
{% for row in rows %}<tr><td>{{ row.name }}</td><td>{{ row.institution }}</td><td>{{ row.type }}</td><td>{{ row.last4 }}</td><td>{{ row.active }}</td><td>{{ row.owner }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No accounts.</p>
{% endif %}
{% endblock %}
```

`src/finances/web/templates/people.html`

```html
{% extends "layout.html" %}
{% block title %}People · Finances{% endblock %}
{% block content %}
<h1>People</h1>
{% if rows %}
<table>
<thead><tr><th>Name</th><th>Owns</th><th>Cardholder names</th></tr></thead>
<tbody>
{% for row in rows %}<tr><td>{{ row.name }}</td><td>{{ row.owns }}</td><td>{{ row.cardholders }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No people.</p>
{% endif %}
{% endblock %}
```

`src/finances/web/templates/transactions.html`

```html
{% extends "layout.html" %}
{% block title %}Transactions · Finances{% endblock %}
{% block content %}
<h1>Transactions</h1>
<form method="get" action="/transactions" class="filters">
  <label>Account
    <select name="account">
      <option value=""{% if not chosen.account %} selected{% endif %}>All accounts</option>
      {% for name in choices.accounts %}<option value="{{ name }}"{% if name == chosen.account %} selected{% endif %}>{{ name }}</option>
      {% endfor %}
    </select>
  </label>
  <label>Person
    <select name="person">
      <option value=""{% if not chosen.person %} selected{% endif %}>Everyone</option>
      {% for name in choices.people %}<option value="{{ name }}"{% if name == chosen.person %} selected{% endif %}>{{ name }}</option>
      {% endfor %}
      <option value="{{ special[0] }}"{% if chosen.person == special[0] %} selected{% endif %}>Joint</option>
      <option value="{{ special[1] }}"{% if chosen.person == special[1] %} selected{% endif %}>Unassigned</option>
    </select>
  </label>
  <label>From <input type="date" name="from" value="{{ chosen['from'] }}"></label>
  <label>To <input type="date" name="to" value="{{ chosen['to'] }}"></label>
  <label>Rows <input type="number" name="limit" min="1" max="1000" value="{{ chosen.limit }}"></label>
  <button type="submit">Show</button>
</form>
{% if error %}<p class="error">{{ error }}</p>
{% elif rows %}
<table>
<thead><tr><th>Date</th><th>Account</th><th>Description</th><th class="amount">Amount</th><th>Card</th><th>Section</th><th>Person</th></tr></thead>
<tbody>
{% for row in rows %}<tr><td>{{ row.date }}</td><td>{{ row.account }}</td><td>{{ row.description }}</td><td class="amount">{{ row.amount }}</td><td>{{ row.card }}</td><td>{{ row.section }}</td><td>{{ row.person }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No transactions.</p>
{% endif %}
{% endblock %}
```

`src/finances/web/templates/sync.html`

```html
{% extends "layout.html" %}
{% block title %}SimpleFIN · Finances{% endblock %}
{% block content %}
<h1>SimpleFIN</h1>
{% if rows %}
<table>
<thead><tr><th>Link</th><th>Account</th><th>SimpleFIN account</th><th>Keychain</th><th>Last pull</th><th>Balance date</th><th class="amount">Drift</th></tr></thead>
<tbody>
{% for row in rows %}<tr><td>{{ row.link }}</td><td>{{ row.account }}</td><td>{{ row.feed_account }}</td><td>{{ row.keychain }}</td><td>{{ row.last_pull }}</td><td>{{ row.balance_date }}</td><td class="amount">{{ row.drift }}</td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No mapped accounts.</p>
{% endif %}
{% endblock %}
```

`src/finances/web/static/app.css`

```css
:root { color-scheme: light dark; --line: #8884; --muted: #888; --accent: #2563eb; --bad: #b91c1c; }
body { font: 15px/1.5 system-ui, -apple-system, sans-serif; margin: 0; }
nav { display: flex; gap: 1rem; align-items: baseline; padding: .75rem 1rem; border-bottom: 1px solid var(--line); flex-wrap: wrap; }
nav .brand { font-weight: 600; margin-right: 1rem; }
nav a { color: inherit; text-decoration: none; }
nav a[aria-current="page"] { color: var(--accent); font-weight: 600; }
main { padding: 1rem; max-width: 72rem; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: .35rem .6rem; border-bottom: 1px solid var(--line); }
td.amount, th.amount { text-align: right; font-variant-numeric: tabular-nums; }
.empty { color: var(--muted); }
.error { color: var(--bad); }
.filters { display: flex; gap: .75rem; flex-wrap: wrap; align-items: end; margin-bottom: 1rem; }
.filters label { display: flex; flex-direction: column; font-size: .85rem; }
```

## Given tests

Create these three files exactly as shown and do not change them. If one of their tests fails, the production code is wrong. Together they reach every line and branch of the code this phase adds, so there are no tests for you to write.

`tests/unit/test_web_security.py`

```python
import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.web.app import HOST, SECURITY_HEADERS, create_app

PORT = 8765


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")


def test_the_host_is_this_machine_only() -> None:
    assert HOST == "127.0.0.1"


def test_the_security_headers() -> None:
    assert SECURITY_HEADERS == {
        "content-security-policy": (
            "default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        ),
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "no-referrer",
        "cache-control": "no-store",
    }


@pytest.mark.parametrize("host", [f"127.0.0.1:{PORT}", f"localhost:{PORT}"])
def test_requests_for_this_machine_are_answered(client: TestClient, host: str) -> None:
    response = client.get("/static/app.css", headers={"host": host})
    assert response.status_code == 200


@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        f"evil.example:{PORT}",
        "127.0.0.1",
        "localhost",
        "127.0.0.1:9999",
        f"127.0.0.2:{PORT}",
        f"[::1]:{PORT}",
        f"LOCALHOST:{PORT}x",
        "",
    ],
)
def test_any_other_host_is_refused(client: TestClient, host: str) -> None:
    response = client.get("/accounts", headers={"host": host})
    assert (response.status_code, response.text) == (400, "Bad host")
    assert (
        response.headers["content-security-policy"] == SECURITY_HEADERS["content-security-policy"]
    )


@pytest.mark.parametrize(
    "path", ["/", "/accounts", "/static/app.css", "/nowhere", "/static/none.css"]
)
def test_every_answer_carries_the_security_headers(client: TestClient, path: str) -> None:
    response = client.get(path, follow_redirects=False)
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_no_api_documentation_is_served(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_the_stylesheet_is_served_from_this_app() -> None:
    from pathlib import Path

    import finances.web

    css = (Path(finances.web.__file__).parent / "static" / "app.css").read_text()
    assert "@import" not in css and "url(" not in css


def test_the_server_start_and_stop_messages_pass_through(tmp_settings: Settings) -> None:
    with TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}") as started:
        assert started.get("/static/app.css").status_code == 200
```

`tests/integration/test_web_pages.py`

```python
from datetime import date
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import AccountRow, TransactionRow
from finances.db.repositories import (
    create_account,
    create_feed_pull,
    create_person,
    map_feed_account,
    set_account_owner,
    set_cardholder_alias,
)
from finances.web.app import create_app

PORT = 8765
NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"


class Page(HTMLParser):
    """The parts of a page the tests read: table rows, select options, and paragraphs."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.options: dict[str, list[tuple[str, str, bool]]] = {}
        self.paragraphs: list[tuple[str, str]] = []
        self.links: list[str] = []
        self.current: list[str] | None = None
        self.cell: list[str] | None = None
        self.select: str | None = None
        self.option: tuple[str, bool] | None = None
        self.text: list[str] = []
        self.paragraph: str | None = None
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "tr":
            self.current = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag == "select":
            self.select = values.get("name") or ""
            self.options[self.select] = []
        elif tag == "option":
            self.option = (values.get("value") or "", "selected" in values)
            self.text = []
        elif tag == "p":
            self.paragraph = values.get("class") or ""
            self.text = []
        elif tag == "a":
            self.links.append(values.get("href") or "")

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)
        self.text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self.current is not None and self.cell is not None:
            self.current.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.current is not None:
            self.rows.append(self.current)
            self.current = None
        elif tag == "option" and self.select is not None and self.option is not None:
            value, selected = self.option
            self.options[self.select].append((value, "".join(self.text).strip(), selected))
            self.option = None
        elif tag == "select":
            self.select = None
        elif tag == "p" and self.paragraph is not None:
            self.paragraphs.append((self.paragraph, "".join(self.text).strip()))
            self.paragraph = None


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")


@pytest.fixture
def household(tmp_settings: Settings, client: TestClient) -> TestClient:
    """Alex owns the card; checking is joint; savings is closed; Sam owns a closed old card."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test <Card>", "Test Bank", "credit_card", last4="1111")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        savings = create_account(session, "Test Savings", "Test Bank", "savings", last4="3333")
        alex = create_person(session, "Alex")
        sam = create_person(session, "Sam")
        set_account_owner(session, card.id, alex.id)
        set_account_owner(session, checking.id, None)
        set_cardholder_alias(session, "SAM DOE", sam.id)
        session.get(AccountRow, savings.id).is_active = False
        old = create_account(session, "Test Old Card", "Test Bank", "credit_card")
        set_account_owner(session, old.id, sam.id)
        session.get(AccountRow, old.id).is_active = False
        for account_id, day, cents, cardholder, card_last4 in (
            (card.id, 8, -800, "SAM DOE", "2222"),
            (checking.id, 7, -700, None, None),
            (card.id, 6, -600, None, None),
            (savings.id, 5, 1000, None, None),
        ):
            session.add(
                TransactionRow(
                    account_id=account_id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=f"ACME <i>{day}</i>",
                    section="purchases" if cents < 0 else None,
                    card_last4=card_last4,
                    cardholder=cardholder,
                    source="statement",
                    fingerprint=f"{day}".ljust(64, "x"),
                )
            )
    engine.dispose()
    return client


def test_home_goes_to_accounts(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert (response.status_code, response.headers["location"]) == (303, "/accounts")


@pytest.mark.parametrize("path", ["/accounts", "/people", "/transactions", "/sync"])
def test_every_page_needs_a_migrated_database(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 503
    assert ("error", NOT_MIGRATED) in Page(response.text).paragraphs


@pytest.mark.parametrize(
    ("path", "label"),
    [
        ("/accounts", "Accounts"),
        ("/people", "People"),
        ("/transactions", "Transactions"),
        ("/sync", "SimpleFIN"),
    ],
)
def test_every_page_has_the_menu_and_marks_its_own_entry(
    household: TestClient, path: str, label: str
) -> None:
    html = household.get(path).text
    for href in ("/accounts", "/people", "/transactions", "/sync"):
        assert f'href="{href}"' in html
    assert f'aria-current="page">{label}</a>' in html
    assert html.count('aria-current="page"') == 1
    assert "<script" not in html


def test_accounts(household: TestClient) -> None:
    page = Page(household.get("/accounts").text)
    assert page.rows == [
        ["Name", "Institution", "Type", "Last 4", "Active", "Owner"],
        ["Test <Card>", "Test Bank", "credit_card", "••1111", "yes", "Alex"],
        ["Test Checking", "Test Bank", "checking", "", "yes", "Joint"],
    ]
    assert "/accounts?closed=true" in page.links


def test_accounts_with_closed_ones(household: TestClient) -> None:
    page = Page(household.get("/accounts?closed=true").text)
    assert page.rows[3:] == [
        ["Test Old Card", "Test Bank", "credit_card", "", "no", "Sam"],
        ["Test Savings", "Test Bank", "savings", "••3333", "no", ""],
    ]
    assert "/accounts" in page.links


def test_text_from_the_database_is_escaped(household: TestClient) -> None:
    assert "Test &lt;Card&gt;" in household.get("/accounts").text
    assert "<i>" not in household.get("/transactions").text


def test_accounts_with_none(tmp_settings: Settings, client: TestClient) -> None:
    upgrade_to_head()
    assert ("empty", "No accounts.") in Page(client.get("/accounts").text).paragraphs


def test_people(household: TestClient) -> None:
    assert Page(household.get("/people").text).rows == [
        ["Name", "Owns", "Cardholder names"],
        ["Alex", "Test <Card>", ""],
        ["Sam", "Test Old Card", "SAM DOE"],
    ]


def test_people_with_none(tmp_settings: Settings, client: TestClient) -> None:
    upgrade_to_head()
    assert ("empty", "No people.") in Page(client.get("/people").text).paragraphs


TRANSACTION_HEADINGS = ["Date", "Account", "Description", "Amount", "Card", "Section", "Person"]


def test_transactions(household: TestClient) -> None:
    page = Page(household.get("/transactions").text)
    assert page.rows == [
        TRANSACTION_HEADINGS,
        ["2026-05-08", "Test <Card>", "ACME <i>8</i>", "-$8.00", "••2222", "purchases", "Sam"],
        ["2026-05-07", "Test Checking", "ACME <i>7</i>", "-$7.00", "", "purchases", "Joint"],
        ["2026-05-06", "Test <Card>", "ACME <i>6</i>", "-$6.00", "", "purchases", "Alex"],
        ["2026-05-05", "Test Savings", "ACME <i>5</i>", "$10.00", "", "", ""],
    ]
    assert page.options["account"] == [
        ("", "All accounts", True),
        ("Test <Card>", "Test <Card>", False),
        ("Test Checking", "Test Checking", False),
        ("Test Old Card", "Test Old Card", False),
        ("Test Savings", "Test Savings", False),
    ]
    assert page.options["person"] == [
        ("", "Everyone", True),
        ("Alex", "Alex", False),
        ("Sam", "Sam", False),
        ("joint", "Joint", False),
        ("unassigned", "Unassigned", False),
    ]


@pytest.mark.parametrize(
    ("query", "days"),
    [
        ("person=Alex", ["2026-05-06"]),
        ("person=joint", ["2026-05-07"]),
        ("person=unassigned", ["2026-05-05"]),
        ("account=Test+Checking", ["2026-05-07"]),
        ("from=2026-05-06&to=2026-05-07", ["2026-05-07", "2026-05-06"]),
        ("limit=2", ["2026-05-08", "2026-05-07"]),
        ("person=sam&account=test+%3Ccard%3E", ["2026-05-08"]),
        ("account=&person=&from=&to=", ["2026-05-08", "2026-05-07", "2026-05-06", "2026-05-05"]),
    ],
)
def test_transaction_filters(household: TestClient, query: str, days: list[str]) -> None:
    page = Page(household.get(f"/transactions?{query}").text)
    assert [row[0] for row in page.rows[1:]] == days


def test_the_chosen_filters_stay_chosen(household: TestClient) -> None:
    html = household.get("/transactions?person=joint&from=2026-05-01&limit=7").text
    page = Page(html)
    assert ("joint", "Joint", True) in page.options["person"]
    assert 'name="from" value="2026-05-01"' in html
    assert 'name="limit" min="1" max="1000" value="7"' in html


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("person=Nobody", "person not found"),
        ("account=Nope", "account not found"),
        ("from=2026-13-01", "from must be a date as YYYY-MM-DD"),
        ("to=yesterday", "to must be a date as YYYY-MM-DD"),
        ("limit=0", "limit must be a whole number from 1 to 1000"),
        ("limit=1001", "limit must be a whole number from 1 to 1000"),
        ("limit=ten", "limit must be a whole number from 1 to 1000"),
    ],
)
def test_bad_filters(household: TestClient, query: str, message: str) -> None:
    response = household.get(f"/transactions?{query}")
    assert response.status_code == 400
    page = Page(response.text)
    assert ("error", message) in page.paragraphs
    assert page.rows == []


def test_transactions_with_none(household: TestClient) -> None:
    page = Page(household.get("/transactions?account=Test+Checking&from=2027-01-01").text)
    assert ("empty", "No transactions.") in page.paragraphs


def test_sync_status(household: TestClient, keychain) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        map_feed_account(session, 1, "ACT-1", "alex")
        map_feed_account(session, 2, "ACT-2", "sam")
        create_feed_pull(
            session,
            account_id=1,
            inserted=1,
            updated=0,
            removed=0,
            unchanged=0,
            feed_total_cents=-100,
            balance_cents=-100,
            balance_date=date(2026, 5, 9),
            drift_cents=-250,
        )
    engine.dispose()
    keychain.passwords[("finances-simplefin", "alex")] = "https://u:p@bridge.simplefin.org/s"
    rows = Page(household.get("/sync").text).rows
    assert rows[0] == [
        "Link",
        "Account",
        "SimpleFIN account",
        "Keychain",
        "Last pull",
        "Balance date",
        "Drift",
    ]
    assert rows[1][:4] == ["alex", "Test <Card>", "ACT-1", "yes"]
    assert rows[1][4].endswith(" UTC") and len(rows[1][4]) == 20
    assert rows[1][5:] == ["2026-05-09", "-$2.50"]
    assert rows[2] == ["sam", "Test Checking", "ACT-2", "no", "never", "", ""]
    assert "u:p@" not in household.get("/sync").text


def test_sync_status_with_nothing_mapped(household: TestClient) -> None:
    assert ("empty", "No mapped accounts.") in Page(household.get("/sync").text).paragraphs


def test_sync_status_when_the_keychain_fails(household: TestClient) -> None:
    import keyring
    import keyring.backend
    import keyring.errors

    class Broken(keyring.backend.KeyringBackend):
        priority = 1

        def get_password(self, service: str, username: str) -> str | None:
            raise keyring.errors.KeyringLocked("locked")

        def set_password(self, service: str, username: str, password: str) -> None:
            raise keyring.errors.PasswordSetError("no")

        def delete_password(self, service: str, username: str) -> None:
            raise keyring.errors.PasswordDeleteError("no")

    engine = get_engine()
    with session_scope(engine) as session:
        map_feed_account(session, 1, "ACT-1")
    engine.dispose()
    previous = keyring.get_keyring()
    keyring.set_keyring(Broken())
    try:
        assert Page(household.get("/sync").text).rows[1][3] == "unknown"
    finally:
        keyring.set_keyring(previous)
```

`tests/e2e/test_cli_web.py`

```python
import pytest
from typer.testing import CliRunner

from finances.cli import web as web_module
from finances.cli.main import app
from finances.config import Settings, get_settings

runner = CliRunner(env={"COLUMNS": "200"})


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> list[tuple[object, dict]]:
    """Replace uvicorn.run so that no server starts; remember how it was called."""
    calls: list[tuple[object, dict]] = []

    def fake_run(app: object, **options: object) -> None:
        calls.append((app, options))

    monkeypatch.setattr(web_module.uvicorn, "run", fake_run)
    return calls


def test_the_default_port_setting(tmp_settings: Settings) -> None:
    assert get_settings().web_port == 8765


def test_serve_on_the_default_port(tmp_settings: Settings, served) -> None:
    result = runner.invoke(app, ["web", "serve"])
    assert (result.exit_code, result.stdout) == (
        0,
        "Serving on http://127.0.0.1:8765 (press Ctrl+C to stop)\n",
    )
    assert len(served) == 1
    application, options = served[0]
    assert options == {
        "host": "127.0.0.1",
        "port": 8765,
        "access_log": False,
        "log_level": "warning",
    }
    assert callable(application)


def test_serve_on_a_port_from_the_settings(
    tmp_settings: Settings, served, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIN_WEB_PORT", "9123")
    get_settings.cache_clear()
    result = runner.invoke(app, ["web", "serve"])
    assert result.stdout == "Serving on http://127.0.0.1:9123 (press Ctrl+C to stop)\n"
    assert served[0][1]["port"] == 9123


def test_serve_on_a_port_given(tmp_settings: Settings, served) -> None:
    result = runner.invoke(app, ["web", "serve", "--port", "8800"])
    assert result.exit_code == 0
    assert served[0][1]["port"] == 8800
    assert served[0][1]["host"] == "127.0.0.1"


@pytest.mark.parametrize("port", ["80", "1023", "65536", "x"])
def test_a_bad_port(tmp_settings: Settings, served, port: str) -> None:
    result = runner.invoke(app, ["web", "serve", "--port", port])
    assert result.exit_code == 2
    assert served == []


def test_there_is_no_host_option(tmp_settings: Settings, served) -> None:
    result = runner.invoke(app, ["web", "serve", "--host", "0.0.0.0"])
    assert result.exit_code == 2
    assert served == []
```

## Rules for this phase

- **One address.** The server listens on `127.0.0.1` only. `0.0.0.0`, another interface, or a host option must not appear anywhere.
- **No JavaScript and nothing from outside.** No `<script>`, no external URL in a template or the stylesheet.
- **Thin.** `web/` shows what the functions return; it holds no business logic and no query.
- **No access log**, and nothing logged at INFO or above.
- **Tests start no server.** They use FastAPI's test client, or replace `uvicorn.run`.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.
- Do not run `fin web serve` against the real database in `data/`; the owner does that after verification.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, no warnings summary, at least N + 68 passed, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_web_security.py tests/integration/test_web_pages.py tests/e2e/test_cli_web.py --no-cov` | exactly `68 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| each of the five searches below | no output |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.cli --cov=finances.config --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -E "^ *(import|from) +(requests|httpx|urllib|socket|http|aiohttp|ssl|ftplib|smtplib)" -- src/finances ':!src/finances/sync' ':!src/finances/config.py'`

`git grep -n --untracked -E "select\(|finances\.db\.orm|session\.(add|execute|delete)|keyring|@app\.(post|put|patch|delete)" -- src/finances/web src/finances/cli/web.py`

`git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static`

`git grep -n --untracked -E "0\.0\.0\.0|host=\"" -- src/finances`

`git grep -n --untracked -E "float|(^|[^_a-zA-Z.])print\(|logging" -- src/finances/web src/finances/cli/web.py`

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 16a: the web interface, foundation (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. Under "Deviations", list your design choices and anything you did that the spec did not ask for, or `None`.

In your final message, give the output line of each acceptance command, and for each of R1 to R14 the name of a test that covers it.
