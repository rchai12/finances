# Phase 17c: SimpleFIN links and the sync commands

## Goal

Make the daily feed usable from the command line, for a household of two people with their own SimpleFIN subscriptions.

After this phase:

- `fin sync link --link NAME` asks for a SimpleFIN setup token, claims it, and keeps the access URL in the **macOS Keychain**, one entry per link. A link is a named SimpleFIN subscription: one person's bank logins are not the other's, so each person can have their own.
- `fin sync accounts` lists what SimpleFIN has under a link, `fin sync map` says which SimpleFIN account feeds which of our accounts, `fin sync run` pulls every link, `fin sync status` shows each mapped account's last pull and drift, and `fin sync unlink` forgets a link.
- The same SimpleFIN account id under two links is two different mappings (migration `0005`).
- No request follows a redirect, so the access credentials can only ever reach the host in the access URL. This closes the follow-up raised in Phase 17b.
- Every test runs with the network and the real Keychain out of reach.

## Read first

- `AGENTS.md`: "Privacy rules" (rules 1 and 4), "Architecture rules" (the aggregator token lives in the OS keyring only)
- `docs/architecture.md`: "Privacy boundary", "People"
- `docs/phases/phase-17b-simplefin-sync.md` and the code it produced in `src/finances/sync/`
- `src/finances/cli/importing.py`, `src/finances/cli/listing.py`, `src/finances/cli/common.py`: how commands print, fail, and check the database
- `tests/e2e/test_cli_listing.py`: how command tests read a table

## Starting state

- Phase 17b is committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `1388` when Phase 17b is the last phase built.
- The newest migration is `0004`. `feed_accounts` has a unique constraint on `provider_account_id` alone, so one SimpleFIN account id can be mapped once in the whole database.
- `urllib_transport` opens requests with `urllib.request.urlopen`, which follows redirects and carries the `Authorization` header to the new address.
- The architect has already made three older tests independent of columns added to `feed_accounts` later: `test_the_orm_class_starts_with_the_columns_of_0004` and `test_one_mapping_per_account_and_per_aggregator_account` in `tests/integration/test_migration_0004.py`, and `test_feed_account_fields_in_order_and_frozen` in `tests/integration/test_feed_account_repositories.py`. They pass before and after this phase.
- `keyring` is not installed.
- `finances.sync`, `finances.db`, `finances.domain`, and `finances.cli` are at 100% line and branch coverage.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `pyproject.toml` | one dependency added (below) |
| `src/finances/db/migrations/versions/0005_feed_links.py` | new: `feed_accounts.link` |
| `src/finances/domain/models.py` | `DEFAULT_LINK` added; `FeedAccount` gains `link` as its last field |
| `src/finances/db/orm.py` | `FeedAccountRow` gains `link` and the new unique constraint; `to_feed_account` copies it |
| `src/finances/db/repositories.py` | `map_feed_account` and `list_feed_accounts` gain a `link` parameter |
| `src/finances/sync/runner.py` | `run_sync` gains a `link` keyword |
| `src/finances/sync/transport.py` | requests go through an opener that refuses redirects |
| `src/finances/sync/links.py` | new: link names and the Keychain |
| `src/finances/cli/sync.py` | new: the `fin sync` commands |
| `src/finances/cli/main.py` | the `sync` group registered |
| `tests/conftest.py` | the given block below added |
| `tests/unit/test_transport.py` | replaced by the given file below |
| `tests/integration/test_migration_0005.py`, `tests/unit/test_links.py`, `tests/integration/test_sync_links.py`, `tests/e2e/test_cli_sync.py` | given, do not change |
| `docs/progress.md` | one new entry |

You may add private helpers to the new modules. Do not change any other production file, any other existing test, or the shipped migrations `0001` to `0004`. Existing signatures keep working: every new parameter has a default, so the tests of Phase 17b pass unchanged.

## Out of scope

- People and account owners. Phase 21. A link name is only a label for a SimpleFIN subscription.
- Printing Phase 8's upgraded and dropped counts in `fin import statement`.
- A command that runs on a schedule. Scheduling is done outside the app; the architect documents a `launchd` job separately.
- Listing links that have no mapping. The Keychain cannot be listed, and links are known through their mappings.
- Moving or renaming a link's mappings in bulk, and any cleanup when a link is removed: `unlink` forgets the access URL only, and the mappings stay.
- Any request to a real host, in code or in tests.

## Dependencies

Add `"keyring>=25"` to `dependencies` in `pyproject.toml`, after `"pypdf>=5"`, and install it:

`.venv/bin/python -m pip install -e ".[dev]"`

Nothing else. `keyring` uses the macOS Keychain on this machine; no backend package is needed.

## Design

### The table change (migration `0005`, `down_revision = "0004"`)

`feed_accounts` gains one column, added last:

| Column | Type | Null | Notes |
|---|---|---|---|
| `link` | String(50) | no | the link's name; mappings that exist before the upgrade get `default` |

The unique constraint `uq_feed_accounts_provider_account_id` on (`provider_account_id`) is replaced by `uq_feed_accounts_link_provider_account` on (`link`, `provider_account_id`). `uq_feed_accounts_account_id` stays: an account is fed by one SimpleFIN account at most.

SQLite cannot change constraints in place, so the migration uses Alembic's batch mode (`op.batch_alter_table`), which copies the table. Add the column as nullable, set it to `'default'` on every existing row with a SQLAlchemy Core `update()` (no `server_default`, no dialect-specific SQL), then make it non-nullable and swap the constraint. `downgrade` drops the new constraint and the column and restores the old constraint; it fails, as it should, if two links map the same SimpleFIN id.

### Domain and ORM

```python
# domain/models.py
DEFAULT_LINK = "default"


@dataclass(frozen=True)
class FeedAccount:
    """Which aggregator account feeds one of our accounts, and under which link."""

    id: int
    account_id: int
    provider_account_id: str
    link: str = DEFAULT_LINK
```

`FeedAccountRow.link` is a `String(50)`, not nullable, with the ORM default `DEFAULT_LINK`, declared after `provider_account_id`.

### Repository and sync signatures

```python
def map_feed_account(
    session: Session, account_id: int, provider_account_id: str, link: str = DEFAULT_LINK
) -> FeedAccount: ...


def list_feed_accounts(session: Session, link: str | None = None) -> list[FeedAccount]: ...


def run_sync(
    session: Session,
    access_url: str,
    *,
    today: date,
    transport: Transport,
    days: int = SYNC_DAYS,
    link: str = DEFAULT_LINK,
) -> SyncReport: ...
```

### Links and the Keychain, in `src/finances/sync/links.py`

```python
KEYCHAIN_SERVICE = "finances-simplefin"


def validate_link_name(name: str) -> str: ...
def save_access_url(link: str, access_url: str) -> None: ...
def load_access_url(link: str) -> str | None: ...
def delete_access_url(link: str) -> bool: ...
```

Each access URL is stored with `keyring` under the service `finances-simplefin` and the user name equal to the link's name. It is never written anywhere else.

