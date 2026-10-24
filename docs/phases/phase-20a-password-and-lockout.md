# Phase 20a: the household password and the lockout

## Goal

The first part of Phase 20 (remote access), with the owner's decisions (2026-10-24): one household password, its scrypt hash in the macOS Keychain, set and changed with `fin web password`; an escalating lockout; `fin web unlock` to clear it, which also needs the password. After this phase:

- `fin web password` sets the first password, or changes it after the current one is given; a change also replaces the key that will sign sessions (20b), so every device logs in again;
- a pure rule hashes and checks a password and gives the lockout's length: 5 wrong in a row lock the login for 1 hour, 10 for 1 day, and every 3 more (13, 16, …) for 3 days; tries during a lock are refused without being checked or counted; a right password resets the count;
- `fin web unlock`, at the Mac, clears the lock when given the password;
- `fin web serve` refuses to start until a password is set.

Nothing on the web changes yet: 20b adds the login page and puts every page behind it; 20c reaches the site through Tailscale Serve; 20d asks for the password again before restoring or deleting a backup and linking or unlinking SimpleFIN.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/sync/links.py` (the Keychain through `keyring`, its errors, `KEYCHAIN_SERVICE`), `tests/conftest.py` (`MemoryKeyring`: every test has an in-memory Keychain)
- `src/finances/cli/web.py` (`serve`), `src/finances/cli/sync.py` (a hidden `typer.prompt`), `src/finances/cli/common.py` (`fail`)

## Starting state

N is `3847` when Phase 30d is the last phase built. The newest migration is `0021`; this phase adds none and keeps nothing in the database. The lockout is kept in the Keychain beside the password, so a restart does not clear it.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/login.py` (new) | `PASSWORD_MIN`, `PASSWORD_MAX`, `check_new_password`, `hash_password`, `verify_password`, `lock_for` (R1, R2) |
| `src/finances/web/login.py` (new) | the Keychain store: `KEYCHAIN_SERVICE`, `Attempt`, `has_password`, `check_password`, `set_password`, `attempt`, `unlock`, `session_key` (R3 to R6) |
| `src/finances/cli/web.py` | `fin web password`, `fin web unlock`; `serve` refuses with no password (R7 to R9) |
| `tests/e2e/test_cli_web.py` | the given diff (R10) |
| `tests/unit/test_login_rules.py`, `tests/integration/test_web_login_store.py`, `tests/e2e/test_cli_web_password.py` | new: given |
| `tests/integration/test_web_login_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Anything on the web: the login page, sessions, the gate on every page (20b); Tailscale, the host check, `Secure` cookies, `fin doctor` (20c); asking again before sensitive actions (20d).
- A password per person, a password in a setting or a file, recovering a forgotten password (the runbook in 20c says to delete the Keychain item and set a new one).
- Logging or recording logins in the audit trail.

## Dependencies

None new: `hashlib.scrypt`, `hmac`, and `secrets` from the standard library.

## Design

```python
# src/finances/domain/login.py (imports only the standard library and finances.domain)
PASSWORD_MIN = 12
PASSWORD_MAX = 200
def check_new_password(text: str) -> str: ...            # the text, or ValueError
def hash_password(password: str, salt: bytes) -> str: ...
# "scrypt$16384$8$1$<salt hex>$<key hex>": hashlib.scrypt of the UTF-8 password, n=16384, r=8, p=1, dklen=32
def verify_password(password: str, stored: str) -> bool: ...  # False for any stored text it cannot read
def lock_for(failures: int) -> timedelta | None: ...

# src/finances/web/login.py
KEYCHAIN_SERVICE = "finances-web"   # items: "password", "session-key", "lockout"

@dataclass(frozen=True)
class Attempt:
    ok: bool
    locked_until: datetime | None   # set while the login is locked

