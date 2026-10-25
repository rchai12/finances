# Phase 20d: the password again for the sensitive actions

## Goal

The last part of Phase 20, with the owner's choices (2026-10-24): restoring a backup, deleting a backup, linking SimpleFIN, and unlinking it ask for the household password again, even when logged in; the box is on each action's own form; a wrong password counts toward the same lockout as the login; it is asked every time; the terminal does not ask. After this phase:

- each of the four forms has a password box while a password is set, and its route refuses the action unless the password is right;
- unlinking gets a confirmation page of its own (`GET /sync/unlink`), reached from the Unlink button, which now opens it;
- five wrong passwords in a row on these forms lock the login as five on the login page do;
- with no password set nothing changes: no box, no check (the same rule as 20b's gate).

This finishes Phase 20 and the build order.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-20b-login-on-the-web.md`, `src/finances/web/login.py` (`attempt`, `has_password`), `src/finances/web/session.py`, `src/finances/views/login.py` (`lock_text`)
- `src/finances/web/routes/backups.py` (`delete`, `restore`, `_backup_confirm`), `src/finances/web/routes/sync.py` (`link`, `unlink`, `_sync_page`), `src/finances/web/templates/backup_confirm.html`, `sync.html`

## Starting state

N is `3937` when Phase 20c is the last phase built. The newest migration is `0021`; this phase adds none. Today the SimpleFIN page's Unlink button posts straight to `/sync/unlink`; an earlier test reads those forms' action and hidden `link` only, so the button can become a GET to the new confirmation page. The given templates were checked against every earlier integration and end-to-end test with `reauth` false: all 2229 pass unchanged.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/templates/sync_unlink.html` (new), `backup_confirm.html`, `sync.html` | the given diff (R5) |
| `src/finances/web/session.py` | `recheck` (R1) |
| `src/finances/web/routes/backups.py` | `reauth` on the confirmation page; the check in `delete` and `restore` (R2) |
| `src/finances/web/routes/sync.py` | `reauth` on the page; the check in `link`; `GET /sync/unlink`; the check in `unlink` (R3, R4) |
| `tests/unit/test_web_split.py` | the given diff (R6) |
| `tests/integration/test_web_recheck.py` | new: given |
| `tests/integration/test_web_recheck_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- The terminal's restore, link, and unlink (the owner's choice); remembering a right password for a while; any other action.
- Any change to 20a's store, 20b's gate and timeouts, or 20c's host and cookie rules.

## Dependencies

None new.

## Design

```python
# src/finances/web/session.py
def recheck(password: str) -> str | None: ...
# None when no password is set or attempt(password, web_app._now()) is ok;
# otherwise the error to show: lock_text(locked_until) while locked, "wrong password" when
# wrong, "could not use the system keychain" when the Keychain cannot be read
```

| Route | Order | A refused password |
|---|---|---|
| `POST /backups/delete` | form token; then `recheck(password)`; then the delete | the delete confirmation page, 400, the error |
| `POST /backups/restore` | form token; the backup found and checked; `recheck(password)`; the typed name; the restore | the restore confirmation page, 400, the error |
| `POST /sync/link` | form token and schema; `recheck(password)`; the link name, the token | the SimpleFIN page, 400, the error, the link name kept and the token not |
| `GET /sync/unlink` | the link name (`validate_link_name`, refused on the SimpleFIN page with 400) | renders `sync_unlink` with `link` and `reauth` |
| `POST /sync/unlink` | form token and schema; `recheck(password)`; the unlink | the unlink page, 400, the error |

`reauth` is `has_password()` (false when the Keychain cannot be read, which the gate already answers with 503), on the backup confirmation pages, the SimpleFIN page, and the unlink page. The password field is named `password`.

## Requirements

- **R1.** `recheck` as designed: a wrong password counts toward the lockout and a right one resets it, exactly as on the login page, because both go through `attempt`.
- **R2.** `delete` and `restore` check the password in the order above; a refused password changes nothing (no file deleted, nothing restored, nothing set aside).
- **R3.** `link` checks the password before it reads the link name or claims the token; a refused password stores nothing in the Keychain and never shows the token back.
- **R4.** `GET /sync/unlink` and `unlink` as designed; a refused password leaves the link's access in the Keychain.
- **R5.** Apply the given template diff exactly: the box appears only when `reauth` is true; the Unlink button is a GET form to `/sync/unlink`.
- **R6.** Apply the given diff to `tests/unit/test_web_split.py`. No other earlier test changes.

## Given template diff

Applied to `src/finances/web/templates/` (do not change).

```text
diff --git a/src/finances/web/templates/backup_confirm.html b/src/finances/web/templates/backup_confirm.html
index b848b48..02bd64c 100644
--- a/src/finances/web/templates/backup_confirm.html
+++ b/src/finances/web/templates/backup_confirm.html
@@ -10,6 +10,7 @@
   <input type="hidden" name="csrf" value="{{ csrf }}">
   <input type="hidden" name="name" value="{{ name }}">
   <label>Name <input name="confirm" value="" autocomplete="off" required></label>
+  {% if reauth %}<label>Your password <input type="password" name="password" required autocomplete="current-password"></label>{% endif %}
   <button type="submit">Restore</button>
 </form>
 {% else %}
@@ -17,6 +18,7 @@
 <form method="post" action="/backups/delete" class="fields">
   <input type="hidden" name="csrf" value="{{ csrf }}">
   <input type="hidden" name="name" value="{{ name }}">
+  {% if reauth %}<label>Your password <input type="password" name="password" required autocomplete="current-password"></label>{% endif %}
   <button type="submit">Delete</button>
 </form>
 {% endif %}
diff --git a/src/finances/web/templates/sync.html b/src/finances/web/templates/sync.html
index 210dfb8..06eec92 100644
--- a/src/finances/web/templates/sync.html
+++ b/src/finances/web/templates/sync.html
@@ -81,8 +81,7 @@
 <ul class="links">
 {% for name in links %}<li>{{ name }}
   <a href="/sync/accounts?link={{ name }}">SimpleFIN accounts</a>
-  <form method="post" action="/sync/unlink" class="inline">
-    <input type="hidden" name="csrf" value="{{ csrf }}">
+  <form method="get" action="/sync/unlink" class="inline">
     <input type="hidden" name="link" value="{{ name }}">
     <button type="submit">Unlink</button>
   </form>
@@ -113,6 +112,7 @@
   <label>Link name <input name="link" required maxlength="30" pattern="[a-z][a-z0-9-]{0,29}" value="{{ form.link }}"></label>
   <label>Setup token <input type="password" name="token" required autocomplete="off"></label>
   <label class="check"><input type="checkbox" name="replace" value="on"> Replace an existing link</label>
+  {% if reauth %}<label>Your password <input type="password" name="password" required autocomplete="current-password"></label>{% endif %}
   <button type="submit">Link</button>
 </form>
 </section>
diff --git a/src/finances/web/templates/sync_unlink.html b/src/finances/web/templates/sync_unlink.html
new file mode 100644
index 0000000..b0ddb44
--- /dev/null
+++ b/src/finances/web/templates/sync_unlink.html
@@ -0,0 +1,14 @@
+{% extends "layout.html" %}
+{% block title %}Unlink {{ link }} · Finances{% endblock %}
+{% block content %}
+<h1>Unlink {{ link }}</h1>
+{% include "messages.html" %}
+<p class="summary">Unlink {{ link }}? Its SimpleFIN access is removed from this Mac's Keychain; its accounts and their mappings stay.</p>
+<form method="post" action="/sync/unlink" class="fields">
+  <input type="hidden" name="csrf" value="{{ csrf }}">
+  <input type="hidden" name="link" value="{{ link }}">
+  {% if reauth %}<label>Your password <input type="password" name="password" required autocomplete="current-password"></label>{% endif %}
+  <button type="submit">Unlink</button>
+</form>
+<p><a href="/sync">Cancel</a></p>
+{% endblock %}
```

## Given diff to earlier tests

```text
diff --git a/tests/unit/test_web_split.py b/tests/unit/test_web_split.py
index 3b4274c..5322200 100644
--- a/tests/unit/test_web_split.py
+++ b/tests/unit/test_web_split.py
@@ -87,6 +87,7 @@ ROUTES = {
     ("GET", "/sync"),
     ("POST", "/sync/link"),
     ("POST", "/sync/unlink"),
+    ("GET", "/sync/unlink"),
     ("GET", "/sync/accounts"),
     ("POST", "/sync/map"),
     ("POST", "/sync/create"),
```

## Given tests

7 tests in one file. Do not change them. One (`test_no_password_box_without_a_password`) is a guard that passes today and must still pass.

`tests/integration/test_web_recheck.py`

```python
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.backup import list_backups, make_backup
from finances.db.migrate import upgrade_to_head
from finances.sync.links import load_access_url, save_access_url
from finances.web.app import create_app
from finances.web.login import set_password
from tests.support import WEB_PORT, Page, page, texts

RIGHT = "correct horse battery"
TOKEN = "x"


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    upgrade_to_head()
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def backup(tmp_settings: Settings, client: TestClient) -> Path:
    make_backup(
        tmp_settings.effective_database_url,
        tmp_settings.effective_backup_dir,
        14,
        datetime(2026, 10, 24, 12, 0, tzinfo=UTC),
    )
    return list_backups(tmp_settings.effective_backup_dir)[0]


@pytest.fixture
def home(client: TestClient) -> TestClient:
    set_password(RIGHT, None)
    client.get("/login")
    client.post(
        "/login",
        data={"csrf": client.cookies["fin_csrf"], "password": RIGHT, "next": "/"},
        follow_redirects=False,
    )
    return client


def send(client: TestClient, path: str, **fields: str):
    data = {"csrf": client.cookies["fin_csrf"], **fields}
    return client.post(path, data=data, follow_redirects=False)


def test_no_password_box_without_a_password(client: TestClient, backup: Path) -> None:
    found = page(client, f"/backups/delete?name={backup.name}")
    assert "password" not in found.find("/backups/delete")["inputs"]


def test_the_boxes_with_a_password(home: TestClient, backup: Path) -> None:
    for path, action in (
        (f"/backups/delete?name={backup.name}", "/backups/delete"),
        (f"/backups/restore?name={backup.name}", "/backups/restore"),
        ("/sync", "/sync/link"),
        ("/sync/unlink?link=alex", "/sync/unlink"),
    ):
        assert page(home, path).find(action)["inputs"]["password"] == ("password", ""), path


def test_deleting_needs_the_password(home: TestClient, backup: Path) -> None:
    wrong = send(home, "/backups/delete", name=backup.name, password="not the password")
    assert wrong.status_code == 400
    assert texts(Page(wrong.text), "error") == ["wrong password"]
    assert backup.exists()
    right = send(home, "/backups/delete", name=backup.name, password=RIGHT)
    assert (right.status_code, right.headers["location"]) == (303, "/backups?notice=deleted")
    assert not backup.exists()


def test_restoring_needs_the_password_before_the_name(home: TestClient, backup: Path) -> None:
    wrong = send(
        home, "/backups/restore", name=backup.name, confirm=backup.name, password="not it at all"
    )
    assert (wrong.status_code, texts(Page(wrong.text), "error")) == (400, ["wrong password"])
    right = send(home, "/backups/restore", name=backup.name, confirm=backup.name, password=RIGHT)
    assert (right.status_code, right.headers["location"]) == (303, "/backups?notice=restored")


def test_linking_needs_the_password(home: TestClient) -> None:
    wrong = send(home, "/sync/link", link="alex", token=TOKEN, password="not the password")
    assert (wrong.status_code, texts(Page(wrong.text), "error")) == (400, ["wrong password"])
    assert f'value="{TOKEN}"' not in wrong.text
    right = send(home, "/sync/link", link="alex", token=TOKEN, password=RIGHT)
    assert (right.status_code, texts(Page(right.text), "error")) == (
        400,
        ["setup token is not valid"],
    )


def test_unlinking_has_a_page_and_needs_the_password(home: TestClient) -> None:
    save_access_url("alex", "https://user:secret@bridge.example/simplefin")
    found = page(home, "/sync")
    assert [form["method"] for form in found.all("/sync/unlink")] == ["get"]
    confirm = page(home, "/sync/unlink?link=alex")
    assert texts(confirm, "summary") == [
        "Unlink alex? Its SimpleFIN access is removed from this Mac's Keychain; its accounts and"
        " their mappings stay."
    ]
    wrong = send(home, "/sync/unlink", link="alex", password="not the password")
    assert (wrong.status_code, texts(Page(wrong.text), "error")) == (400, ["wrong password"])
    assert load_access_url("alex") is not None
    right = send(home, "/sync/unlink", link="alex", password=RIGHT)
    assert (right.status_code, right.headers["location"]) == (303, "/sync?notice=unlinked")
    assert load_access_url("alex") is None


def test_wrong_passwords_here_lock_the_login(home: TestClient, backup: Path) -> None:
    for _ in range(5):
        send(home, "/backups/delete", name=backup.name, password="not the password")
    home.cookies.clear()
    home.get("/login")
    login = send(home, "/login", password=RIGHT, next="/")
    assert login.status_code == 400
    assert texts(Page(login.text), "error")[0].startswith("Too many wrong passwords:")
    assert backup.exists()
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_web_recheck_more.py`:

- `recheck` with no password set gives None for any text; while locked it gives the lock's text even for the right password;
- a restore with a wrong password and a wrong typed name gives `wrong password` (the order); with the right password and a wrong name, the name's message;
- `GET /sync/unlink?link=Bad` answers 400 on the SimpleFIN page with the link-name message;
- with no password set, posting each of the four forms without a `password` field works as before;
- a wrong password on the link form leaves the Keychain empty (the token was never claimed).

## Rules for this phase

- The password is never shown back, logged, or kept; neither is the setup token.
- Every check goes through `recheck`, so the lockout is one count for the whole site.
- Earlier tests stay unchanged except the given diff.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file above, 7 tests; at least N + 7 passed in all;
- `git diff --stat HEAD -- tests` lists only `tests/unit/test_web_split.py`;
- `git grep -n "attempt(" -- src/finances/web/routes` lists only `src/finances/web/routes/login.py`;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web.session --cov=finances.web.routes.backups --cov=finances.web.routes.sync --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 20d: the password again for the sensitive actions (YYYY-MM-DD)`.
