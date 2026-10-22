# Phase 16l: a Sync now button in the menu

## Goal

Fresh data from SimpleFIN is one click away from any page. After this phase, every page's menu ends with a **Sync now** button that does exactly what the SimpleFIN page's Sync now button does (Phase 16b): it posts the page's form token to the existing `POST /sync/run`, which syncs every mapped link and shows the result page. Nothing else changes: no new route, no change to how a sync runs.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/web/templates/layout.html`, `src/finances/web/static/app.css`, `src/finances/web/routes/sync.py` (`run`), `src/finances/web/forms.py` (`refused`), `src/finances/web/render.py` (`_render` gives every page `csrf`)

## Starting state

N is `3033` when Phase 14a is the last phase built.

Every page is rendered by `_render`, which puts the form token in `csrf`, including the error page and the not-migrated page, so the menu's form always has a token. The web passes no retry waits to `run_links`, so a press never waits on Phase 33's retries.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/templates/layout.html` | the button (given diff) |
| `src/finances/web/static/app.css` | one rule (given diff) |
| `tests/support.py`, `tests/integration/test_web_forms.py`, `tests/integration/test_web_sync_setup.py` | their page readers leave out forms inside `<nav>` (given diff) |
| `tests/integration/test_web_nav_sync.py` | new: given |
| `docs/progress.md` | one new entry |

No Python module under `src/` changes.

## Out of scope

- A new route, a redirect back to the page the button was pressed on, or any change to `POST /sync/run` or its result page.
- Hiding the button when nothing is mapped (the result page already says `No mapped accounts.`); a busy indicator or any JavaScript.

## Dependencies

None new. No migration.

## Requirements

- **R1.** Apply the given diff exactly. In `layout.html` the button's form is the last thing in `<nav>`: `<form method="post" action="/sync/run" class="nav-sync">` with a hidden `csrf` field holding the page's token and a `Sync now` submit button. `app.css` gains `nav .nav-sync { margin: 0 0 0 auto; }`, which pushes it to the right end of the menu.
- **R2.** The three test page readers (`Page` in `tests/support.py`, and the local `Page` classes of `test_web_forms.py` and `test_web_sync_setup.py`) skip forms inside `<nav>`, so every earlier test that lists a page's forms keeps reading the page's own forms. These are the only readers whose tests see the menu's form (the architect ran the whole suite with the button: 8 earlier tests failed through these three readers and none through any other; with the diff all pass).
- **R3.** Pressing the button from any page runs the sync as the SimpleFIN page's button does, with the same token and origin checks; on a database that is not migrated it gives the not-migrated page (503), as `refused` already does.

## Given tests

16 tests in one file. They pass with the given diff alone.

`tests/integration/test_web_nav_sync.py`

```python
import re

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, texts

BUTTON = re.compile(
    r'<form method="post" action="/sync/run" class="nav-sync">'
    r'<input type="hidden" name="csrf" value="([A-Za-z0-9_-]{43})">'
    r'<button type="submit">Sync now</button></form>'
)
PAGES = [
    "/",
    "/accounts",
    "/people",
    "/transactions",
    "/statements",
    "/categories",
    "/transfers",
    "/reports",
    "/insights",
    "/budgets",
    "/ahead",
    "/sync",
    "/backups",
]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


def menu(html: str) -> str:
    return html[html.index("<nav>") : html.index("</nav>")]


@pytest.mark.parametrize("path", PAGES)
def test_every_page_ends_its_menu_with_the_button(client: TestClient, path: str) -> None:
    upgrade_to_head()
    response = client.get(path)
    assert response.status_code == 200
    assert BUTTON.findall(menu(response.text)) == [client.cookies["fin_csrf"]]
    assert menu(response.text).rstrip().endswith("</form>")


