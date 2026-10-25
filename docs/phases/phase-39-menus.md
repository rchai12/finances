# Phase 39: menus in the navigation bar

## Goal

The navigation bar holds sixteen links and two buttons in one row. With the owner's choices (2026-10-25) it becomes:

```
Finances  Home  Money ▾  Plan ▾  Organize ▾  Review [2]  System ▾          [Log out] [Sync now]

Money ▾      Accounts, Transactions, Statements, Transfers
Plan ▾       Reports, Insights, Budgets, Ahead
Organize ▾   Categories, People, Shared
System ▾     SimpleFIN, Backups, History
```

- a menu opens on a click or a tap and needs no JavaScript (an HTML `<details>`), so it works on a phone through Tailscale and from the keyboard; opening one closes the others (`name="menu"`);
- the menu that holds the current page is marked; the page's own link keeps `aria-current="page"`, exactly as today;
- **Review** shows how many agent proposals are waiting, when there are any;
- **Log out** and **Sync now** stay at the right.

Every page link keeps its exact markup, so the earlier tests that pin `href="/x" aria-current="page">Label</a>` stay unchanged.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/web/templates/layout.html`, `src/finances/web/static/app.css` (the `nav` rules)
- `src/finances/web/render.py` (`_render`: the context every page gets; `_not_migrated`), `src/finances/web/routes/backups.py` (pages that render before the database is migrated, so a restore can run)
- `src/finances/db/repositories/proposals.py` (`list_proposals`, `OPEN`), `src/finances/db/repositories/assignments.py` (`count_uncategorized`, the model for a count)

## Starting state

N is the number passed in Phase 38's progress entry, when Phase 38 is the last phase built. `_render` gives every template `section`, `csrf`, `notice`, and `error`. The backups pages render without checking the migration; every other page renders `error` until the database is migrated. No migration.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/templates/layout.html`, `src/finances/web/static/app.css` | the given diff (R1) |
| `src/finances/db/repositories/proposals.py` | `count_open_proposals` (R2) |
| `src/finances/db/repositories/__init__.py` | export it (R2) |
| `src/finances/web/render.py` | `review_count` for every page (R3) |
| `tests/unit/test_repositories_split.py` | the given diff (R4) |
| `tests/integration/test_web_menus.py` | new: given |
| `tests/integration/test_web_menus_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Any change to a page's own content, a route other than through `_render`, or the link labels.
- JavaScript; hover menus; closing an open menu by clicking elsewhere (it closes on the next page load, or when another opens).
- A count anywhere but beside Review; a count of anything but waiting proposals.

## Dependencies

None new.

## Design

```python
# src/finances/db/repositories/proposals.py
def count_open_proposals(session: Session) -> int: ...
# how many proposals have status OPEN, with one query (select count), not by loading rows
```

`_render` adds `review_count` to the shared context:

- `0` when the template is `login` or `error`, or when `current_revision() != head_revision()`;
- otherwise `count_open_proposals` read in a session of its own that commits nothing.

A value the route passes in its own context still wins, as today for every shared key. The template shows the count only when it is not zero.

## Requirements

- **R1.** Apply the given template and style diff exactly.
- **R2.** `count_open_proposals` as designed, exported from `finances.db.repositories`.
- **R3.** `review_count` as designed: the login page and error pages never read it, a page shown before the database is migrated (the backups pages) shows no count and still renders, and every other page shows the number of open proposals.
- **R4.** Apply the given diff to `tests/unit/test_repositories_split.py`. No other earlier test changes.

## Given template diff

Applied to `src/finances/web/` (do not change). It was checked against every earlier integration and end-to-end test with `review_count` 0 and with 7: all 2256 pass unchanged.

```text
diff --git a/src/finances/web/static/app.css b/src/finances/web/static/app.css
index 17bd907..4cdef64 100644
--- a/src/finances/web/static/app.css
+++ b/src/finances/web/static/app.css
@@ -29,6 +29,14 @@ nav a { color: var(--muted); padding: .3rem .6rem; border-radius: 6px; }
 nav a:hover { color: var(--fg); background: var(--hover); text-decoration: none; }
 nav a[aria-current="page"] { color: var(--accent); background: var(--accent-tint); font-weight: 600; }
 nav .nav-sync { margin: 0 0 0 auto; }
+nav .menu { position: relative; }
+nav .menu summary { list-style: none; cursor: pointer; color: var(--muted); padding: .3rem .6rem; border-radius: 6px; }
+nav .menu summary::-webkit-details-marker { display: none; }
+nav .menu summary::after { content: " \25BE"; font-size: .75em; }
+nav .menu summary:hover { color: var(--fg); background: var(--hover); }
+nav .menu.current summary { color: var(--accent); font-weight: 600; }
+nav .menu-items { position: absolute; top: calc(100% + .25rem); left: 0; z-index: 6; display: flex; flex-direction: column; min-width: 10rem; padding: .3rem; background: var(--raised); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: 0 6px 18px rgba(0, 0, 0, .12); }
+nav .count { margin-left: -.35rem; padding: 0 .4rem; border-radius: 999px; background: var(--accent); color: var(--bg); font-size: .72rem; font-weight: 650; }
 
 main { max-width: 76rem; margin: 0 auto; padding: 1.25rem 1rem 3rem; overflow-x: auto; }
 h1 { font-size: 1.35rem; font-weight: 650; margin: .25rem 0 1rem; }