### The transport

`urllib_transport` keeps its signature and behavior, except that it opens requests with an opener built once by `urllib.request.build_opener(...)` with a redirect handler whose `redirect_request` returns `None`. A `3xx` answer then comes back as an `HTTPError`, which the transport already returns as `(status, b"")`. `urlopen` is no longer used anywhere in the project.

### The commands, in `src/finances/cli/sync.py`

Registered in `main.py` as `app.add_typer(sync_app, name="sync")`, after `transactions`. Help text of the group: `Pull transactions from SimpleFIN.`

| Command | Options |
|---|---|
| `fin sync link` | `--link NAME` (default `default`), `--replace` |
| `fin sync unlink` | `--link NAME` (default `default`) |
| `fin sync accounts` | `--link NAME` (default `default`) |
| `fin sync map` | `--account NAME` (required), `--feed-account ID` (required), `--link NAME` (default `default`) |
| `fin sync run` | `--link NAME` (optional: every link when left out), `--days N` (`1` to `90`, default `30`) |
| `fin sync status` | none |

Every error is printed to standard error as `Error: <message>` and ends the command with exit code 1, as in the other commands. The commands reach the network only through `transport.urllib_transport`, looked up on the module `finances.sync.transport` at the moment of the call (not imported by name), so that tests can replace it. "Today" is the current date in UTC.

## Requirements

### Part 1: links in the database

- **R1.** Migration `0005` changes `feed_accounts` exactly as designed. Every mapping that existed before it belongs to the link `default` afterwards. `downgrade` restores the table of `0004` with its rows.
- **R2.** `FeedAccount` and `FeedAccountRow` are as designed, and `to_feed_account` copies `link`.
- **R3.** `map_feed_account(session, account_id, provider_account_id, link=DEFAULT_LINK)` behaves as in Phase 17b, with "the aggregator account" now meaning that id **under that link**: when that link's id already feeds a different account, it raises the same `ValueError` and changes nothing; the same id under another link is a separate mapping; and when the account is already mapped, its mapping is changed in place, link included, and keeps its id.
- **R4.** `list_feed_accounts(session, link=None)` returns every mapping in id order, or only that link's when a link is given.
- **R5.** `run_sync(..., link=DEFAULT_LINK)` uses only the mappings of its link (R17 to R20 of Phase 17b, with "mapped" meaning mapped under that link). Mappings of other links are never applied or reported.
- **R6.** Code that does not pass a link behaves exactly as in Phase 17b, on the link `default`.

### Part 2: the transport

- **R7.** `urllib_transport` sends each request through one opener built with a redirect handler that refuses every redirect. A `3xx` answer is returned as `(status, b"")`, and the address it points to is never asked.
- **R8.** Everything else is as in Phase 17b: the timeout, the `POST` body, an error status returned without its body, and `SyncError("could not reach the aggregator")` for a failure to connect.
- **R9.** No module in `src/finances/` calls `urlopen`.

### Part 3: links and the Keychain

- **R10.** `validate_link_name(name)` returns the name when it is 1 to 30 characters, each a lowercase ASCII letter, an ASCII digit, or `-`, starting with a letter. Otherwise it raises `ValueError("a link name is 1 to 30 lowercase letters, digits, or hyphens, starting with a letter")`.
- **R11.** `save_access_url(link, url)` stores the URL with `keyring.set_password(KEYCHAIN_SERVICE, link, url)`, replacing an earlier one. `load_access_url(link)` returns `keyring.get_password(KEYCHAIN_SERVICE, link)`, which is `None` when there is none. `delete_access_url(link)` removes it and returns `True`, or returns `False` without deleting when there is none.
- **R12.** All three check the name first with `validate_link_name`; a bad name never reaches the Keychain.
- **R13.** Any `keyring.errors.KeyringError` (a locked or missing Keychain) becomes `SyncError("could not use the system keychain")`, raised from `None`.

### Part 4: the commands

- **R14.** `fin sync link`: checks the name; when the link already has an access URL and `--replace` is not given, fails with `link NAME is already set up; use --replace to set it up again` before asking anything. Otherwise it asks `SimpleFIN setup token` with the input hidden (`typer.prompt(..., hide_input=True)`), claims it with `claim_access_url`, stores the access URL with `save_access_url`, and prints `Linked NAME.`. A `SyncError` is printed as the error and nothing is stored. Neither the token nor the access URL is ever printed.
- **R15.** `fin sync unlink`: checks the name, removes the access URL, and prints `Unlinked NAME.`; when there was none, fails with `link NAME is not set up`. The link's mappings stay.
- **R16.** `fin sync accounts`: checks the database (`require_current_schema`) and the name; with no access URL for the link, fails with `link NAME is not set up (run: fin sync link --link NAME)` without any request. Otherwise it calls `fetch_accounts` once for today only. With no account in the answer it prints `No accounts.`; otherwise a table with the headings `SimpleFIN account`, `Institution`, `Name`, `Currency`, `Mapped to`, one row per account in the answer's order, where `Mapped to` is the name of our account mapped to it **under this link**, or empty. After the table (or `No accounts.`), each message of the answer is printed on its own line as `SimpleFIN: <message>`. A `SyncError` is printed as the error.
- **R17.** `fin sync map`: checks the database and the name. The feed account id has its outer whitespace removed and must then be 1 to 200 characters, else it fails with `feed account id must be 1 to 200 characters`. The account is found with `get_account_by_name` (so case and outer spaces do not matter), else it fails with `account not found`. The `ValueError` of R3 is printed as the error. On success it prints `Mapped ID to "ACCOUNT NAME" under link NAME.`, with the account's stored name.
- **R18.** `fin sync run`: checks the database. With `--link`, it checks that name and runs that link only; without it, it runs every link that has a mapping, in sorted order. With no link to run, it prints `No mapped accounts.` and succeeds. For each link: with no access URL, the error of R16 is printed and the link is skipped; a `SyncError` (from the Keychain or from SimpleFIN) is printed as `Error: link NAME: <message>`, except that the Keychain error of R13 when loading is printed as `Error: could not use the system keychain`, and the link is skipped; otherwise `run_sync` runs with today, `--days`, and the link, in its own database session that is committed. A failing link never stops the next one.
- **R19.** After every link has been tried, `fin sync run` prints, when there is at least one row, one table with the headings `Link`, `Account`, `SimpleFIN account`, `New`, `Changed`, `Removed`, `Same`, `Drift`, `Problem`: one row per `AccountSync`, links in the order run. `Account` is our account's name, or empty when the SimpleFIN account is not mapped. `New`, `Changed`, `Removed`, `Same` are the pull's `inserted`, `updated`, `removed`, `unchanged`, or empty when there was no pull. `Drift` is `format_cents` of the pull's drift, or empty when there is none. `Problem` is the problem, or empty. Then each message of each link is printed as `SimpleFIN (NAME): <message>`. The command ends with exit code 1 when any link was skipped, and 0 otherwise.
- **R20.** `fin sync status`: checks the database. With no mapping it prints `No mapped accounts.`. Otherwise a table with the headings `Link`, `Account`, `SimpleFIN account`, `Keychain`, `Last pull`, `Balance date`, `Drift`, one row per mapping in id order. `Keychain` is `yes` or `no` (whether the link has an access URL), or `unknown` when the Keychain cannot be read. `Last pull` is the `pulled_at` of the account's latest pull as `YYYY-MM-DD HH:MM UTC`, or `never`. `Balance date` and `Drift` come from the account's latest pull **that has a balance**: its balance date in ISO form and `format_cents` of its drift, each empty when there is none.
- **R21.** Every table is printed with `print_table`. Options that Typer validates (`--days` out of range) end with Typer's own usage error, exit code 2.

