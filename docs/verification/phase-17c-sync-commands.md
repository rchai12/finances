# Verify Phase 17c: SimpleFIN links and the sync commands

Spec: `docs/phases/phase-17c-sync-commands.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder added migration `0005` (`feed_accounts.link`), a `link` parameter to two repository functions and `run_sync`, a transport that refuses redirects, `src/finances/sync/links.py` (link names and the Keychain), and the `fin sync` commands. A block was added to `tests/conftest.py`, `tests/unit/test_transport.py` was replaced, and four test files were given. The coder wrote no tests.

**Do not run any `fin sync` command against the real Keychain or SimpleFIN**, and do not contact any host. The tests and the probe script use an in-memory Keychain, a fake SimpleFIN, and, for the transport, a server on `127.0.0.1` that they start and stop.

Judge the code by what it does, never by how it is written. These are all correct and must not be reported:

- any private helpers and any division of the commands;
- building the opener at import time or on first use, as long as one opener with the refusing redirect handler is used;
- the migration's batch steps in another order, as long as the result and its downgrade are as specified.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

**N** is the passed count before the phase. The coder's entry in `docs/progress.md` states it; it is `1388` when Phase 17b was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 61 passed, 0 failed, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_transport.py tests/integration/test_migration_0005.py tests/unit/test_links.py tests/integration/test_sync_links.py tests/e2e/test_cli_sync.py --no-cov` | exactly `73 passed` |
| the coverage command below | `Required test coverage of 100% reached`, with every module of `finances.sync`, `finances.db`, `finances.domain`, and `finances.cli` at 100% |
| `.venv/bin/python -c "from finances.db.migrate import head_revision; print(head_revision())"` | `0005` |
| `.venv/bin/python -c "import keyring; print(keyring.__name__)"` | `keyring` |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.sync --cov=finances.db --cov=finances.domain --cov=finances.cli --cov-branch --cov-report=term-missing --cov-fail-under=100`

If you can, run the third command once more with the network switched off. The result must be the same.

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M pyproject.toml
 M src/finances/cli/main.py
 M src/finances/db/orm.py
 M src/finances/db/repositories.py
 M src/finances/domain/models.py
 M src/finances/sync/runner.py
 M src/finances/sync/transport.py
 M tests/conftest.py
 M tests/unit/test_transport.py
?? src/finances/cli/sync.py
?? src/finances/db/migrations/versions/0005_feed_links.py
?? src/finances/sync/links.py
?? tests/e2e/test_cli_sync.py
?? tests/integration/test_migration_0005.py
?? tests/integration/test_sync_links.py
?? tests/unit/test_links.py
```

- `git diff HEAD -- pyproject.toml` adds exactly `"keyring>=25",` after `"pypdf>=5",`.
- `git diff HEAD -- tests/conftest.py` adds exactly the given block and its imports.
- `tests/unit/test_transport.py` and the four new test files are identical to the blocks in the spec, apart from trailing whitespace.
- `git diff HEAD -- src/finances/cli/main.py` adds only the import of the sync app and `app.add_typer(sync_app, name="sync")`.
- The shipped migrations `0001` to `0004`, `sync/simplefin.py`, `sync/service.py`, `sync/feed.py`, `ingest/`, the fixtures, and every other existing test are unchanged.

## 3. Requirement checklist