def has_password() -> bool: ...
def check_password(password: str) -> bool: ...          # no lockout counting
def set_password(new: str, current: str | None) -> None: ...
def attempt(password: str, now: datetime) -> Attempt: ...
def unlock(password: str) -> None: ...
def session_key() -> str | None: ...                     # 64 hex characters, or None
```

| Command | Asks (hidden) | Prints |
|---|---|---|
| `fin web password` | `Current password` (only when one is set, and checked before anything else), then `New password` with `typer.prompt`'s confirmation | `Password saved; every session has ended.` |
| `fin web unlock` | `Password` | `The login is unlocked.` |
| `fin web serve` | nothing | refuses with no password, before printing anything, otherwise as today |

A refusal is `fail(message)`: `Error: <message>` on stderr, exit code 1.

## Requirements

### The rule

- **R1.** `check_new_password` refuses a text outside `PASSWORD_MIN` to `PASSWORD_MAX` characters (`a password is 12 to 200 characters`) and returns it otherwise, unchanged (spaces kept). `hash_password` and `verify_password` as designed; `verify_password` compares with `hmac.compare_digest` and never raises.
- **R2.** `lock_for` gives 1 hour at 5 failures, 1 day at 10, 3 days at 13 and every third failure after (16, 19, …), and None otherwise.

### The store

- **R3.** `set_password` refuses, when a password is set, a `current` that is None or wrong (`the current password is wrong`); then `check_new_password`; then stores `hash_password(new, a new 16-byte random salt)`, a new session key (`secrets.token_hex(32)`), and an empty lockout. With no password set, `current` is not used. `has_password`, `check_password`, and `session_key` read the Keychain.
- **R4.** `attempt`, when the login is locked at `now` (its lock ends later than `now`), returns `Attempt(False, the end)` without checking the password or counting. Otherwise a right password sets the count to 0 and returns `Attempt(True, None)`; a wrong one adds 1 and, when `lock_for(count)` is not None, locks until `now` plus it, returning `Attempt(False, that end)`, else `Attempt(False, None)`. The count and the end are kept in the Keychain.
- **R5.** `unlock` refuses with no password set (`no password is set; run fin web password`) and a wrong password (`wrong password`), and otherwise clears the lock and the count.
- **R6.** Every Keychain failure is a `ValueError` (`could not use the system keychain`). No message, log line, or return value holds a password, a hash, or the session key.

### The commands

- **R7.** `fin web password` as designed: the current password is asked and checked with `check_password` before the new one is asked.
- **R8.** `fin web unlock` as designed.
- **R9.** `fin web serve` refuses with no password (`set a password first: fin web password`) before printing or starting anything.
- **R10.** Apply the given diff to `tests/e2e/test_cli_web.py` (its serving fixture sets a password). No other earlier test changes.

## Given diff to earlier tests

```text
diff --git a/tests/e2e/test_cli_web.py b/tests/e2e/test_cli_web.py
index 71d1fdd..4f3e76a 100644
--- a/tests/e2e/test_cli_web.py
+++ b/tests/e2e/test_cli_web.py
@@ -4,13 +4,16 @@ from typer.testing import CliRunner
 from finances.cli import web as web_module
 from finances.cli.main import app
 from finances.config import Settings, get_settings
+from finances.web.login import set_password
 
 runner = CliRunner(env={"COLUMNS": "200"})
 
 
 @pytest.fixture
 def served(monkeypatch: pytest.MonkeyPatch) -> list[tuple[object, dict]]:
-    """Replace uvicorn.run so that no server starts; remember how it was called."""
+    """Replace uvicorn.run so that no server starts; remember how it was called. A password
+    is set, since serving needs one."""
+    set_password("correct horse battery", None)
     calls: list[tuple[object, dict]] = []
 
     def fake_run(app: object, **options: object) -> None:
```

## Given tests

35 tests in three files. Do not change them. `tests/unit/test_login_rules.py` covers every line and branch of `domain/login.py`.

`tests/unit/test_login_rules.py`

```python
from datetime import timedelta

import pytest

from finances.domain.login import (
    PASSWORD_MAX,
    PASSWORD_MIN,
    check_new_password,
    hash_password,
    lock_for,
    verify_password,
)

SALT = bytes(range(16))
STORED = (
    "scrypt$16384$8$1$000102030405060708090a0b0c0d0e0f$"
    "e96ec6ba8c63a23698220f37c7fc042925d430c7feadec9ceb04af03cabb9f2f"
)
LENGTH = "a password is 12 to 200 characters"


def test_the_limits() -> None:
    assert (PASSWORD_MIN, PASSWORD_MAX) == (12, 200)


@pytest.mark.parametrize("text", ["x" * 12, "  ünïcödé kept  "])
def test_a_new_password_that_is_kept(text: str) -> None:
    assert check_new_password(text) == text