### Part 5: tests never leave the machine

- **R22.** `tests/conftest.py` gains the given block: an in-memory Keychain installed for every test, and a guard that makes every connection or name lookup to anything but the local machine fail with `AssertionError("a test tried to use the network")`. No test may switch either off for anything but a server on `127.0.0.1`.

## Given code and tests

Add this block to `tests/conftest.py`, after `_TERMINAL_KEYS` and before the fixture `plain_terminal`, together with the imports it needs (`socket`, `keyring`, `keyring.backend`, `keyring.errors`):

```python
class MemoryKeyring(keyring.backend.KeyringBackend):
    """A keychain that lives in memory, so no test reads or writes the real one."""

    priority = 1

    def __init__(self) -> None:
        super().__init__()
        self.passwords: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.passwords.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.passwords[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self.passwords:
            raise keyring.errors.PasswordDeleteError("not found")
        del self.passwords[(service, username)]


_LOCAL_HOSTS = ("127.0.0.1", "::1", "localhost")


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse every connection and name lookup that leaves the machine."""
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def connect(self: socket.socket, address: object) -> object:
        host = address[0] if isinstance(address, tuple) else address
        if host not in _LOCAL_HOSTS:
            raise AssertionError("a test tried to use the network")
        return real_connect(self, address)

    def getaddrinfo(host: object, *args: object, **kwargs: object) -> object:
        if host not in _LOCAL_HOSTS:
            raise AssertionError("a test tried to use the network")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


@pytest.fixture(autouse=True)
def keychain() -> Iterator[MemoryKeyring]:
    """Give every test an empty keychain in memory, never the real one."""
    previous = keyring.get_keyring()
    store = MemoryKeyring()
    keyring.set_keyring(store)
    yield store
    keyring.set_keyring(previous)
```

Replace `tests/unit/test_transport.py` with this file. Its tests run the real transport against a server on `127.0.0.1` that the test starts and stops.

```python
import http.server
import socketserver
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from finances.sync.simplefin import SyncError
from finances.sync.transport import TIMEOUT_SECONDS, urllib_transport


class Handler(http.server.BaseHTTPRequestHandler):
    """A local server: /moved redirects to /target, /fail answers 403 with a body, / answers 200."""

    seen: list[tuple[str, str, str | None]] = []

    def _answer(self) -> None:
        Handler.seen.append((self.command, self.path, self.headers.get("Authorization")))
        if self.path == "/moved":
            self.send_response(302)
            self.send_header("Location", "/target")
            self.end_headers()
        elif self.path == "/fail":
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"SECRET BODY")
        else:
            body = b'{"accounts": []}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    do_GET = _answer
    do_POST = _answer

    def log_message(self, *args: object) -> None:
        return


class LocalServer(http.server.HTTPServer):
    """An HTTP server that skips the reverse name lookup HTTPServer makes when it starts."""

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "127.0.0.1", self.server_address[1]


@pytest.fixture
def server() -> Iterator[str]:
    """A server on 127.0.0.1 only, for this test; nothing leaves the machine."""
    Handler.seen = []
    httpd = LocalServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01})
    thread.daemon = True
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def test_the_timeout_is_a_minute() -> None:
    assert TIMEOUT_SECONDS == 60


def test_a_get_returns_status_and_body(server: str) -> None:
    assert urllib_transport("GET", server + "/", {"Authorization": "Basic abc"}) == (
        200,
        b'{"accounts": []}',
    )
    assert Handler.seen == [("GET", "/", "Basic abc")]


def test_a_post_is_sent_as_a_post(server: str) -> None:
    status, _ = urllib_transport("POST", server + "/claim", {"Content-Length": "0"})
    assert status == 200
    assert Handler.seen == [("POST", "/claim", None)]


def test_a_redirect_is_not_followed_and_the_credentials_go_nowhere_else(server: str) -> None:
    assert urllib_transport("GET", server + "/moved", {"Authorization": "Basic abc"}) == (302, b"")
    assert Handler.seen == [("GET", "/moved", "Basic abc")]


def test_an_error_status_is_returned_without_its_body(server: str) -> None:
    assert urllib_transport("GET", server + "/fail", {}) == (403, b"")


def test_the_timeout_is_passed_to_the_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = []

    class Reply:
        status = 200

        def read(self) -> bytes:
            return b"x"

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_open(self, request, data=None, timeout=None):
        seen.append((request.get_method(), request.data, timeout))
        return Reply()

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)
    assert urllib_transport("GET", "https://bridge.simplefin.org/x", {}) == (200, b"x")
    assert urllib_transport("POST", "https://bridge.simplefin.org/x", {}) == (200, b"x")
    assert seen == [("GET", None, 60), ("POST", b"", 60)]


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("unreachable bridge.simplefin.org user:secret"),
        TimeoutError("timed out"),
        ConnectionResetError("reset"),
        OSError("no route"),
    ],
)
def test_a_failure_to_connect_is_one_constant_error(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def fake_open(self, request, data=None, timeout=None):
        raise error

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)
    with pytest.raises(SyncError) as caught:
        urllib_transport("GET", "https://bridge.simplefin.org/x", {})
    assert str(caught.value) == "could not reach the aggregator"
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


def test_urlopen_is_not_used(monkeypatch: pytest.MonkeyPatch, server: str) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("urlopen follows redirects; the transport must not use it")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    assert urllib_transport("GET", server + "/", {})[0] == 200


def test_conftest_keeps_tests_off_the_network() -> None:
    with pytest.raises(AssertionError) as caught:
        urllib_transport("GET", "https://bridge.simplefin.org/x", {})
    assert str(caught.value) == "a test tried to use the network"
```

Create these four files exactly as shown and do not change them. If one of their tests fails, the production code is wrong. Together with the existing tests they reach every line and branch of the code this phase changes, so there are no tests for you to write.

`tests/integration/test_migration_0005.py`

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import finances.db
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, Base

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0005_feed_links.py"
COLUMNS = [
    ("id", "INTEGER", False),
    ("account_id", "INTEGER", False),
    ("provider_account_id", "VARCHAR(200)", False),
    ("link", "VARCHAR(50)", False),
]
UNIQUES = [
    ("uq_feed_accounts_account_id", ["account_id"]),
    ("uq_feed_accounts_link_provider_account", ["link", "provider_account_id"]),
]
INSERT = text(
    "INSERT INTO feed_accounts (account_id, provider_account_id, link)"
    " VALUES (:account, :provider, :link)"
)


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