Probe lines are named by how they start. "Every line starting `x`" passes when each such line ends in `ok`.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | migration | gate 4; probe script; read `0005_feed_links.py` | `migration:` lines; `down_revision = "0004"`; batch mode; no import from `finances`; no `server_default`; no raw SQL |
| R2 to R6 | links in the database | gate 4; probe script | the `cli: map ...`, `cli: the same id twice under one link is refused`, `cli: accounts shows this link's mappings only`, and `cli: an account mapped again under another link moves to it` lines |
| R7 to R9 | transport | probe script; the fifth search | every line starting `transport:`; no `urlopen` |
| R10 to R13 | Keychain | probe script; gate 4 | every line starting `links:`, and `cli: link lee, each in its own keychain entry` |
| R14, R15 | link, unlink | probe script | `cli: link kim`, `cli: linking kim again needs --replace`, `cli: a link name with capitals is refused`, `cli: unlink kim`, `cli: unlinking it twice fails` |
| R16 | accounts | probe script | `cli: accounts shows this link's mappings only` |
| R17 | map | probe script | the lines starting `cli: map` |
| R18, R19 | run | probe script | `cli: run pulls both links ...`, `cli: run of one link shows its drift`, `cli: days beyond 90 are refused`, `cli: a link without its keychain entry fails, the next one still runs` |
| R20 | status | probe script | `cli: status, one row per mapping ...` |
| R22 | no network, no real Keychain | gate 4 (`test_conftest_keeps_tests_off_the_network`); read the conftest block | the guard and the in-memory Keychain are autouse |
| secrets | nothing printed | probe script; read `cli/sync.py` | `cli: no credential ever printed`; the prompt uses `hide_input=True`; no `echo` of the token or the access URL |

Run each of these searches. Each must print nothing.

`git grep -n --untracked -E "^ *(import|from) +(requests|httpx|urllib|socket|http|aiohttp|ssl|ftplib|smtplib)" -- src/finances ':!src/finances/sync' ':!src/finances/config.py'`

`git grep -n --untracked -E "^ *(import|from) +(urllib\.request|urllib\.error|socket|http\.client|ssl)" -- src/finances ':!src/finances/sync/transport.py'`

`git grep -n --untracked -e "urlopen" -- src/finances`

`git grep -n --untracked -e "keyring" -- src/finances ':!src/finances/sync/links.py'`

`git grep -n --untracked -E "float|(^|[^_a-zA-Z.])print\(|logging" -- src/finances/sync src/finances/cli/sync.py`

`git grep -n --untracked -E "finances\.(ingest|cli)" -- src/finances/sync src/finances/db src/finances/domain`

Then read `transport.py`: the redirect handler's `redirect_request` returns `None`; nothing creates an SSL context, sets `check_hostname`, or passes `context=`.

## 4. Independent probes

The script tells a two-person story with its own names, ids, and amounts: two links, three mappings (one SimpleFIN id under both links), a sync of both links, a second sync with drift, status, unlink, and a run with one link missing. It replaces the transport with a fake SimpleFIN and the Keychain with one in memory while it runs, uses a temporary data folder, and restores everything afterwards. It also starts a server on `127.0.0.1` to check that a redirect is refused.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`. A line that says a section `ran to the end (stopped by ...)` and ends in `FAIL` means the code raised where it should not have; report it with the exception named on that line.

```python
import base64
import http.server
import json
import os
import socketserver
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path

import keyring
import keyring.backend
import keyring.errors

failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def outcome(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__, str(exc))


def section(name, function):
    try:
        function()
    except Exception as exc:  # noqa: BLE001
        check(f"{name}: ran to the end (stopped by {type(exc).__name__}: {exc})", False)


class MemoryKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.passwords = {}

    def get_password(self, service, username):
        return self.passwords.get((service, username))

    def set_password(self, service, username, password):
        self.passwords[(service, username)] = password

    def delete_password(self, service, username):
        if (service, username) not in self.passwords:
            raise keyring.errors.PasswordDeleteError("missing")
        del self.passwords[(service, username)]


KIM = "https://kim-user:kim-pass@bridge.simplefin.org/simplefin"
LEE = "https://lee-user:lee-pass@beta-bridge.simplefin.org/simplefin"


def day_stamp(days_ago):
    today = datetime.now(UTC).date()
    return int(datetime(today.year, today.month, today.day, 15, tzinfo=UTC).timestamp()) - days_ago * 86400


def account(account_id, balance, *moves):
    return {"id": account_id, "name": f"Probe {account_id}", "conn_id": "K", "currency": "USD", "balance": balance,
            "balance-date": day_stamp(0),
            "transactions": [{"id": feed_id, "posted": day_stamp(days_ago), "amount": amount, "description": "PROBE SHOP"} for feed_id, days_ago, amount in moves]}


