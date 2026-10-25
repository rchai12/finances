# Phase 20b: the login on the web

## Goal

20a's password guards the web, with the owner's choices (2026-10-24): every page needs the login, the Mac included; a session ends after 30 minutes idle and at most 1 day after logging in; after logging in the person lands on the page they asked for; a Log out button in the menu; while locked, the login page says when it unlocks. After this phase:

- once a password is set, every page and form but the login page and the site's own static files answers a request without a valid session by sending it to `/login` (a page asked for comes back after the login);
- a session is a cookie signed with 20a's session key, so `fin web password` ends every session;
- `/login` checks the password through 20a's `attempt`, so the lockout holds on the web;
- with no password set the site works as before: `fin web serve` refuses to start without one (20a), and every earlier web test runs unchanged.

20c reaches the site through Tailscale Serve (and marks the cookie `Secure`); 20d asks for the password again before the four sensitive actions.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-20a-password-and-lockout.md`, `src/finances/web/login.py`
- `src/finances/web/app.py` (`create_app`, `_Guard`, `_now`), `src/finances/web/render.py` (`_render`, the form-token cookie), `src/finances/web/forms.py` (`forged`), `src/finances/web/templates/layout.html`

## Starting state

N is `3887` when Phase 20a is the last phase built. The newest migration is `0021`; this phase adds none. The given templates (a new `login.html`, and a Log out form in the menu before Sync now) were checked against every earlier integration and end-to-end test: all 2198 pass unchanged, the menu still ending with Sync now.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/templates/login.html` (new), `layout.html` | the given diff (R8) |
| `src/finances/web/session.py` (new) | `COOKIE`, `IDLE`, `LONGEST`, `make_cookie`, `read_cookie`, `safe_next`, `gate` (R1 to R3) |
| `src/finances/views/login.py` (new) | `LOCKED`, `lock_text` (R7) |
| `src/finances/web/routes/login.py` (new), `src/finances/web/app.py` | the `login` router: three routes; the gate added in `create_app` (R3 to R6) |
| `tests/unit/test_web_split.py` | the given diff (R9) |
| `tests/integration/test_web_login.py` | new: given |
| `tests/unit/test_session.py`, `tests/integration/test_web_login_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- The `Secure` flag, the host check for Tailscale's name, `fin doctor` (20c); asking for the password again (20d).
- Remembering a device beyond the 1-day limit; showing who is logged in; logins in the audit trail.
- Any change to 20a's store or commands.

## Dependencies

None new: `hmac`, `hashlib`, and `urllib.parse` from the standard library.

## Design

```python
# src/finances/web/session.py
COOKIE = "fin_session"
IDLE = timedelta(minutes=30)
LONGEST = timedelta(days=1)

def make_cookie(key: str, issued: datetime, last: datetime) -> str: ...
# "<issued>.<last>.<signature>": the two times as whole UTC seconds since 1970, and the
# HMAC-SHA256 of "<issued>.<last>" under the key, in hex
def read_cookie(value: str, key: str, now: datetime) -> datetime | None: ...
# the session's issued time when the value is well formed, the signature matches
# (hmac.compare_digest), now is no more than IDLE after its last time and no more than
# LONGEST after its issued time; otherwise None
def safe_next(text: str) -> str: ...
# text when it starts with "/" and not "//" and holds no "\"; otherwise "/"
async def gate(request: Request, call_next) -> Response: ...

# src/finances/views/login.py
LOCKED = "Too many wrong passwords: the login is locked until {time}."
def lock_text(until: datetime) -> str: ...
# the end in the machine's local time: "15:30 on 24 October" (24-hour, no leading zero on the day)
```

The `login` router:

| Route | Fields | Does | Answers |
|---|---|---|---|
| `GET /login` | `next` (query) | renders `login` with `ready` (`has_password()`) and `next` (`safe_next`) | 200 |
| `POST /login` | `csrf`, `password`, `next` | `forged(request, csrf)`; no password set: `no password is set; run fin web password`; else `attempt(password, web_app._now())` | right: 303 to `safe_next(next)` with the session cookie (issued and last now); locked: 400 with `lock_text(locked_until)`; wrong: 400 with `wrong password` |
| `POST /logout` | `csrf` | `forged(request, csrf)` | 303 to `/login`, the session cookie deleted |

The cookie is set with `httponly=True`, `samesite="strict"`, `path="/"`, and no `max_age` (it ends with the browser, and the server's own checks end it sooner).

## Requirements

### The session

- **R1.** `make_cookie` and `read_cookie` as designed; `read_cookie` never raises.
- **R2.** `safe_next` as designed.
- **R3.** `gate`, added in `create_app` with `api.middleware("http")`, lets through `/login` and every path under `/static/`, and every request when `has_password()` is false. Otherwise it reads the cookie with `session_key()` and `web_app._now()` (looked up when the request runs): a valid session goes on, and its cookie is set again with the same issued time and the last time now; a request without one is answered 303 to `/login?next=<the path and query, quoted with urllib.parse.quote and "/" kept>` for GET and HEAD, and to `/login` for any other method. A Keychain failure answers 503 with the plain text `could not use the system keychain`.

### The pages

- **R4.** `GET /login` as designed.
- **R5.** `POST /login` as designed; it checks the form token with `forged` (no database needed), so a forged or tokenless login answers 403 as other forms do.
- **R6.** `POST /logout` as designed; GET on `/logout` answers 405.
- **R7.** `lock_text` as designed.
- **R8.** Apply the given template diff exactly.
- **R9.** Apply the given diff to `tests/unit/test_web_split.py`. No other earlier test changes.

## Given template diff

Applied to `src/finances/web/templates/` (do not change).

```text
diff --git a/src/finances/web/templates/layout.html b/src/finances/web/templates/layout.html
index a858d07..cbf4d8a 100644
--- a/src/finances/web/templates/layout.html
+++ b/src/finances/web/templates/layout.html
@@ -26,6 +26,7 @@
   <a href="/backups"{% if section == "backups" %} aria-current="page"{% endif %}>Backups</a>
   <a href="/history"{% if section == "history" %} aria-current="page"{% endif %}>History</a>
   <a href="/review"{% if section == "review" %} aria-current="page"{% endif %}>Review</a>
