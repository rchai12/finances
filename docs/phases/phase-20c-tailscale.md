# Phase 20c: reaching the site through Tailscale

## Goal

The household's other devices reach the site through Tailscale Serve, with the owner's choices (2026-10-24): the Mac's Tailscale name in a setting, `FIN_WEB_HOSTNAME`; a launchd job that keeps the server running; `fin doctor` failing with no web password; the password alone, no Tailscale identity check. After this phase:

- the site answers to its Tailscale name as well as localhost, and accepts forms sent from `https://` that name;
- its cookies are `Secure` when a request arrives through Tailscale Serve (the name, or `X-Forwarded-Proto: https`), and stay as they are on `http://127.0.0.1`;
- the site **fails closed**: a Keychain it cannot read refuses every page with 503, where 20b let the request through;
- `fin doctor` reports the web address, the password, and the Tailscale name, failing with no password;
- the repository holds the keep-alive job (given scripts) and the runbook, `docs/remote-access.md` (written by the architect with this spec).

20d asks for the password again before restoring or deleting a backup and linking or unlinking SimpleFIN.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-20b-login-on-the-web.md`, `docs/remote-access.md`
- `src/finances/config.py`, `src/finances/web/app.py` (`_Guard`, `create_app`), `src/finances/web/forms.py` (`configure_origins`), `src/finances/web/render.py` (`_render`'s form-token cookie), `src/finances/web/session.py` (`gate`), `src/finances/web/routes/login.py`, `src/finances/diagnostics.py`

## Starting state

N is `3920` when Phase 20b is the last phase built. The newest migration is `0021`; this phase adds none. 20b's gate treats a Keychain error on `has_password()` as no password and lets the request through (an approved deviation then); this phase closes it. Three earlier tests break the whole Keychain on purpose to test the SimpleFIN pages; the given diff makes their broken Keychains answer "no password" for the `finances-web` service only, so they keep testing what they tested. Tailscale is not installed on the machine that wrote this spec, so the design works whichever way Tailscale Serve passes the host: by name, or forwarded over HTTPS.

## Scope

| Path | What changes |
|---|---|
| `src/finances/config.py` | `web_hostname` and its check (R2) |
| `src/finances/web/app.py`, `src/finances/web/forms.py` | the name in the host check and the form origins (R3, R4) |
| `src/finances/web/session.py`, `src/finances/web/render.py`, `src/finances/web/routes/login.py` | `over_https`; `Secure` cookies; failing closed (R1, R5) |
| `src/finances/diagnostics.py` | three checks (R6) |
| `scripts/install-web-service.sh`, `scripts/uninstall-web-service.sh` | new: given (R7) |
| `tests/conftest.py`, `tests/unit/test_diagnostics.py`, `tests/e2e/test_cli.py`, `tests/unit/test_session.py`, `tests/integration/test_web_pages.py`, `tests/integration/test_web_sync_setup.py` | the given diff (R8) |
| `tests/integration/test_web_tailscale.py`, `tests/e2e/test_cli_doctor_web.py` | new: given |
| `tests/integration/test_web_tailscale_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- A Tailscale identity check, `Strict-Transport-Security`, or binding to any address but 127.0.0.1; running or configuring Tailscale from the app.
- Asking for the password again (20d); any change to 20a's store or 20b's timeouts.
- Changing `docs/remote-access.md` (the architect's).

## Dependencies

None new.

## Design

```python
# src/finances/config.py
web_hostname: str | None = None   # FIN_WEB_HOSTNAME; lower-cased when set
# refused unless it matches [a-z0-9-]+(\.[a-z0-9-]+)+ after lower-casing:
# "FIN_WEB_HOSTNAME must be a host name such as mac.tail1234.ts.net"

# src/finances/web/session.py
def over_https(request: Request) -> bool: ...
# the request's host (without a port) is get_settings().web_hostname, or its
# X-Forwarded-Proto header is "https"
```

`fin doctor`'s checks gain three, after `Database schema`, in this order:

| Check | Result |
|---|---|
| `Web address` | `http://127.0.0.1:<FIN_WEB_PORT> (loopback only)`; always passes |
| `Web password` | `set OK`; `not set FAIL (run: fin web password)` (fails); `cannot read the Keychain FAIL` (fails) |
| `Tailscale name` | the name, or `not set (this Mac only)`; always passes |

## Requirements

### Failing closed

- **R1.** `gate` answers 503 with the plain text `could not use the system keychain` when `has_password()` raises, as it already does for `session_key()`; `GET /login` and `POST /login` answer the same when the Keychain cannot be read. Static files still answer.

### The Tailscale name

- **R2.** `Settings.web_hostname` as designed; the check runs when the settings are read, so a bad value stops every command with its message. `FIN_WEB_HOSTNAME` joins `tests/conftest.py`'s cleared keys (the given diff).
- **R3.** With `web_hostname` set, `_Guard` also accepts the Host `<name>` and `<name>:443`; any other host is refused as today (`Bad host`, 400).
- **R4.** With `web_hostname` set, `configure_origins` also accepts the origin `https://<name>`.
- **R5.** `over_https` as designed. When it is true, the session cookie (set by the login and set again by the gate) and the form-token cookie (set by `_render`) are also `secure=True`; otherwise they are set exactly as before.

### `fin doctor` and the files

- **R6.** `run_checks` gains the three checks as designed, so `fin doctor` exits 1 with no password set.
- **R7.** Add the given scripts exactly, executable.
- **R8.** Apply the given diff to the six earlier test files. No other earlier test changes.

## Given scripts

`scripts/install-web-service.sh` (do not change)

```sh
#!/bin/bash
# Keep `fin web serve` running as the logged-in user, with launchd: it starts at login and
# again whenever it stops.
#
#   scripts/install-web-service.sh
#
# The job runs inside the user's login session, so it can read the web password's hash in the
# Keychain. Set the password first (fin web password); without one the server refuses to start.
# Output goes to data/logs/web.log (data/ is never committed); each start writes a line with
# the local date and time. Installing again replaces the earlier job. Remove it with
# scripts/uninstall-web-service.sh.
set -euo pipefail

LABEL="local.finances.web"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIN="$REPO/.venv/bin/fin"
LOGS="$REPO/data/logs"
AGENTS="$HOME/Library/LaunchAgents"
PLIST="$AGENTS/$LABEL.plist"
DOMAIN="gui/$(id -u)"

if [[ ! -x "$FIN" ]]; then
    echo "Error: $FIN not found; install the project first" >&2
    exit 1
fi
mkdir -p "$LOGS" "$AGENTS"

cat >"$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>printf '== %s\\n' "\$(date '+%Y-%m-%d %H:%M:%S %Z')"; exec "$FIN" web serve</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$REPO</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>30</integer>
  <key>StandardOutPath</key>
  <string>$LOGS/web.log</string>
  <key>StandardErrorPath</key>
  <string>$LOGS/web.log</string>
</dict>
</plist>
PLIST
plutil -lint "$PLIST" >/dev/null

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "The web server now starts at login and again whenever it stops (log: $LOGS/web.log)"
```

`scripts/uninstall-web-service.sh` (do not change)

```sh
#!/bin/bash
# Stop the `fin web serve` job and remove it. The log in data/logs/ is kept.
set -euo pipefail

LABEL="local.finances.web"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [[ -f "$PLIST" ]]; then
    rm "$PLIST"
    echo "Removed the web server job."
else
    echo "No web server job was installed."
fi
```

## Given diff to earlier tests

```text
diff --git a/tests/conftest.py b/tests/conftest.py
index 6fd1360..f63bc75 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -38,6 +38,7 @@ _ENV_KEYS = (
     "FIN_BACKUP_DIR",
     "FIN_BACKUP_KEEP",
     "FIN_EXPORT_DIR",
+    "FIN_WEB_HOSTNAME",
 )
 
 _TERMINAL_KEYS = ("FORCE_COLOR", "NO_COLOR", "TTY_COMPATIBLE", "TTY_INTERACTIVE")
diff --git a/tests/e2e/test_cli.py b/tests/e2e/test_cli.py
index 36629f7..116fb0e 100644
--- a/tests/e2e/test_cli.py
+++ b/tests/e2e/test_cli.py
@@ -3,6 +3,7 @@ from typer.testing import CliRunner
 from finances.cli.main import app
 from finances.config import Settings, get_settings
 from finances.db.migrate import head_revision
+from finances.web.login import set_password
 
 runner = CliRunner(env={"COLUMNS": "200"})
 HEAD = head_revision()
@@ -62,6 +63,7 @@ def test_db_upgrade_twice_is_fine(tmp_settings: Settings) -> None:
 
 def test_doctor_passes_after_an_upgrade(tmp_settings: Settings) -> None:
     runner.invoke(app, ["db", "upgrade"])
+    set_password("correct horse battery", None)
     result = runner.invoke(app, ["doctor"])
     assert result.exit_code == 0
     assert f"{HEAD} OK" in result.stdout
diff --git a/tests/integration/test_web_pages.py b/tests/integration/test_web_pages.py
index 5545563..5e7631f 100644
--- a/tests/integration/test_web_pages.py
+++ b/tests/integration/test_web_pages.py
@@ -332,6 +332,8 @@ def test_sync_status_when_the_keychain_fails(household: TestClient) -> None:
         priority = 1
 
         def get_password(self, service: str, username: str) -> str | None:
+            if service == "finances-web":
+                return None
             raise keyring.errors.KeyringLocked("locked")
 
         def set_password(self, service: str, username: str, password: str) -> None:
diff --git a/tests/integration/test_web_sync_setup.py b/tests/integration/test_web_sync_setup.py
index 8cdd17a..3858ccf 100644
--- a/tests/integration/test_web_sync_setup.py
+++ b/tests/integration/test_web_sync_setup.py
@@ -172,6 +172,8 @@ class BrokenKeyring(keyring.backend.KeyringBackend):
     priority = 1
 
     def get_password(self, service: str, username: str) -> str | None:
+        if service == "finances-web":
+            return None
         raise keyring.errors.KeyringError("locked")
 
     def set_password(self, service: str, username: str, password: str) -> None:
diff --git a/tests/unit/test_diagnostics.py b/tests/unit/test_diagnostics.py
index 6f20485..1bcd631 100644
--- a/tests/unit/test_diagnostics.py
+++ b/tests/unit/test_diagnostics.py
@@ -55,7 +55,7 @@ def test_database_url_is_masked(tmp_settings: Settings, tmp_path: Path) -> None:
     assert "***" in checks[3][2]
 
 
-def test_there_are_five_checks_in_order(tmp_settings: Settings) -> None:
+def test_there_are_eight_checks_in_order(tmp_settings: Settings) -> None:
     names = [name for name, _ok, _detail in run_checks(tmp_settings)]
     assert names == [
         "Python version",
@@ -63,6 +63,9 @@ def test_there_are_five_checks_in_order(tmp_settings: Settings) -> None:
         "Data dir",
         "Database URL",
         "Database schema",
+        "Web address",
+        "Web password",
+        "Tailscale name",
     ]
 
 
diff --git a/tests/unit/test_session.py b/tests/unit/test_session.py
index a452d43..48c9ee3 100644
--- a/tests/unit/test_session.py
+++ b/tests/unit/test_session.py
@@ -140,14 +140,15 @@ def test_a_keychain_error_on_session_key_is_503(
     assert (response.status_code, response.text) == (503, "could not use the system keychain")
 
 
-def test_a_keychain_error_on_has_password_lets_the_page_through(
+def test_a_keychain_error_on_has_password_closes_the_site(
     client: TestClient, monkeypatch: pytest.MonkeyPatch
 ) -> None:
     def boom() -> bool:
         raise ValueError("could not use the system keychain")
 
     monkeypatch.setattr("finances.web.session.has_password", boom)
-    assert client.get("/", follow_redirects=False).status_code == 200
+    response = client.get("/", follow_redirects=False)
+    assert (response.status_code, response.text) == (503, "could not use the system keychain")
 
 
 def test_a_cookie_from_before_a_password_change_is_refused(guarded: TestClient) -> None:
```

## Given tests

11 tests in two files. Do not change them. Two (`test_the_name_is_served_only_when_set`, `test_cookies_on_this_mac_are_not_secure`) are guards that pass today and must still pass.

`tests/integration/test_web_tailscale.py`

```python
import keyring
import keyring.backend
import keyring.errors
import pytest
from fastapi.testclient import TestClient

from finances.config import Settings, get_settings
from finances.db.migrate import upgrade_to_head
from finances.web.app import create_app
from finances.web.login import set_password
from tests.support import WEB_PORT

NAME = "mac.tail1234.ts.net"
RIGHT = "correct horse battery"


@pytest.fixture
def named(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("FIN_WEB_HOSTNAME", NAME)
    get_settings.cache_clear()
    upgrade_to_head()
    return get_settings()


def remote() -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"https://{NAME}")


def here() -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


def cookies(response) -> list[str]:
    return response.headers.get_list("set-cookie")


def test_the_name_is_served_only_when_set(tmp_settings: Settings) -> None:
    upgrade_to_head()
    refused = remote().get("/login")
    assert (refused.status_code, refused.text) == (400, "Bad host")


def test_the_name_and_no_other(named: Settings) -> None:
    client = remote()
    assert client.get("/login").status_code == 200
    assert client.get("/login", headers={"host": f"{NAME}:443"}).status_code == 200
    assert client.get("/login", headers={"host": "other.tail1234.ts.net"}).status_code == 400


def test_cookies_are_secure_over_tailscale(named: Settings) -> None:
    set_password(RIGHT, None)
    client = remote()
    page = client.get("/login")
    assert [c for c in cookies(page) if c.startswith("fin_csrf=")][0].count("Secure") == 1
    login = client.post(
        "/login",
        data={"csrf": client.cookies["fin_csrf"], "password": RIGHT, "next": "/"},
        headers={"origin": f"https://{NAME}"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert "Secure" in [c for c in cookies(login) if c.startswith("fin_session=")][0]
    again = client.get("/", follow_redirects=False)
    assert again.status_code == 200
    assert "Secure" in [c for c in cookies(again) if c.startswith("fin_session=")][0]


def test_cookies_on_this_mac_are_not_secure(named: Settings) -> None:
    page = here().get("/login")
    assert all("Secure" not in c for c in cookies(page))


def test_a_request_forwarded_over_https(named: Settings) -> None:
    page = here().get("/login", headers={"x-forwarded-proto": "https"})
    assert "Secure" in [c for c in cookies(page) if c.startswith("fin_csrf=")][0]


def test_the_form_origin(named: Settings) -> None:
    set_password(RIGHT, None)
    client = remote()
    client.get("/login")
    data = {"csrf": client.cookies["fin_csrf"], "password": RIGHT, "next": "/"}
    good = client.post(
        "/login", data=data, headers={"origin": f"https://{NAME}"}, follow_redirects=False
    )
    assert good.status_code == 303
    bad = client.post(
        "/login", data=data, headers={"origin": "https://evil.example"}, follow_redirects=False
    )
    assert (bad.status_code, bad.text) == (403, "Bad origin")


class Broken(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringLocked("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.PasswordSetError("no")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.PasswordDeleteError("no")


def test_a_broken_keychain_closes_the_site(named: Settings) -> None:
    previous = keyring.get_keyring()
    keyring.set_keyring(Broken())
    try:
        client = remote()
        for path in ("/", "/reports", "/login"):
            response = client.get(path, follow_redirects=False)
            assert (response.status_code, response.text) == (
                503,
                "could not use the system keychain",
            ), path
        assert client.get("/static/app.css").status_code == 200
    finally:
        keyring.set_keyring(previous)


def test_the_setting_is_a_host_name(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert Settings(web_hostname="Mac.Tail1234.TS.NET").web_hostname == NAME
    monkeypatch.setenv("FIN_WEB_HOSTNAME", "not a host!")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="FIN_WEB_HOSTNAME must be a host name such as"):
        get_settings()
```

`tests/e2e/test_cli_doctor_web.py`

```python
import keyring
import keyring.backend
import keyring.errors
import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings, get_settings
from finances.web.login import set_password
from tests.support import table_rows

runner = CliRunner(env={"COLUMNS": "200"})


def doctor() -> tuple[int, list[list[str]]]:
    assert runner.invoke(app, ["db", "upgrade"]).exit_code == 0
    result = runner.invoke(app, ["doctor"])
    return result.exit_code, table_rows(result.stdout)[-3:]


def test_doctor_without_a_password(tmp_settings: Settings) -> None:
    assert doctor() == (
        1,
        [
            ["Web address", "http://127.0.0.1:8765 (loopback only)"],
            ["Web password", "not set FAIL (run: fin web password)"],
            ["Tailscale name", "not set (this Mac only)"],
        ],
    )


def test_doctor_ready_for_tailscale(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIN_WEB_HOSTNAME", "mac.tail1234.ts.net")
    get_settings.cache_clear()
    set_password("correct horse battery", None)
    assert doctor() == (
        0,
        [
            ["Web address", "http://127.0.0.1:8765 (loopback only)"],
            ["Web password", "set OK"],
            ["Tailscale name", "mac.tail1234.ts.net"],
        ],
    )


class Broken(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringLocked("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.PasswordSetError("no")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.PasswordDeleteError("no")


def test_doctor_with_a_broken_keychain(tmp_settings: Settings) -> None:
    previous = keyring.get_keyring()
    keyring.set_keyring(Broken())
    try:
        code, rows = doctor()
    finally:
        keyring.set_keyring(previous)
    assert (code, rows[1]) == (1, ["Web password", "cannot read the Keychain FAIL"])
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_web_tailscale_more.py`:

- `over_https` for the name with a port, another name, `X-Forwarded-Proto: http`, and no header at all;
- a `FIN_WEB_HOSTNAME` with a leading dot, with a space, and with one label only (`mac`) is refused; `mac-studio.tail1234.ts.net` is kept;
- with no name set, the origin `https://mac.tail1234.ts.net` is refused (`Bad origin`);
- a logout through Tailscale deletes the session cookie (the next page asks for the login);
- `fin doctor` on another `FIN_WEB_PORT` shows that port in `Web address`.

## Rules for this phase

- The app still binds to 127.0.0.1 only; nothing in this phase listens elsewhere or starts Tailscale.
- Fail closed: when the Keychain cannot answer, no page but the static files is served.
- `docs/remote-access.md` and the given scripts are the architect's; the coder does not change them.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files above, 11 tests; at least N + 11 passed in all;
- `git diff --stat HEAD -- tests` lists only the six files of the given diff;
- `bash -n scripts/install-web-service.sh scripts/uninstall-web-service.sh` prints nothing;
- `git grep -nF -e "0.0.0.0" -e 'host=""' -- src/finances ':!src/finances/web/static'` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.config --cov=finances.diagnostics --cov=finances.web.app --cov=finances.web.forms --cov=finances.web.render --cov=finances.web.routes.login --cov=finances.web.session --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 20c: reaching the site through Tailscale (YYYY-MM-DD)`.