diff --git a/src/finances/web/templates/layout.html b/src/finances/web/templates/layout.html
index cbf4d8a..bc50a93 100644
--- a/src/finances/web/templates/layout.html
+++ b/src/finances/web/templates/layout.html
@@ -11,21 +11,41 @@
 <nav>
   <span class="brand">Finances</span>
   <a href="/"{% if section == "dashboard" %} aria-current="page"{% endif %}>Home</a>
-  <a href="/accounts"{% if section == "accounts" %} aria-current="page"{% endif %}>Accounts</a>
-  <a href="/people"{% if section == "people" %} aria-current="page"{% endif %}>People</a>
-  <a href="/shared"{% if section == "shared" %} aria-current="page"{% endif %}>Shared</a>
-  <a href="/transactions"{% if section == "transactions" %} aria-current="page"{% endif %}>Transactions</a>
-  <a href="/statements"{% if section == "statements" %} aria-current="page"{% endif %}>Statements</a>
-  <a href="/categories"{% if section == "categories" %} aria-current="page"{% endif %}>Categories</a>
-  <a href="/transfers"{% if section == "transfers" %} aria-current="page"{% endif %}>Transfers</a>
-  <a href="/reports"{% if section == "reports" %} aria-current="page"{% endif %}>Reports</a>
-  <a href="/insights"{% if section == "insights" %} aria-current="page"{% endif %}>Insights</a>
-  <a href="/budgets"{% if section == "budgets" %} aria-current="page"{% endif %}>Budgets</a>
-  <a href="/ahead"{% if section == "ahead" %} aria-current="page"{% endif %}>Ahead</a>
-  <a href="/sync"{% if section == "sync" %} aria-current="page"{% endif %}>SimpleFIN</a>
-  <a href="/backups"{% if section == "backups" %} aria-current="page"{% endif %}>Backups</a>
-  <a href="/history"{% if section == "history" %} aria-current="page"{% endif %}>History</a>
-  <a href="/review"{% if section == "review" %} aria-current="page"{% endif %}>Review</a>
+  <details class="menu{% if section in ("accounts", "transactions", "statements", "transfers") %} current{% endif %}" name="menu">
+    <summary>Money</summary>
+    <div class="menu-items">
+      <a href="/accounts"{% if section == "accounts" %} aria-current="page"{% endif %}>Accounts</a>
+      <a href="/transactions"{% if section == "transactions" %} aria-current="page"{% endif %}>Transactions</a>
+      <a href="/statements"{% if section == "statements" %} aria-current="page"{% endif %}>Statements</a>
+      <a href="/transfers"{% if section == "transfers" %} aria-current="page"{% endif %}>Transfers</a>
+    </div>
+  </details>
+  <details class="menu{% if section in ("reports", "insights", "budgets", "ahead") %} current{% endif %}" name="menu">
+    <summary>Plan</summary>
+    <div class="menu-items">
+      <a href="/reports"{% if section == "reports" %} aria-current="page"{% endif %}>Reports</a>
+      <a href="/insights"{% if section == "insights" %} aria-current="page"{% endif %}>Insights</a>
+      <a href="/budgets"{% if section == "budgets" %} aria-current="page"{% endif %}>Budgets</a>
+      <a href="/ahead"{% if section == "ahead" %} aria-current="page"{% endif %}>Ahead</a>
+    </div>
+  </details>
+  <details class="menu{% if section in ("categories", "people", "shared") %} current{% endif %}" name="menu">
+    <summary>Organize</summary>
+    <div class="menu-items">
+      <a href="/categories"{% if section == "categories" %} aria-current="page"{% endif %}>Categories</a>
+      <a href="/people"{% if section == "people" %} aria-current="page"{% endif %}>People</a>
+      <a href="/shared"{% if section == "shared" %} aria-current="page"{% endif %}>Shared</a>
+    </div>
+  </details>
+  <a href="/review"{% if section == "review" %} aria-current="page"{% endif %}>Review</a>{% if review_count %}<span class="count" title="Proposals waiting for review">{{ review_count }}</span>{% endif %}
+  <details class="menu{% if section in ("sync", "backups", "history") %} current{% endif %}" name="menu">
+    <summary>System</summary>
+    <div class="menu-items">
+      <a href="/sync"{% if section == "sync" %} aria-current="page"{% endif %}>SimpleFIN</a>
+      <a href="/backups"{% if section == "backups" %} aria-current="page"{% endif %}>Backups</a>
+      <a href="/history"{% if section == "history" %} aria-current="page"{% endif %}>History</a>
+    </div>
+  </details>
   <form method="post" action="/logout" class="nav-logout"><input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit">Log out</button></form>
   <form method="post" action="/sync/run" class="nav-sync"><input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit">Sync now</button></form>
 </nav>