+  <form method="post" action="/logout" class="nav-logout"><input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit">Log out</button></form>
   <form method="post" action="/sync/run" class="nav-sync"><input type="hidden" name="csrf" value="{{ csrf }}"><button type="submit">Sync now</button></form>
 </nav>
 <main>
diff --git a/src/finances/web/templates/login.html b/src/finances/web/templates/login.html
new file mode 100644
index 0000000..e7a6f0b
--- /dev/null
+++ b/src/finances/web/templates/login.html
@@ -0,0 +1,16 @@
+{% extends "layout.html" %}
+{% block title %}Log in · Finances{% endblock %}
+{% block content %}
+<h1>Log in</h1>
+{% include "messages.html" %}
+{% if ready %}
+<form method="post" action="/login" class="fields">
+  <input type="hidden" name="csrf" value="{{ csrf }}">
+  <input type="hidden" name="next" value="{{ next }}">
+  <label>Password <input type="password" name="password" required autocomplete="current-password" autofocus></label>
+  <button type="submit">Log in</button>
+</form>
+{% else %}
+<p class="hint">No password is set. On the Mac, run fin web password, then serve the site again.</p>
+{% endif %}
+{% endblock %}
```

## Given diff to earlier tests

```text
diff --git a/tests/unit/test_web_split.py b/tests/unit/test_web_split.py
index a71b8c7..3b4274c 100644
--- a/tests/unit/test_web_split.py
+++ b/tests/unit/test_web_split.py
@@ -19,6 +19,7 @@ AREAS = [
     "export",
     "history",
     "home",
+    "login",
     "people",
     "reports",
     "review",
@@ -99,6 +100,9 @@ ROUTES = {
     ("GET", "/backups/restore"),
     ("POST", "/backups/restore"),
     ("GET", "/history"),
+    ("GET", "/login"),
+    ("POST", "/login"),
+    ("POST", "/logout"),
     ("GET", "/review"),
     ("POST", "/review"),
 }
```

## Given tests

14 tests in one file. Do not change them.

`tests/integration/test_web_login.py`

```python
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.web.app import create_app
from finances.web.login import set_password
from tests.support import WEB_PORT, Page, texts

RIGHT = "correct horse battery"
T0 = datetime(2026, 10, 24, 19, 30, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    found = Clock()
    monkeypatch.setattr("finances.web.app._now", found)
    return found


@pytest.fixture
def client(tmp_settings: Settings, clock: Clock) -> TestClient:
    upgrade_to_head()
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def guarded(client: TestClient) -> TestClient:
    set_password(RIGHT, None)
    return client


def log_in(client: TestClient, password: str = RIGHT, next_page: str = "/"):
    client.get("/login")
    return client.post(
        "/login",
        data={"csrf": client.cookies["fin_csrf"], "password": password, "next": next_page},
        follow_redirects=False,
    )


def test_no_password_means_no_login(client: TestClient) -> None:
    assert client.get("/reports").status_code == 200
    assert texts(Page(client.get("/login").text), "hint") == [
        "No password is set. On the Mac, run fin web password, then serve the site again."
    ]


def test_a_page_needs_the_login(guarded: TestClient) -> None:
    response = guarded.get("/reports?month=2026-05", follow_redirects=False)
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/login?next=/reports%3Fmonth%3D2026-05",
    )
    posted = guarded.post("/sync/run", data={"csrf": "x"}, follow_redirects=False)
    assert (posted.status_code, posted.headers["location"]) == (303, "/login")
    assert guarded.get("/static/app.css").status_code == 200


def test_logging_in_returns_to_the_page(guarded: TestClient) -> None:
    response = log_in(guarded, next_page="/reports?month=2026-05")
    assert (response.status_code, response.headers["location"]) == (303, "/reports?month=2026-05")
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("fin_session=")
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert guarded.get("/reports").status_code == 200


@pytest.mark.parametrize("next_page", ["//evil.example/x", "https://evil.example/", "reports", ""])
def test_only_this_sites_pages(guarded: TestClient, next_page: str) -> None:
    assert log_in(guarded, next_page=next_page).headers["location"] == "/"


def test_a_wrong_password(guarded: TestClient) -> None:
    response = log_in(guarded, password="not the password")
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["wrong password"]
    assert guarded.get("/", follow_redirects=False).status_code == 303


@pytest.fixture
def chicago(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TZ", "America/Chicago")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_the_lock_says_when_it_ends(guarded: TestClient, chicago: None) -> None:
    for _ in range(4):
        log_in(guarded, password="not the password")
    response = log_in(guarded, password="not the password")
    assert texts(Page(response.text), "error") == [
        "Too many wrong passwords: the login is locked until 15:30 on 24 October."
    ]
    locked = log_in(guarded)
    assert locked.status_code == 400
    assert texts(Page(locked.text), "error") == [
        "Too many wrong passwords: the login is locked until 15:30 on 24 October."
    ]


def test_the_idle_and_the_longest_time(guarded: TestClient, clock: Clock) -> None:
    log_in(guarded)
    clock.now = T0 + timedelta(minutes=29)
    assert guarded.get("/", follow_redirects=False).status_code == 200
    clock.now = T0 + timedelta(minutes=59)
    assert guarded.get("/", follow_redirects=False).status_code == 200
    clock.now = T0 + timedelta(minutes=89, seconds=1)
    assert guarded.get("/", follow_redirects=False).status_code == 303
    log_in(guarded)
    for minutes in range(20, 24 * 60 + 1, 20):
        clock.now = T0 + timedelta(minutes=89, seconds=1) + timedelta(minutes=minutes)
        assert guarded.get("/", follow_redirects=False).status_code == 200
    clock.now = clock.now + timedelta(minutes=20)
    assert guarded.get("/", follow_redirects=False).status_code == 303


def test_logging_out(guarded: TestClient) -> None:
    log_in(guarded)
    response = guarded.post(
        "/logout", data={"csrf": guarded.cookies["fin_csrf"]}, follow_redirects=False
    )
    assert (response.status_code, response.headers["location"]) == (303, "/login")
    assert guarded.get("/", follow_redirects=False).status_code == 303


def test_a_new_password_ends_every_session(guarded: TestClient) -> None:
    log_in(guarded)
    set_password("another long password", RIGHT)
    assert guarded.get("/", follow_redirects=False).status_code == 303


def test_a_login_without_the_form_token(guarded: TestClient) -> None:
    response = guarded.post("/login", data={"password": RIGHT}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")


def test_the_menu_logs_out_before_sync_now(guarded: TestClient) -> None:
    log_in(guarded)
    html = guarded.get("/").text
    menu = html[html.index("<nav>") : html.index("</nav>")]
    assert 0 < menu.index('action="/logout"') < menu.index('action="/sync/run"')
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/unit/test_session.py`:

- `make_cookie` of a fixed key and two times gives the expected three parts; `read_cookie` refuses a changed signature, a changed time, a value with two parts, non-digits, and a value made with another key;
- `read_cookie` accepts exactly `IDLE` after the last time and exactly `LONGEST` after the issued time, and refuses one second more of either;
- `safe_next` of `/a?b=c`, `/`, `//x`, `/\x`, `x`, and `""`;
- `lock_text` with `TZ` set to `Europe/London` gives the London time (`time.tzset()`, restored after).

`tests/integration/test_web_login_more.py`:

- HEAD of a page without a session is sent to the login like GET;
- `/login` itself and `/static/charts.js` answer without a session; `GET /logout` answers 405;
- a Keychain that raises on `session_key` answers 503 with the plain text;
- a cookie made with the session key before `fin web password` changed it is refused.

## Rules for this phase

- The session key and the password never reach a page, a log line, or a message; secrets are compared with `hmac.compare_digest`.
- The gate is the one place that decides whether a request may go on; no route repeats it.
- Times are UTC in the cookie and local only in `lock_text`'s words; a test of that rule sets the zone.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file above, 14 tests; at least N + 14 passed in all;
- `git diff --stat HEAD -- tests` lists only `tests/unit/test_web_split.py`;
- `git grep -n "session_key()\|has_password()" -- src/finances/web/routes` lists only `src/finances/web/routes/login.py`;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web.session --cov=finances.web.routes.login --cov=finances.views.login --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 20b: the login on the web (YYYY-MM-DD)`.