@pytest.mark.parametrize("text", ["", "x" * 11, "x" * 201])
def test_a_new_password_that_is_refused(text: str) -> None:
    with pytest.raises(ValueError) as raised:
        check_new_password(text)
    assert str(raised.value) == LENGTH


def test_the_hash() -> None:
    assert hash_password("correct horse battery", SALT) == STORED


@pytest.mark.parametrize(
    ("password", "stored", "right"),
    [
        ("correct horse battery", STORED, True),
        ("correct horse batterY", STORED, False),
        ("correct horse battery", "", False),
        ("correct horse battery", "md5$abc", False),
        ("correct horse battery", "scrypt$16384$8$1$zz$00", False),
        ("correct horse battery", STORED.replace("$8$", "$9$"), False),
    ],
)
def test_verifying(password: str, stored: str, right: bool) -> None:
    assert verify_password(password, stored) is right


@pytest.mark.parametrize(
    ("failures", "lock"),
    [
        (0, None),
        (4, None),
        (5, timedelta(hours=1)),
        (6, None),
        (10, timedelta(days=1)),
        (11, None),
        (13, timedelta(days=3)),
        (14, None),
        (16, timedelta(days=3)),
    ],
)
def test_the_lockout_schedule(failures: int, lock: timedelta | None) -> None:
    assert lock_for(failures) == lock
```

`tests/integration/test_web_login_store.py`

```python
import re
from datetime import UTC, datetime, timedelta

import pytest

from finances.web.login import Attempt, attempt, has_password, session_key, set_password, unlock

RIGHT = "correct horse battery"
T0 = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def test_no_password_at_first() -> None:
    assert (has_password(), session_key()) == (False, None)


def test_the_first_password_and_a_change() -> None:
    set_password(RIGHT, None)
    first = session_key()
    assert has_password() and re.fullmatch(r"[0-9a-f]{64}", first or "")
    for current in (None, "not the password"):
        with pytest.raises(ValueError) as raised:
            set_password("another long password", current)
        assert str(raised.value) == "the current password is wrong"
    set_password("another long password", RIGHT)
    assert session_key() != first
    assert attempt("another long password", T0) == Attempt(True, None)


def test_a_short_password_stores_nothing() -> None:
    with pytest.raises(ValueError) as raised:
        set_password("too short", None)
    assert str(raised.value) == "a password is 12 to 200 characters"
    assert has_password() is False


def test_the_lockout() -> None:
    set_password(RIGHT, None)
    for _ in range(4):
        assert attempt("wrong", T0) == Attempt(False, None)
    one_hour = T0 + timedelta(hours=1)
    assert attempt("wrong", T0) == Attempt(False, one_hour)
    for _ in range(3):
        assert attempt("wrong", T0 + timedelta(minutes=30)) == Attempt(False, one_hour)
    assert attempt(RIGHT, T0 + timedelta(minutes=59)) == Attempt(False, one_hour)
    later = T0 + timedelta(minutes=61)
    for _ in range(4):
        assert attempt("wrong", later) == Attempt(False, None)
    one_day = later + timedelta(days=1)
    assert attempt("wrong", later) == Attempt(False, one_day)
    after = one_day + timedelta(minutes=1)
    for _ in range(2):
        assert attempt("wrong", after) == Attempt(False, None)
    assert attempt("wrong", after) == Attempt(False, after + timedelta(days=3))
    free = after + timedelta(days=3, minutes=1)
    assert attempt(RIGHT, free) == Attempt(True, None)
    for _ in range(4):
        assert attempt("wrong", free) == Attempt(False, None)


def test_unlock_needs_the_password() -> None:
    with pytest.raises(ValueError) as raised:
        unlock(RIGHT)
    assert str(raised.value) == "no password is set; run fin web password"
    set_password(RIGHT, None)
    for _ in range(5):
        attempt("wrong", T0)
    with pytest.raises(ValueError) as raised:
        unlock("wrong")
    assert str(raised.value) == "wrong password"
    assert attempt(RIGHT, T0) == Attempt(False, T0 + timedelta(hours=1))
    unlock(RIGHT)
    assert attempt(RIGHT, T0) == Attempt(True, None)
    for _ in range(4):
        assert attempt("wrong", T0) == Attempt(False, None)