def table_names(url: str) -> list[str]:
    engine = get_engine(url)
    names = sorted(inspect(engine).get_table_names())
    engine.dispose()
    return names


def versions(url: str) -> list[str]:
    engine = get_engine(url)
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT version_num FROM alembic_version")).all()
    engine.dispose()
    return [row[0] for row in rows]


def reflect(url: str, table: str, what: str) -> list:
    engine = get_engine(url)
    result = getattr(inspect(engine), what)(table)
    engine.dispose()
    return result


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def with_accounts(url: str, revision: str) -> None:
    command.upgrade(make_config(url), revision)
    engine = get_engine(url)
    with session_scope(engine) as session:
        for name in ("Test Card", "Test Checking", "Test Savings"):
            session.add(AccountRow(name=name, institution="Test Bank", type="checking"))
    engine.dispose()


@pytest.fixture
def at_0005(url: str) -> str:
    """A database at revision 0005 only, with three accounts."""
    with_accounts(url, "0005")
    return url


def rows(url: str) -> list[tuple]:
    engine = get_engine(url)
    with engine.connect() as connection:
        found = connection.execute(
            text("SELECT id, account_id, provider_account_id, link FROM feed_accounts ORDER BY id")
        ).all()
    engine.dispose()
    return [tuple(row) for row in found]


def test_0005_follows_0004(url: str) -> None:
    scripts = ScriptDirectory.from_config(make_config(url))
    assert scripts.get_revision("0005").down_revision == "0004"
    assert len(scripts.get_heads()) == 1


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source
    assert "batch_alter_table" in source


def test_columns_and_constraints(at_0005: str) -> None:
    assert len(table_names(at_0005)) == 8
    assert versions(at_0005) == ["0005"]
    columns = reflect(at_0005, "feed_accounts", "get_columns")
    assert [(c["name"], str(c["type"]), c["nullable"]) for c in columns] == COLUMNS
    assert [c["default"] for c in columns] == [None, None, None, None]
    primary_key = reflect(at_0005, "feed_accounts", "get_pk_constraint")
    assert (primary_key["name"], primary_key["constrained_columns"]) == ("pk_feed_accounts", ["id"])
    uniques = reflect(at_0005, "feed_accounts", "get_unique_constraints")
    assert sorted((u["name"], u["column_names"]) for u in uniques) == UNIQUES
    keys = reflect(at_0005, "feed_accounts", "get_foreign_keys")
    assert [(k["name"], k["constrained_columns"], k["referred_table"]) for k in keys] == [
        ("fk_feed_accounts_account_id_accounts", ["account_id"], "accounts")
    ]
    assert reflect(at_0005, "feed_accounts", "get_indexes") == []


def test_the_orm_class_matches_the_migrated_table(at_0005: str) -> None:
    declared = Base.metadata.tables["feed_accounts"]
    assert [(c.name, c.nullable) for c in declared.columns] == [
        (name, nullable) for name, _, nullable in COLUMNS
    ]
    found = {
        (constraint.name, tuple(column.name for column in constraint.columns))
        for constraint in declared.constraints
        if type(constraint).__name__ == "UniqueConstraint"
    }
    assert found == {(name, tuple(columns)) for name, columns in UNIQUES}
    assert declared.columns["link"].default.arg == "default"


def test_existing_mappings_become_the_default_link(url: str) -> None:
    with_accounts(url, "0004")
    engine = get_engine(url)
    with session_scope(engine) as session:
        session.execute(
            text("INSERT INTO feed_accounts (account_id, provider_account_id) VALUES (1, 'ACT-1')")
        )
        session.execute(
            text("INSERT INTO feed_accounts (account_id, provider_account_id) VALUES (2, 'ACT-2')")
        )
    engine.dispose()
    command.upgrade(make_config(url), "0005")
    assert rows(url) == [(1, 1, "ACT-1", "default"), (2, 2, "ACT-2", "default")]


def test_the_same_aggregator_id_under_two_links(at_0005: str) -> None:
    engine = get_engine(at_0005)
    with session_scope(engine) as session:
        session.execute(INSERT, {"account": 1, "provider": "ACT-1", "link": "alex"})
        session.execute(INSERT, {"account": 2, "provider": "ACT-1", "link": "sam"})
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.execute(INSERT, {"account": 3, "provider": "ACT-1", "link": "alex"})
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.execute(INSERT, {"account": 1, "provider": "ACT-9", "link": "sam"})
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.execute(
            text("INSERT INTO feed_accounts (account_id, provider_account_id) VALUES (3, 'ACT-3')")
        )
    engine.dispose()
    assert rows(at_0005) == [(1, 1, "ACT-1", "alex"), (2, 2, "ACT-1", "sam")]


def test_downgrade_restores_0004(at_0005: str) -> None:
    engine = get_engine(at_0005)
    with session_scope(engine) as session:
        session.execute(INSERT, {"account": 1, "provider": "ACT-1", "link": "alex"})
        session.execute(INSERT, {"account": 2, "provider": "ACT-2", "link": "sam"})
    engine.dispose()
    command.downgrade(make_config(at_0005), "0004")
    assert versions(at_0005) == ["0004"]
    columns = reflect(at_0005, "feed_accounts", "get_columns")
    assert [c["name"] for c in columns] == ["id", "account_id", "provider_account_id"]
    uniques = reflect(at_0005, "feed_accounts", "get_unique_constraints")
    assert sorted((u["name"], u["column_names"]) for u in uniques) == [
        ("uq_feed_accounts_account_id", ["account_id"]),
        ("uq_feed_accounts_provider_account_id", ["provider_account_id"]),
    ]
    engine = get_engine(at_0005)
    with engine.connect() as connection:
        kept = connection.execute(
            text("SELECT account_id, provider_account_id FROM feed_accounts ORDER BY id")
        ).all()
    engine.dispose()
    assert [tuple(row) for row in kept] == [(1, "ACT-1"), (2, "ACT-2")]
    command.upgrade(make_config(at_0005), "0005")
    assert rows(at_0005) == [(1, 1, "ACT-1", "default"), (2, 2, "ACT-2", "default")]
```

`tests/unit/test_links.py`

```python
import keyring
import keyring.backend
import keyring.errors
import pytest

from finances.domain.models import DEFAULT_LINK, FeedAccount
from finances.sync.links import (
    KEYCHAIN_SERVICE,
    delete_access_url,
    load_access_url,
    save_access_url,
    validate_link_name,
)
from finances.sync.simplefin import SyncError

ACCESS = "https://user:pass@bridge.simplefin.org/simplefin"
NAME_RULE = "a link name is 1 to 30 lowercase letters, digits, or hyphens, starting with a letter"