class Bridge:
    def __init__(self):
        self.claims = {}
        self.answers = {}
        self.calls = []

    def __call__(self, method, url, headers):
        self.calls.append((method, url))
        if method == "POST":
            return 200, self.claims[url].encode()
        return 200, json.dumps({"errlist": [], "connections": [{"conn_id": "K", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}], "accounts": self.answers[headers["Authorization"]]}).encode()

    def answer(self, access, *accounts):
        user, password = access.split("//")[1].split("@")[0].split(":")
        self.answers["Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()] = list(accounts)


def cells(output):
    return [[cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]] for line in output.splitlines() if line.startswith(("│", "┃"))]


def cli_checks():
    from typer.testing import CliRunner

    from finances.cli.main import app
    from finances.config import get_settings
    from finances.sync import transport

    store = MemoryKeyring()
    previous_keyring = keyring.get_keyring()
    keyring.set_keyring(store)
    bridge = Bridge()
    real_transport = transport.urllib_transport
    transport.urllib_transport = bridge
    saved = os.environ.get("FIN_DATA_DIR")
    folder = tempfile.TemporaryDirectory()
    os.environ["FIN_DATA_DIR"] = folder.name
    get_settings.cache_clear()
    runner = CliRunner(env={"COLUMNS": "200"})

    def fin(*args, input=None):
        return runner.invoke(app, list(args), input=input)

    try:
        check("cli: db upgrade", fin("db", "upgrade").exit_code == 0)
        for name, kind in (("Kim Card", "credit_card"), ("Kim Checking", "checking"), ("Lee Card", "credit_card")):
            fin("accounts", "add", "--name", name, "--institution", "Probe Bank", "--type", kind)
        claim_kim = "https://bridge.simplefin.org/simplefin/claim/PROBE-K"
        claim_lee = "https://beta-bridge.simplefin.org/simplefin/claim/PROBE-L"
        bridge.claims = {claim_kim: KIM, claim_lee: LEE}
        token = base64.b64encode(claim_kim.encode()).decode()
        linked = fin("sync", "link", "--link", "kim", input=token + "\n")
        check("cli: link kim", linked.exit_code == 0 and linked.stdout.endswith("Linked kim.\n") and token not in linked.output)
        lee = fin("sync", "link", "--link", "lee", input=base64.b64encode(claim_lee.encode()).decode() + "\n")
        check("cli: link lee, each in its own keychain entry", lee.exit_code == 0 and store.passwords == {("finances-simplefin", "kim"): KIM, ("finances-simplefin", "lee"): LEE})
        again = fin("sync", "link", "--link", "kim", input=token + "\n")
        check("cli: linking kim again needs --replace", again.exit_code == 1 and "use --replace" in again.stderr)
        check("cli: a link name with capitals is refused", fin("sync", "link", "--link", "Kim", input=token + "\n").exit_code == 1)
        for account_name, feed, link in (("Kim Card", "SF-1", "kim"), ("Kim Checking", "SF-2", "kim"), ("Lee Card", "SF-1", "lee")):
            mapped = fin("sync", "map", "--account", account_name, "--feed-account", feed, "--link", link)
            check(f"cli: map {account_name} under {link}", mapped.exit_code == 0 and mapped.stdout == f'Mapped {feed} to "{account_name}" under link {link}.\n')
        check("cli: the same id twice under one link is refused", fin("sync", "map", "--account", "Lee Card", "--feed-account", "SF-2", "--link", "kim").stderr == "Error: feed account is already mapped to another account\n")
        bridge.answer(KIM, account("SF-1", "-20.00", ("K-1", 2, "-20.00")), account("SF-2", "500.00", ("K-2", 1, "500.00")))
        bridge.answer(LEE, account("SF-1", "-7.25", ("L-1", 1, "-7.25")))
        listed = fin("sync", "accounts", "--link", "kim")
        check("cli: accounts shows this link's mappings only", cells(listed.stdout)[1:] == [["SF-1", "Probe Bank", "Probe SF-1", "USD", "Kim Card"], ["SF-2", "Probe Bank", "Probe SF-2", "USD", "Kim Checking"]])
        pulled = fin("sync", "run")
        rows = cells(pulled.stdout)
        check("cli: run pulls both links, one row per account", pulled.exit_code == 0 and [row[:4] for row in rows[1:]] == [["kim", "Kim Card", "SF-1", "1"], ["kim", "Kim Checking", "SF-2", "1"], ["lee", "Lee Card", "SF-1", "1"]])
        bridge.answer(LEE, account("SF-1", "-9.25", ("L-1", 1, "-7.25")))
        drift = fin("sync", "run", "--link", "lee")
        check("cli: run of one link shows its drift", cells(drift.stdout)[1:] == [["lee", "Lee Card", "SF-1", "0", "0", "0", "1", "-$2.00", ""]])
        status = cells(fin("sync", "status").stdout)
        check("cli: status, one row per mapping with its keychain entry and drift", [row[:4] + row[5:] for row in status[1:]] == [["kim", "Kim Card", "SF-1", "yes", datetime.now(UTC).date().isoformat(), ""], ["kim", "Kim Checking", "SF-2", "yes", datetime.now(UTC).date().isoformat(), ""], ["lee", "Lee Card", "SF-1", "yes", datetime.now(UTC).date().isoformat(), "-$2.00"]])
        check("cli: days beyond 90 are refused", fin("sync", "run", "--days", "91").exit_code == 2)
        check("cli: unlink kim", fin("sync", "unlink", "--link", "kim").stdout == "Unlinked kim.\n" and ("finances-simplefin", "kim") not in store.passwords)
        check("cli: unlinking it twice fails", fin("sync", "unlink", "--link", "kim").stderr == "Error: link kim is not set up\n")
        failing = fin("sync", "run")
        check("cli: a link without its keychain entry fails, the next one still runs", failing.exit_code == 1 and failing.stderr == "Error: link kim is not set up (run: fin sync link --link kim)\n" and [row[0] for row in cells(failing.stdout)[1:]] == ["lee"])
        moved = fin("sync", "map", "--account", "Kim Checking", "--feed-account", "SF-9", "--link", "lee")
        check("cli: an account mapped again under another link moves to it", moved.exit_code == 0 and [row[:3] for row in cells(fin("sync", "status").stdout)[1:]] == [["kim", "Kim Card", "SF-1"], ["lee", "Kim Checking", "SF-9"], ["lee", "Lee Card", "SF-1"]])
        check("cli: no credential ever printed", all("kim-pass" not in text and "lee-pass" not in text for text in (linked.output, pulled.output, status and "", failing.output)))
    finally:
        transport.urllib_transport = real_transport
        keyring.set_keyring(previous_keyring)
        if saved is None:
            os.environ.pop("FIN_DATA_DIR", None)
        else:
            os.environ["FIN_DATA_DIR"] = saved
        get_settings.cache_clear()
        from finances.db.engine import get_engine
        try:
            get_engine().dispose()
        except Exception:  # noqa: BLE001
            pass
        folder.cleanup()