```

## Given diff to an earlier test

```text
diff --git a/tests/unit/test_repositories_split.py b/tests/unit/test_repositories_split.py
index a3a747f..a450936 100644
--- a/tests/unit/test_repositories_split.py
+++ b/tests/unit/test_repositories_split.py
@@ -88,6 +88,7 @@ HOMES = {
     ],
     "proposals": [
         "accept_proposal",
+        "count_open_proposals",
         "decided_by_a_person",
         "decline_proposal",
         "list_advice",
@@ -176,7 +177,7 @@ def test_the_package_holds_one_module_per_area() -> None:
 
 def test_the_facade_offers_every_name_and_only_those() -> None:
     expected = sorted(name for names in HOMES.values() for name in names)
-    assert len(expected) == 124
+    assert len(expected) == 125
     assert sorted(repositories.__all__) == expected
     public = sorted(name for name in vars(repositories) if not name.startswith("_"))
     assert sorted(set(public) - set(HOMES)) == expected
```

## Given tests

14 tests in one file. Do not change them. Five pass today and must still pass: the two pages with no marked menu (`/`, `/review`) and the three without a count.

`tests/integration/test_web_menus.py`

```python
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, decline_proposal, propose_category
from finances.web.app import create_app
from finances.web.login import set_password
from tests.support import WEB_PORT

COUNT = '<span class="count" title="Proposals waiting for review">'
CURRENT = re.compile(r'<details class="menu current" name="menu">\s*<summary>(\w+)</summary>')


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    upgrade_to_head()
    return client


@pytest.fixture
def proposals(home: TestClient) -> TestClient:
    """Three category proposals, the third declined: two are waiting."""
    engine = get_engine()
    with session_scope(engine) as session:
        account = create_account(session, "Test Checking", "Test Bank", "checking")
        for number in (1, 2, 3):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, number),
                    amount_cents=-1000 * number,
                    description="ACME COFFEE",
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for number in (1, 2, 3):
            propose_category(session, number, "Coffee & Dessert", "a coffee shop")
        decline_proposal(session, 3)
    engine.dispose()
    return home


def test_the_menus_and_the_top_links_in_order(home: TestClient) -> None:
    html = home.get("/").text
    assert re.findall(r"<summary>(\w+)</summary>", html) == ["Money", "Plan", "Organize", "System"]
    marks = [">Home</a>", "<summary>Money", "<summary>Plan", "<summary>Organize"]
    marks += [">Review</a>", "<summary>System", ">Log out</button>", ">Sync now</button>"]
    assert [html.index(mark) for mark in marks] == sorted(html.index(mark) for mark in marks)


@pytest.mark.parametrize(
    ("path", "menus"),
    [
        ("/", []),
        ("/accounts", ["Money"]),
        ("/transactions", ["Money"]),
        ("/reports", ["Plan"]),
        ("/ahead", ["Plan"]),
        ("/people", ["Organize"]),
        ("/review", []),
        ("/sync", ["System"]),
        ("/history", ["System"]),
    ],
)
def test_the_menu_holding_the_page_is_marked(home: TestClient, path: str, menus: list[str]) -> None:
    html = home.get(path).text
    assert CURRENT.findall(html) == menus
    assert html.count('aria-current="page"') == 1


def test_review_shows_how_many_proposals_wait(proposals: TestClient) -> None:
    for path in ("/", "/accounts", "/review"):
        assert f">Review</a>{COUNT}2</span>" in proposals.get(path).text, path


def test_no_count_when_nothing_waits(home: TestClient) -> None:
    assert COUNT not in home.get("/").text


def test_no_count_on_the_login_page(proposals: TestClient) -> None:
    set_password("correct horse battery", None)
    response = proposals.get("/login")
    assert response.status_code == 200
    assert COUNT not in response.text


def test_a_page_shown_before_the_database_is_migrated_has_no_count(client: TestClient) -> None:
    response = client.get("/backups")
    assert response.status_code == 200
    assert COUNT not in response.text
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_web_menus_more.py`:

- `count_open_proposals` with no proposals is `0`; with an accepted one and an open one it is `1`;
- an error page (`GET /accounts` before the database is migrated, 503) has no count;
- each of the sixteen links sits inside the menu the Goal names (`/statements` and `/transfers` in Money, `/budgets` in Plan, `/categories` and `/shared` in Organize, `/backups` in System), and Home and Review sit outside every menu;
- the account page (`/accounts/<id>`) marks Money.

## Rules for this phase

- The count is read only through `count_open_proposals`, never by listing proposals.
- Earlier tests stay unchanged except the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file above, 14 tests; at least N + 14 passed in all;
- `git diff --stat HEAD -- tests` lists only `tests/unit/test_repositories_split.py`;
- `git grep -n "<script" -- src/finances/web/templates/layout.html` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web.render --cov=finances.db.repositories.proposals --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 39: menus in the navigation bar (YYYY-MM-DD)`.