def test_a_new_password_clears_the_lockout() -> None:
    set_password(RIGHT, None)
    for _ in range(5):
        attempt("wrong", T0)
    set_password("another long password", RIGHT)
    assert attempt("another long password", T0) == Attempt(True, None)
```

`tests/e2e/test_cli_web_password.py`

```python
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

import finances.cli.web as web_module
from finances.cli.main import app
from finances.config import Settings
from finances.web.login import Attempt, attempt, set_password

RIGHT = "correct horse battery"
runner = CliRunner(env={"COLUMNS": "200"})


def run(*args: str, given: str = ""):
    return runner.invoke(app, list(args), input=given)


def last_line(text: str) -> str:
    return text.strip().splitlines()[-1]


def test_the_first_password(tmp_settings: Settings) -> None:
    result = run("web", "password", given=f"{RIGHT}\n{RIGHT}\n")
    assert result.exit_code == 0
    assert last_line(result.stdout) == "Password saved; every session has ended."
    assert attempt(RIGHT, datetime(2026, 10, 24, tzinfo=UTC)) == Attempt(True, None)


def test_a_change_needs_the_current_password(tmp_settings: Settings) -> None:
    set_password(RIGHT, None)
    wrong = run("web", "password", given="not the password\n")
    assert (wrong.exit_code, wrong.stderr) == (1, "Error: the current password is wrong\n")
    right = run("web", "password", given=f"{RIGHT}\nanother long one\nanother long one\n")
    assert last_line(right.stdout) == "Password saved; every session has ended."


def test_a_short_password(tmp_settings: Settings) -> None:
    result = run("web", "password", given="too short\ntoo short\n")
    assert (result.exit_code, result.stderr) == (1, "Error: a password is 12 to 200 characters\n")


@pytest.mark.parametrize(
    ("ready", "given", "code", "out"),
    [
        (False, f"{RIGHT}\n", 1, "Error: no password is set; run fin web password\n"),
        (True, "not the password\n", 1, "Error: wrong password\n"),
    ],
)
def test_unlock_refused(
    tmp_settings: Settings, ready: bool, given: str, code: int, out: str
) -> None:
    if ready:
        set_password(RIGHT, None)
    result = run("web", "unlock", given=given)
    assert (result.exit_code, result.stderr) == (code, out)


def test_unlock(tmp_settings: Settings) -> None:
    set_password(RIGHT, None)
    for _ in range(5):
        attempt("wrong", datetime(2026, 10, 24, tzinfo=UTC))
    result = run("web", "unlock", given=f"{RIGHT}\n")
    assert (result.exit_code, last_line(result.stdout)) == (0, "The login is unlocked.")
    assert attempt(RIGHT, datetime(2026, 10, 24, tzinfo=UTC)) == Attempt(True, None)


def test_serve_needs_a_password(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    started = []
    monkeypatch.setattr(web_module.uvicorn, "run", lambda *a, **k: started.append(a))
    result = run("web", "serve")
    assert (result.exit_code, result.stderr, result.stdout) == (
        1,
        "Error: set a password first: fin web password\n",
        "",
    )
    assert started == []
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/integration/test_web_login_more.py`:

- the stored hash in the Keychain starts `scrypt$16384$8$1$`, and two passwords set in turn get different salts;
- `check_password` neither counts nor locks: 10 wrong checks, then `attempt` with the right password gives `Attempt(True, None)`;
- a Keychain that raises `keyring.errors.KeyringError` gives `could not use the system keychain` from `set_password` and from `attempt`;
- a lock that ended exactly at `now` is over (the end is not later than `now`);
- `fin web password` with no password set does not ask for a current one.

## Rules for this phase

- The password is never stored, printed, or logged: only its scrypt hash, in the Keychain. The session key stays in the Keychain too.
- `domain/login.py` imports only the standard library and `finances.domain`; the Keychain lives in `web/login.py` only.
- Comparisons of secrets use `hmac.compare_digest`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files above, 35 tests; at least N + 35 passed in all;
- `git diff --stat HEAD -- tests` lists only `tests/e2e/test_cli_web.py`;
- `git grep -n "logging\|print(\|logger" -- src/finances/domain/login.py src/finances/web/login.py` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.login --cov=finances.web.login --cov=finances.cli.web --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 20a: the household password and the lockout (YYYY-MM-DD)`.