def test_pressing_it_on_another_page_runs_a_sync(client: TestClient) -> None:
    upgrade_to_head()
    token = BUTTON.findall(client.get("/reports").text)[0]
    response = client.post(
        "/sync/run",
        data={"csrf": token},
        headers={"Origin": f"http://127.0.0.1:{WEB_PORT}"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert texts(Page(response.text), "empty") == ["No mapped accounts."]


def test_the_not_migrated_page_has_it_and_pressing_it_says_so(client: TestClient) -> None:
    response = client.get("/reports")
    assert response.status_code == 503
    tokens = BUTTON.findall(menu(response.text))
    assert tokens == [client.cookies["fin_csrf"]]
    pressed = client.post("/sync/run", data={"csrf": tokens[0]})
    assert pressed.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(pressed.text).paragraphs


def test_the_button_sits_at_the_right_of_the_menu(client: TestClient) -> None:
    assert "nav .nav-sync { margin: 0 0 0 auto; }" in client.get("/static/app.css").text
```

## Given diff

```text
diff --git a/src/finances/web/static/app.css b/src/finances/web/static/app.css
index c0af2d1..536e0ca 100644
--- a/src/finances/web/static/app.css
+++ b/src/finances/web/static/app.css
@@ -4,6 +4,7 @@ nav { display: flex; gap: 1rem; align-items: baseline; padding: .75rem 1rem; bor
 nav .brand { font-weight: 600; margin-right: 1rem; }
 nav a { color: inherit; text-decoration: none; }
 nav a[aria-current="page"] { color: var(--accent); font-weight: 600; }
+nav .nav-sync { margin: 0 0 0 auto; }
 main { padding: 1rem; max-width: 72rem; }
 table { border-collapse: collapse; width: 100%; }
 th, td { text-align: left; padding: .35rem .6rem; border-bottom: 1px solid var(--line); }
diff --git a/src/finances/web/templates/layout.html b/src/finances/web/templates/layout.html
index 156c87b..229a3a3 100644
--- a/src/finances/web/templates/layout.html
+++ b/src/finances/web/templates/layout.html
@@ -23,6 +23,7 @@
   <a href="/ahead"{% if section == "ahead" %} aria-current="page"{% endif %}>Ahead</a>
   <a href="/sync"{% if section == "sync" %} aria-current="page"{% endif %}>SimpleFIN</a>
   <a href="/backups"{% if section == "backups" %} aria-current="page"{% endif %}>Backups</a>
+  <form method="post" action="/sync/run" class="nav-sync"><input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit">Sync now</button></form>
 </nav>
 <main>
 {% block content %}{% endblock %}
diff --git a/tests/integration/test_web_forms.py b/tests/integration/test_web_forms.py
index 6d10231..342e8a1 100644
--- a/tests/integration/test_web_forms.py
+++ b/tests/integration/test_web_forms.py
@@ -27,7 +27,7 @@ POSTS = [
 
 
 class Page(HTMLParser):
-    """The parts of a page the tests read: table rows, paragraphs, and forms."""
+    """The parts of a page the tests read: table rows, paragraphs, and forms (not the menu's)."""
 
     def __init__(self, html: str) -> None:
         super().__init__()
@@ -40,10 +40,13 @@ class Page(HTMLParser):
         self.text: list[str] = []
         self.form: dict | None = None
         self.select: str | None = None
+        self.in_nav = False
         self.feed(html)
 
     def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
         values = {name: value or "" for name, value in attrs}
+        if tag == "nav":
+            self.in_nav = True
         if tag == "tr":
             self.row = []
         elif tag in ("td", "th"):
@@ -58,7 +61,8 @@ class Page(HTMLParser):
                 "inputs": {},
                 "selects": {},
             }
-            self.forms.append(self.form)
+            if not self.in_nav:
+                self.forms.append(self.form)
         elif tag == "input" and self.form is not None:
             self.form["inputs"][values.get("name", "")] = (
                 values.get("type", "text"),
@@ -73,6 +77,8 @@ class Page(HTMLParser):
             )
 
     def handle_endtag(self, tag: str) -> None:
+        if tag == "nav":
+            self.in_nav = False
         if tag in ("td", "th") and self.cell is not None and self.row is not None:
             self.row.append("".join(self.cell).strip())
             self.cell = None
diff --git a/tests/integration/test_web_sync_setup.py b/tests/integration/test_web_sync_setup.py
index e425ce0..8cdd17a 100644
--- a/tests/integration/test_web_sync_setup.py
+++ b/tests/integration/test_web_sync_setup.py
@@ -41,7 +41,7 @@ RUN_HEADINGS = [
 
 
 class Page(HTMLParser):
-    """The parts of a page the tests read: table rows, paragraphs, and forms."""
+    """The parts of a page the tests read: table rows, paragraphs, and forms (not the menu's)."""
 
     def __init__(self, html: str) -> None:
         super().__init__()
@@ -54,10 +54,13 @@ class Page(HTMLParser):
         self.text: list[str] = []
         self.form: dict | None = None
         self.select: str | None = None
+        self.in_nav = False
         self.feed(html)
 
     def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
         values = {name: value or "" for name, value in attrs}
+        if tag == "nav":
+            self.in_nav = True
         if tag == "tr":
             self.row = []
         elif tag in ("td", "th"):
@@ -72,7 +75,8 @@ class Page(HTMLParser):
                 "inputs": {},
                 "selects": {},
             }
-            self.forms.append(self.form)
+            if not self.in_nav:
+                self.forms.append(self.form)
         elif tag == "input" and self.form is not None:
             self.form["inputs"][values.get("name", "")] = (
                 values.get("type", "text"),
@@ -87,6 +91,8 @@ class Page(HTMLParser):
             )
 
     def handle_endtag(self, tag: str) -> None:
+        if tag == "nav":
+            self.in_nav = False
         if tag in ("td", "th") and self.cell is not None and self.row is not None:
             self.row.append("".join(self.cell).strip())
             self.cell = None
diff --git a/tests/support.py b/tests/support.py
index 0806f4f..894eefd 100644
--- a/tests/support.py
+++ b/tests/support.py
@@ -49,7 +49,7 @@ def failed_cleanly(result, message: str) -> bool:
 
 
 class Page(HTMLParser):
-    """The parts of a page the tests read: table rows, paragraphs, and forms."""
+    """The parts of a page the tests read: table rows, paragraphs, and forms (not the menu's)."""
 
     def __init__(self, html: str) -> None:
         super().__init__()
@@ -63,10 +63,13 @@ class Page(HTMLParser):
         self.form: dict | None = None
         self.select: str | None = None
         self.links: list[str] = []
+        self.in_nav = False
         self.feed(html)
 
     def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
         values = {name: value or "" for name, value in attrs}
+        if tag == "nav":
+            self.in_nav = True
         if tag == "a":
             self.links.append(values.get("href", ""))
         if tag == "tr":
@@ -83,7 +86,8 @@ class Page(HTMLParser):
                 "inputs": {},
                 "selects": {},
             }
-            self.forms.append(self.form)
+            if not self.in_nav:
+                self.forms.append(self.form)
         elif tag == "input" and self.form is not None:
             self.form["inputs"][values.get("name", "")] = (
                 values.get("type", "text"),
@@ -98,6 +102,8 @@ class Page(HTMLParser):
             )
 
     def handle_endtag(self, tag: str) -> None:
+        if tag == "nav":
+            self.in_nav = False
         if tag in ("td", "th") and self.cell is not None and self.row is not None:
             self.row.append("".join(self.cell).strip())
             self.cell = None
```

## Tests to write

None: R1 to R3 are covered by the given tests and the earlier tests the diff keeps passing. Add a test only if `scripts/check.py` asks for coverage.

## Rules for this phase

- Every earlier test passes; the only earlier test files that change are the three in the given diff, and only their page readers.
- The button is a plain HTML form: no script, no inline style.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file: `tests/integration/test_web_nav_sync.py`, 16 tests; at least N + 16 passed in all;
- `git diff --stat HEAD -- src`: only `layout.html` and `app.css`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 16l: a Sync now button in the menu (YYYY-MM-DD)`.