class Handler(http.server.BaseHTTPRequestHandler):
    seen = []

    def do_GET(self):
        Handler.seen.append((self.path, self.headers.get("Authorization")))
        if self.path == "/away":
            self.send_response(301)
            self.send_header("Location", "/elsewhere")
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

    def log_message(self, *args):
        return


class LocalServer(http.server.HTTPServer):
    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "127.0.0.1", self.server_address[1]


def transport_checks():
    from finances.sync.transport import urllib_transport

    server = LocalServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        check("transport: a plain request still works", urllib_transport("GET", base + "/here", {}) == (200, b"ok"))
        Handler.seen = []
        check("transport: a redirect comes back as its status", urllib_transport("GET", base + "/away", {"Authorization": "Basic probe"}) == (301, b""))
        check("transport: the redirected address is never asked, so the credentials go nowhere else", Handler.seen == [("/away", "Basic probe")])
    finally:
        server.shutdown()
        server.server_close()


def migration_checks():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    import finances.db
    from finances.db.engine import get_engine
    from finances.db.migrate import head_revision

    check("migration: the newest revision is 0005", head_revision() == "0005")
    with tempfile.TemporaryDirectory() as folder:
        url = f"sqlite:///{(Path(folder) / 'probe.db').as_posix()}"
        config = Config()
        config.set_main_option("script_location", str(Path(finances.db.__file__).parent / "migrations"))
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "0004")
        engine = get_engine(url)
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO accounts (name, institution, type, currency, is_active, created_at) VALUES ('Probe', 'Probe Bank', 'checking', 'USD', 1, '2027-01-01 00:00:00')"))
            connection.execute(text("INSERT INTO feed_accounts (account_id, provider_account_id) VALUES (1, 'SF-OLD')"))
        engine.dispose()
        command.upgrade(config, "0005")
        engine = get_engine(url)
        with engine.connect() as connection:
            found = connection.execute(text("SELECT account_id, provider_account_id, link FROM feed_accounts")).all()
        engine.dispose()
        check("migration: a mapping made before 0005 belongs to the default link", [tuple(row) for row in found] == [(1, "SF-OLD", "default")])