class BrokenKeyring(keyring.backend.KeyringBackend):
    """A keychain that is locked or missing: every call fails."""

    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringLocked("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.PasswordSetError("refused")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.PasswordDeleteError("refused")


def test_the_names() -> None:
    assert (KEYCHAIN_SERVICE, DEFAULT_LINK) == ("finances-simplefin", "default")


def test_a_feed_account_has_the_default_link_unless_given() -> None:
    assert FeedAccount(1, 2, "ACT-1").link == "default"
    assert FeedAccount(1, 2, "ACT-1", "alex").link == "alex"


@pytest.mark.parametrize("name", ["a", "alex", "sam-2", "x" * 30, "default", "a-b-c", "z9"])
def test_usable_link_names(name: str) -> None:
    assert validate_link_name(name) == name


@pytest.mark.parametrize(
    "name", ["", "Alex", "1alex", "-alex", "al ex", "alex_", "x" * 31, "ålex", "alex\n", " alex"]
)
def test_unusable_link_names(name: str) -> None:
    with pytest.raises(ValueError) as caught:
        validate_link_name(name)
    assert str(caught.value) == NAME_RULE


def test_save_load_and_delete(keychain) -> None:
    assert load_access_url("alex") is None
    save_access_url("alex", ACCESS)
    save_access_url("sam", ACCESS + "2")
    assert keychain.passwords == {
        ("finances-simplefin", "alex"): ACCESS,
        ("finances-simplefin", "sam"): ACCESS + "2",
    }
    assert load_access_url("alex") == ACCESS
    save_access_url("alex", ACCESS + "3")
    assert load_access_url("alex") == ACCESS + "3"
    assert delete_access_url("alex") is True
    assert delete_access_url("alex") is False
    assert load_access_url("alex") is None
    assert load_access_url("sam") == ACCESS + "2"


@pytest.mark.parametrize("call", [load_access_url, delete_access_url])
def test_a_bad_name_never_reaches_the_keychain(keychain, call) -> None:
    with pytest.raises(ValueError):
        call("Bad Name")
    with pytest.raises(ValueError):
        save_access_url("Bad Name", ACCESS)
    assert keychain.passwords == {}


def test_a_keychain_that_fails_is_one_constant_error() -> None:
    previous = keyring.get_keyring()
    keyring.set_keyring(BrokenKeyring())
    try:
        for call, args in (
            (save_access_url, ("alex", ACCESS)),
            (load_access_url, ("alex",)),
            (delete_access_url, ("alex",)),
        ):
            with pytest.raises(SyncError) as caught:
                call(*args)
            assert str(caught.value) == "could not use the system keychain"
            assert caught.value.__suppress_context__ is True
    finally:
        keyring.set_keyring(previous)
```

`tests/integration/test_sync_links.py`

```python
import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.repositories import (
    create_account,
    list_feed_accounts,
    list_transactions,
    map_feed_account,
)
from finances.domain.models import FeedAccount
from finances.sync.runner import AccountSync, run_sync

ACCESS = "https://user:pass@bridge.simplefin.org/simplefin"
TODAY = date(2026, 6, 1)


def stamp(day: int) -> int:
    return int(datetime(2026, 5, day, 12, tzinfo=UTC).timestamp())


def bridge(*accounts: tuple[str, str, int]):
    """A fake transport answering one account set: (account id, transaction id, cents)."""
    body = {
        "errlist": [],
        "accounts": [
            {
                "id": account_id,
                "name": account_id,
                "currency": "USD",
                "balance": "0",
                "balance-date": stamp(31),
                "transactions": [
                    {
                        "id": feed_id,
                        "posted": stamp(20),
                        "amount": f"{cents // 100}.{abs(cents) % 100:02d}",
                        "description": "PROBE",
                    }
                ],
            }
            for account_id, feed_id, cents in accounts
        ],
    }

    def answer(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        return 200, json.dumps(body).encode()

    return answer


@pytest.fixture
def session(db_engine: Engine):
    """Three accounts: ids 1 and 2 for one person, 3 for the other."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card", last4="1111")
        create_account(opened, "Test Checking", "Test Bank", "checking", last4="2222")
        create_account(opened, "Test Other Card", "Other Bank", "credit_card", last4="3333")
        yield opened


def test_mappings_without_a_link_use_the_default_link(session: Session) -> None:
    assert map_feed_account(session, 1, "ACT-1") == FeedAccount(1, 1, "ACT-1", "default")
    assert list_feed_accounts(session) == [FeedAccount(1, 1, "ACT-1", "default")]
    assert list_feed_accounts(session, "default") == [FeedAccount(1, 1, "ACT-1", "default")]
    assert list_feed_accounts(session, "alex") == []


def test_the_same_aggregator_id_under_two_links(session: Session) -> None:
    alex = map_feed_account(session, 1, "ACT-1", "alex")
    sam = map_feed_account(session, 3, "ACT-1", "sam")
    assert (alex, sam) == (FeedAccount(1, 1, "ACT-1", "alex"), FeedAccount(2, 3, "ACT-1", "sam"))
    with pytest.raises(ValueError) as caught:
        map_feed_account(session, 2, "ACT-1", "alex")
    assert str(caught.value) == "feed account is already mapped to another account"
    assert list_feed_accounts(session, "alex") == [alex]
    assert list_feed_accounts(session, "sam") == [sam]
    assert list_feed_accounts(session) == [alex, sam]


def test_an_account_can_move_to_another_link(session: Session) -> None:
    map_feed_account(session, 1, "ACT-1", "alex")
    moved = map_feed_account(session, 1, "ACT-7", "sam")
    assert moved == FeedAccount(1, 1, "ACT-7", "sam")
    assert list_feed_accounts(session, "alex") == []
    assert map_feed_account(session, 2, "ACT-1", "alex") == FeedAccount(2, 2, "ACT-1", "alex")


def test_a_sync_touches_only_its_own_link(session: Session) -> None:
    map_feed_account(session, 1, "ACT-1", "alex")
    map_feed_account(session, 2, "ACT-2", "alex")
    map_feed_account(session, 3, "ACT-1", "sam")
    report = run_sync(
        session, ACCESS, today=TODAY, transport=bridge(("ACT-1", "S-1", -500)), link="sam"
    )
    assert [
        (item.provider_account_id, item.account_id, item.problem) for item in report.accounts
    ] == [("ACT-1", 3, None)]
    assert [t.amount_cents for t in list_transactions(session, 3)] == [-500]
    assert list_transactions(session, 1) == []
    report = run_sync(
        session, ACCESS, today=TODAY, transport=bridge(("ACT-1", "A-1", -700)), link="alex"
    )
    assert [(item.account_id, item.problem) for item in report.accounts] == [
        (1, None),
        (2, "not in the aggregator's answer"),
    ]
    assert [t.amount_cents for t in list_transactions(session, 1)] == [-700]
    assert [t.amount_cents for t in list_transactions(session, 3)] == [-500]


def test_a_sync_without_a_link_uses_the_default_link(session: Session) -> None:
    map_feed_account(session, 1, "ACT-1")
    map_feed_account(session, 3, "ACT-3", "sam")
    report = run_sync(session, ACCESS, today=TODAY, transport=bridge(("ACT-1", "D-1", -100)))
    assert report.accounts == [AccountSync("ACT-1", 1, report.accounts[0].pull, None)]
    assert report.accounts[0].pull.inserted == 1
```

`tests/e2e/test_cli_sync.py`

```python
import base64
import json
import re
from datetime import UTC, datetime

import keyring
import keyring.backend
import keyring.errors
import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.sync import transport
from finances.sync.feed import AccountFeed
from finances.sync.service import apply_feed

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"
SAM = "https://sam-user:sam-pass@bridge.simplefin.org/simplefin"
CLAIM = "https://bridge.simplefin.org/simplefin/claim/DEMO-1"
TOKEN = base64.b64encode(CLAIM.encode()).decode()
ACCOUNT_HEADINGS = ["SimpleFIN account", "Institution", "Name", "Currency", "Mapped to"]
RUN_HEADINGS = [
    "Link",
    "Account",
    "SimpleFIN account",
    "New",
    "Changed",
    "Removed",
    "Same",
    "Drift",
    "Problem",
]
STATUS_HEADINGS = [
    "Link",
    "Account",
    "SimpleFIN account",
    "Keychain",
    "Last pull",
    "Balance date",
    "Drift",
]


def run(*args: object, input: str | None = None):
    return runner.invoke(app, [str(arg) for arg in args], input=input)


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def failed_cleanly(result, message: str) -> bool:
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


def stamp(day: int) -> int:
    today = datetime.now(UTC).date()
    return int(datetime(today.year, today.month, today.day, 12, tzinfo=UTC).timestamp()) - (
        day * 86400
    )


def account(account_id: str, name: str, balance: str, *moves: tuple[str, int, str]) -> dict:
    return {
        "id": account_id,
        "name": name,
        "conn_id": "C-1",
        "currency": "USD",
        "balance": balance,
        "balance-date": stamp(0),
        "transactions": [
            {"id": feed_id, "posted": stamp(days_ago), "amount": amount, "description": "PROBE"}
            for feed_id, days_ago, amount in moves
        ],
    }


class Bridge:
    """A fake SimpleFIN Bridge: claims give an access URL; each access URL has its answer."""

    def __init__(self) -> None:
        self.claim = (200, ALEX.encode())
        self.answers: dict[str, tuple[int, dict | None]] = {}
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append((method, url, dict(headers)))
        if method == "POST":
            return self.claim
        status, body = self.answers[headers["Authorization"]]
        return status, json.dumps(body).encode()

    def answer(self, access: str, *accounts: dict, status: int = 200, messages=()) -> None:
        user, password = access.split("//")[1].split("@")[0].split(":")
        key = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        body = {
            "errlist": [{"code": "con.auth", "msg": text} for text in messages],
            "connections": [
                {"conn_id": "C-1", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}
            ],
            "accounts": list(accounts),
        }
        self.answers[key] = (status, body)


class BrokenKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringLocked("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.PasswordSetError("refused")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.PasswordDeleteError("refused")


@pytest.fixture
def bridge(monkeypatch: pytest.MonkeyPatch) -> Bridge:
    fake = Bridge()
    monkeypatch.setattr(transport, "urllib_transport", fake)
    return fake


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    for name, kind, last4 in (
        ("Test Card", "credit_card", "1111"),
        ("Test Checking", "checking", "2222"),
        ("Test Other Card", "credit_card", "3333"),
    ):
        details = ["--institution", "Probe Bank", "--type", kind, "--last4", last4]
        made = run("accounts", "add", "--name", name, *details)
        assert made.exit_code == 0
    return tmp_settings


@pytest.fixture
def broken_keychain():
    previous = keyring.get_keyring()
    keyring.set_keyring(BrokenKeyring())
    yield
    keyring.set_keyring(previous)


# ----- link and unlink -----


def test_link_claims_the_token_and_keeps_the_access_in_the_keychain(
    bridge: Bridge, keychain
) -> None:
    result = run("sync", "link", "--link", "alex", input=TOKEN + "\n")
    assert result.exit_code == 0
    assert result.stdout == "SimpleFIN setup token: \nLinked alex.\n"
    assert TOKEN not in result.output and "alex-pass" not in result.output
    assert keychain.passwords == {("finances-simplefin", "alex"): ALEX}
    assert [(method, url) for method, url, _ in bridge.calls] == [("POST", CLAIM)]


def test_link_without_a_name_uses_the_default_link(bridge: Bridge, keychain) -> None:
    assert run("sync", "link", input=TOKEN + "\n").stdout.endswith("Linked default.\n")
    assert keychain.passwords == {("finances-simplefin", "default"): ALEX}


def test_a_link_is_not_replaced_unless_asked(bridge: Bridge, keychain) -> None:
    keychain.passwords[("finances-simplefin", "alex")] = SAM
    result = run("sync", "link", "--link", "alex", input=TOKEN + "\n")
    assert failed_cleanly(result, "link alex is already set up; use --replace to set it up again")
    assert bridge.calls == []
    result = run("sync", "link", "--link", "alex", "--replace", input=TOKEN + "\n")
    assert result.exit_code == 0
    assert keychain.passwords == {("finances-simplefin", "alex"): ALEX}


def test_a_refused_token_stores_nothing(bridge: Bridge, keychain) -> None:
    bridge.claim = (403, b"")
    result = run("sync", "link", "--link", "alex", input=TOKEN + "\n")
    assert result.exit_code == 1
    assert result.stderr == "Error: setup token was already used or does not exist\n"
    assert keychain.passwords == {}


def test_a_token_that_is_not_simplefin_is_not_sent(bridge: Bridge, keychain) -> None:
    bad = base64.b64encode(b"https://example.com/claim").decode()
    result = run("sync", "link", "--link", "alex", input=bad + "\n")
    assert result.stderr == "Error: setup token is not valid\n"
    assert bridge.calls == [] and keychain.passwords == {}


@pytest.mark.parametrize("command", ["link", "unlink"])
def test_a_bad_link_name(bridge: Bridge, keychain, command: str) -> None:
    result = run("sync", command, "--link", "Alex Smith", input=TOKEN + "\n")
    message = "a link name is 1 to 30 lowercase letters, digits, or hyphens, starting with a letter"
    assert failed_cleanly(result, message)
    assert bridge.calls == []


def test_unlink(keychain) -> None:
    keychain.passwords[("finances-simplefin", "sam")] = SAM
    result = run("sync", "unlink", "--link", "sam")
    assert (result.exit_code, result.stdout) == (0, "Unlinked sam.\n")
    assert keychain.passwords == {}
    assert failed_cleanly(run("sync", "unlink", "--link", "sam"), "link sam is not set up")


def test_a_keychain_that_fails(bridge: Bridge, broken_keychain) -> None:
    assert failed_cleanly(
        run("sync", "link", input=TOKEN + "\n"), "could not use the system keychain"
    )
    assert failed_cleanly(run("sync", "unlink"), "could not use the system keychain")


# ----- map and accounts -----


def test_map_and_list_accounts(migrated: Settings, bridge: Bridge, keychain) -> None:
    keychain.passwords[("finances-simplefin", "alex")] = ALEX
    bridge.answer(
        ALEX,
        account("ACT-1", "Probe Rewards Card", "-10.00"),
        account("ACT-2", "Probe Checking", "100.00"),
        messages=("Probe Bank\\nneeds attention",),
    )
    result = run(
        "sync", "map", "--account", "test card", "--feed-account", " ACT-1 ", "--link", "alex"
    )
    assert (result.exit_code, result.stdout) == (
        0,
        'Mapped ACT-1 to "Test Card" under link alex.\n',
    )
    result = run("sync", "accounts", "--link", "alex")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        ACCOUNT_HEADINGS,
        ["ACT-1", "Probe Bank", "Probe Rewards Card", "USD", "Test Card"],
        ["ACT-2", "Probe Bank", "Probe Checking", "USD", ""],
    ]
    assert result.stdout.endswith("SimpleFIN: Probe Bank\\nneeds attention\n")
    assert "alex-pass" not in result.output
    method, url, headers = bridge.calls[0]
    assert (method, headers["Authorization"].startswith("Basic ")) == ("GET", True)
    assert url.startswith("https://bridge.simplefin.org/simplefin/accounts?start-date=")


def test_accounts_lists_only_this_links_mappings(
    migrated: Settings, bridge: Bridge, keychain
) -> None:
    keychain.passwords[("finances-simplefin", "sam")] = SAM
    bridge.answer(SAM, account("ACT-1", "Probe Card", "0"))
    assert (
        run(
            "sync", "map", "--account", "Test Card", "--feed-account", "ACT-1", "--link", "alex"
        ).exit_code
        == 0
    )
    result = run("sync", "accounts", "--link", "sam")
    assert table_rows(result.stdout)[1] == ["ACT-1", "Probe Bank", "Probe Card", "USD", ""]


def test_accounts_with_none_and_with_an_error(migrated: Settings, bridge: Bridge, keychain) -> None:
    keychain.passwords[("finances-simplefin", "default")] = ALEX
    bridge.answer(ALEX)
    assert run("sync", "accounts").stdout == "No accounts.\n"
    bridge.answer(ALEX, status=402)
    assert failed_cleanly(run("sync", "accounts"), "aggregator subscription needs payment")


def test_accounts_of_a_link_that_is_not_set_up(migrated: Settings, bridge: Bridge) -> None:
    result = run("sync", "accounts", "--link", "sam")
    assert failed_cleanly(result, "link sam is not set up (run: fin sync link --link sam)")
    assert bridge.calls == []


def test_map_refusals(migrated: Settings) -> None:
    assert failed_cleanly(
        run("sync", "map", "--account", "Nope", "--feed-account", "ACT-1"), "account not found"
    )
    assert failed_cleanly(
        run("sync", "map", "--account", "Test Card", "--feed-account", "  "),
        "feed account id must be 1 to 200 characters",
    )
    assert failed_cleanly(
        run("sync", "map", "--account", "Test Card", "--feed-account", "X" * 201),
        "feed account id must be 1 to 200 characters",
    )
    assert run("sync", "map", "--account", "Test Card", "--feed-account", "ACT-1").exit_code == 0
    assert failed_cleanly(
        run("sync", "map", "--account", "Test Checking", "--feed-account", "ACT-1"),
        "feed account is already mapped to another account",
    )
    result = run(
        "sync", "map", "--account", "Test Checking", "--feed-account", "ACT-1", "--link", "sam"
    )
    assert result.exit_code == 0


# ----- run and status -----


def test_run_pulls_every_link_and_prints_one_row_per_account(
    migrated: Settings, bridge: Bridge, keychain
) -> None:
    keychain.passwords[("finances-simplefin", "alex")] = ALEX
    keychain.passwords[("finances-simplefin", "sam")] = SAM
    for name, feed, link in (
        ("Test Card", "ACT-1", "alex"),
        ("Test Checking", "ACT-2", "alex"),
        ("Test Other Card", "ACT-1", "sam"),
    ):
        assert (
            run("sync", "map", "--account", name, "--feed-account", feed, "--link", link).exit_code
            == 0
        )
    bridge.answer(
        ALEX,
        account("ACT-1", "Probe Card", "-12.50", ("A-1", 3, "-12.50")),
        account("ACT-9", "Probe Unmapped", "1.00"),
    )
    bridge.answer(
        SAM,
        account("ACT-1", "Probe Other", "-4.00", ("S-1", 2, "-4.00")),
        messages=("Sam bank note",),
    )
    result = run("sync", "run")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        RUN_HEADINGS,
        ["alex", "Test Card", "ACT-1", "1", "0", "0", "0", "", ""],
        ["alex", "", "ACT-9", "", "", "", "", "", "not mapped"],
        ["alex", "Test Checking", "ACT-2", "", "", "", "", "", "not in the aggregator's answer"],
        ["sam", "Test Other Card", "ACT-1", "1", "0", "0", "0", "", ""],
    ]
    assert result.stdout.endswith("SimpleFIN (sam): Sam bank note\n")
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-15.00", ("A-1", 3, "-12.50")))
    result = run("sync", "run", "--link", "alex")
    assert table_rows(result.stdout)[1] == [
        "alex",
        "Test Card",
        "ACT-1",
        "0",
        "0",
        "0",
        "1",
        "-$2.50",
        "",
    ]
    assert len(table_rows(result.stdout)) == 3


def test_one_link_failing_does_not_stop_the_others(
    migrated: Settings, bridge: Bridge, keychain
) -> None:
    keychain.passwords[("finances-simplefin", "alex")] = ALEX
    keychain.passwords[("finances-simplefin", "sam")] = SAM
    mapped = (("Test Card", "alex"), ("Test Checking", "bob"), ("Test Other Card", "sam"))
    for name, link in mapped:
        made = run("sync", "map", "--account", name, "--feed-account", "ACT-1", "--link", link)
        assert made.exit_code == 0
    bridge.answer(ALEX, status=403)
    bridge.answer(SAM, account("ACT-1", "Probe Other", "-4.00", ("S-1", 2, "-4.00")))
    result = run("sync", "run")
    assert result.exit_code == 1
    assert result.stderr == (
        "Error: link alex: aggregator access was revoked or is wrong\n"
        "Error: link bob is not set up (run: fin sync link --link bob)\n"
    )
    assert table_rows(result.stdout) == [
        RUN_HEADINGS,
        ["sam", "Test Other Card", "ACT-1", "1", "0", "0", "0", "", ""],
    ]


def test_run_with_nothing_mapped_and_bad_options(migrated: Settings, bridge: Bridge) -> None:
    assert run("sync", "run").stdout == "No mapped accounts.\n"
    assert run("sync", "run", "--days", "0").exit_code == 2
    assert run("sync", "run", "--days", "91").exit_code == 2
    assert failed_cleanly(
        run("sync", "run", "--link", "Bad"),
        "a link name is 1 to 30 lowercase letters, digits, or hyphens, starting with a letter",
    )
    assert bridge.calls == []


def test_run_asks_for_the_days_given(migrated: Settings, bridge: Bridge, keychain) -> None:
    keychain.passwords[("finances-simplefin", "default")] = ALEX
    assert run("sync", "map", "--account", "Test Card", "--feed-account", "ACT-1").exit_code == 0
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "0"))
    assert run("sync", "run", "--days", "7").exit_code == 0
    today = datetime.now(UTC).date()
    start = int(datetime(today.year, today.month, today.day, tzinfo=UTC).timestamp()) - 7 * 86400
    assert re.search(rf"start-date={start}&", bridge.calls[0][1])


def test_status(migrated: Settings, bridge: Bridge, keychain) -> None:
    assert run("sync", "status").stdout == "No mapped accounts.\n"
    keychain.passwords[("finances-simplefin", "alex")] = ALEX
    assert (
        run(
            "sync", "map", "--account", "Test Card", "--feed-account", "ACT-1", "--link", "alex"
        ).exit_code
        == 0
    )
    assert (
        run(
            "sync",
            "map",
            "--account",
            "Test Other Card",
            "--feed-account",
            "ACT-1",
            "--link",
            "sam",
        ).exit_code
        == 0
    )
    result = run("sync", "status")
    assert table_rows(result.stdout) == [
        STATUS_HEADINGS,
        ["alex", "Test Card", "ACT-1", "yes", "never", "", ""],
        ["sam", "Test Other Card", "ACT-1", "no", "never", "", ""],
    ]
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-1.00", ("A-1", 1, "-1.00")))
    assert run("sync", "run", "--link", "alex").exit_code == 0
    bridge.answer(ALEX, account("ACT-1", "Probe Card", "-3.00", ("A-1", 1, "-1.00")))
    assert run("sync", "run", "--link", "alex").exit_code == 0
    row = table_rows(run("sync", "status").stdout)[1]
    assert row[:4] == ["alex", "Test Card", "ACT-1", "yes"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", row[4])
    assert row[5:] == [datetime.now(UTC).date().isoformat(), "-$2.00"]
    engine = get_engine()
    with session_scope(engine) as session:
        apply_feed(session, 1, AccountFeed())
    engine.dispose()
    row = table_rows(run("sync", "status").stdout)[1]
    assert row[5:] == [datetime.now(UTC).date().isoformat(), "-$2.00"]


def test_status_with_a_keychain_that_fails(migrated: Settings, broken_keychain) -> None:
    assert run("sync", "map", "--account", "Test Card", "--feed-account", "ACT-1").exit_code == 0
    assert table_rows(run("sync", "status").stdout)[1][3] == "unknown"


@pytest.mark.parametrize(
    "command", [["accounts"], ["map", "--account", "A", "--feed-account", "B"], ["run"], ["status"]]
)
def test_commands_that_read_the_database_need_it_migrated(
    tmp_settings: Settings, command: list[str]
) -> None:
    result = run("sync", *command)
    assert (result.exit_code, result.stderr) == (1, NOT_MIGRATED)


def test_sync_is_a_command_group() -> None:
    result = run("sync", "--help")
    assert result.exit_code == 0
    for name in ("link", "unlink", "accounts", "map", "run", "status"):
        assert re.search(rf"│ {name} ", result.stdout)


def test_reading_the_keychain_fails_for_accounts_and_run(
    migrated: Settings, bridge: Bridge, broken_keychain
) -> None:
    assert failed_cleanly(run("sync", "accounts"), "could not use the system keychain")
    assert run("sync", "map", "--account", "Test Card", "--feed-account", "ACT-1").exit_code == 0
    result = run("sync", "run")
    assert (result.exit_code, result.stderr) == (1, "Error: could not use the system keychain\n")
    assert bridge.calls == []
```

## Rules for this phase

- **Secrets.** The setup token and the access URL are credentials. The token is read only through the hidden prompt. The access URL lives only in the Keychain, through `links.py`; `keyring` is imported nowhere else. Neither appears in output, in an exception message, in a log, in the database, or in a file.
- **The network.** Only `transport.py` opens connections, through the opener that refuses redirects, and only to hosts the Phase 17b client allows. Tests never reach the network or the real Keychain (R22).
- **Constant messages.** The messages of this phase are the ones written in R10, R13 to R18; the only varying parts are a link name, an account name, a feed account id, and a message from SimpleFIN cleaned as in Phase 17b.
- **Thin commands.** `cli/sync.py` checks options, calls the functions of `sync/` and `db/`, and prints. It contains no sync logic and writes no query.
- **Shipped migrations stay as they are**; the change ships as `0005`.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.
- **Do not run `fin sync link` or any `fin sync` command against the real Keychain or SimpleFIN.** The owner does that after verification.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, at least N + 61 passed, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_transport.py tests/integration/test_migration_0005.py tests/unit/test_links.py tests/integration/test_sync_links.py tests/e2e/test_cli_sync.py --no-cov` | exactly `73 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| each of the six searches below | no output |
| `git diff HEAD --stat -- src/finances/db/migrations/versions/0001_accounts.py src/finances/db/migrations/versions/0002_statements.py src/finances/db/migrations/versions/0003_feed.py src/finances/db/migrations/versions/0004_feed_accounts.py src/finances/sync/simplefin.py src/finances/sync/service.py src/finances/sync/feed.py src/finances/ingest tests/fixtures tests/integration/test_sync_runner.py tests/integration/test_migration_0004.py tests/integration/test_feed_account_repositories.py` | no output |
| `git status --short` | only the paths in the Scope table |

N + 61: the replaced `test_transport.py` has as many tests as the one it replaces, and the four new files add 61.

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.sync --cov=finances.db --cov=finances.domain --cov=finances.cli --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -E "^ *(import|from) +(requests|httpx|urllib|socket|http|aiohttp|ssl|ftplib|smtplib)" -- src/finances ':!src/finances/sync' ':!src/finances/config.py'`

`git grep -n --untracked -E "^ *(import|from) +(urllib\.request|urllib\.error|socket|http\.client|ssl)" -- src/finances ':!src/finances/sync/transport.py'`

`git grep -n --untracked -e "urlopen" -- src/finances`

`git grep -n --untracked -e "keyring" -- src/finances ':!src/finances/sync/links.py'`

`git grep -n --untracked -E "float|(^|[^_a-zA-Z.])print\(|logging" -- src/finances/sync src/finances/cli/sync.py`

`git grep -n --untracked -E "finances\.(ingest|cli)" -- src/finances/sync src/finances/db src/finances/domain`

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 17c: SimpleFIN links and the sync commands (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. Under "Deviations", list your design choices (private helpers, how each command is divided) and anything you did that the spec did not ask for, or `None`. Do not run any `fin sync` command against the real Keychain or SimpleFIN, and report nothing about a real account.

In your final message, give the output line of each acceptance command, and for each of R1 to R22 the name of a test that covers it.