def links_checks():
    from finances.sync import links

    check("links: the keychain service name", links.KEYCHAIN_SERVICE == "finances-simplefin")
    for name, ok in (("kim", True), ("lee-2", True), ("k" * 30, True), ("k" * 31, False), ("Kim", False), ("2kim", False), ("kim lee", False), ("", False)):
        result = outcome(links.validate_link_name, name)
        check(f"links: the name {name[:12]!r} is {'usable' if ok else 'refused'}", (result == name) if ok else (isinstance(result, tuple) and result[0] == "ValueError"))


section("transport", transport_checks)
section("migration", migration_checks)
section("links", links_checks)
section("cli", cli_checks)
print("FAILURES", failures)
```

## 5. The coder's tests

There are none to review. Confirm that the coder added no test file and edited no existing test beyond `tests/conftest.py` and the replaced `tests/unit/test_transport.py` (section 2). Then, for each change below, say which given test would fail, by reading the tests. If none would, that is a finding.

1. `fin sync run` stops at the first link that fails.
2. `fin sync status` takes `Drift` from the latest pull even when it has no balance.
3. `fin sync accounts` shows mappings of every link in `Mapped to`.
4. `fin sync map` keeps the spaces around the feed account id.
5. `delete_access_url` returns `True` when there was nothing to delete.
6. A `KeyringError` escapes `links.py` unchanged.
7. The transport's timeout is 30 seconds.

## 6. Project rules that apply to this phase

- **Privacy rule 1.** The only network code is `transport.py`; requests refuse redirects; tests cannot reach the network (R22).
- **Secrets.** The access URL is only in the Keychain (`links.py` is the only module that imports `keyring`), and the token is read only through the hidden prompt.
- **Privacy rule 4.** Nothing in `src/finances/sync/` or `cli/sync.py` logs or prints anything but the specified lines.
- **Layering.** `cli/sync.py` writes no query and contains no sync logic.

## 7. Out of scope

Each of these must be absent. Report any that is present.

- People or owners of accounts.
- A change to `fin import statement`.
- A scheduler, a daemon, or a loop in the code.
- Any request to a real host, in code or in tests, and any use of the real Keychain in tests.
- A change to a shipped migration.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 17c: SimpleFIN links and the sync commands (YYYY-MM-DD)` with a real date. "Built" gives N and the passed count. It reports nothing about a real SimpleFIN account. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then three lines:

`Total passed: <the count from section 1>`

`Parts that needed a repair: <none, or Part 1 to Part 5>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the probe line, or the file and line), and what is required. Do not prescribe the code.
