# Phase 17b: syncing from SimpleFIN

## Goal

Connect the feed core of Phase 17a to a real aggregator: **SimpleFIN Bridge**. After this phase the app can:

- turn the one-time setup token the user copies from SimpleFIN Bridge into an **access URL** (`claim_access_url`);
- ask SimpleFIN for every account's balance and the last 30 days of transactions, holds included, in **one request** (`fetch_accounts`);
- read the answer into plain data (`parse_account_set`), and
- apply each account that the user has **mapped** to one of ours, through `apply_feed` (`run_sync`).

This is the first code in the project that uses the network. It lives in `src/finances/sync/` only, it talks only to hosts under `simplefin.org` over HTTPS, and every request goes through one small function so that tests never touch the network.

Commands (`fin sync link`, `fin sync map`, `fin sync run`, `fin sync status`) and storing the access URL in the macOS Keychain are Phase 17c. In this phase the access URL is simply a string the caller passes in.

## What SimpleFIN is, for this phase

This summary is taken from the SimpleFIN protocol (`https://www.simplefin.org/protocol.html`, version 2.0.0-draft). You do not need to read it, and you must not contact it.

- The user signs up at SimpleFIN Bridge, links their banks there, and receives a **setup token**: a Base64-encoded HTTPS URL, the **claim URL**.
- An HTTP `POST` to the claim URL, once, returns the **access URL** as the response body, for example `https://user:pass@bridge.simplefin.org/simplefin`. It carries Basic-auth credentials. A second claim of the same token gets status `403`.
- `GET {access URL without the credentials}/accounts` with Basic auth returns an **Account Set** in JSON. Query parameters used here: `start-date` and `end-date` (Unix seconds; transactions on or after the start and strictly before the end) and `pending=1` (include holds). Status `403` means the access was revoked; `402` means the user's SimpleFIN subscription needs payment.
- An Account Set has `accounts`, and, in version 2, `connections` (each with `conn_id` and `name`) and `errlist` (each with `code` and `msg`); in version 1, each account has an `org` object with a `name`, and the top level has `errors`, a list of strings. Either version may be served.
- An account has `id`, `name`, `currency`, `balance` (a decimal string), `balance-date` (Unix seconds), optionally `conn_id`, and optionally `transactions`.
- A transaction has `id` (unique within its account), `posted` (Unix seconds, `0` for some holds), `amount` (a decimal string; positive is money in), `description`, and optionally `transacted_at` (Unix seconds) and `pending` (a boolean, default false).
- SimpleFIN does not say when a hold disappears. A hold that posts usually comes back as a new transaction with a new id, and the hold is simply no longer listed.

## Read first

- `AGENTS.md`: "Privacy rules" (rule 1 in particular), "Money and signs", "Architecture rules"
- `docs/architecture.md`: "Privacy boundary"
- `docs/phases/phase-17a-feed-core.md` and `src/finances/sync/`
- `src/finances/domain/money.py`: `parse_money`
- `tests/fixtures/simplefin/`: two synthetic Account Sets, already in the repository

## Starting state

- Phase 8 is committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `1291` when Phase 8 is the last phase built.
- The newest migration is `0003`. No code in the project makes a network request.
- `tests/fixtures/simplefin/account_set_v2.json` and `account_set_v1.json` are synthetic answers in the two versions of the protocol.
- `finances.sync`, `finances.db`, and `finances.domain` are at 100% line and branch coverage.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0004_feed_accounts.py` | new: table `feed_accounts` |
| `src/finances/domain/models.py` | one class added: `FeedAccount` |
| `src/finances/db/orm.py` | added: `FeedAccountRow`, `to_feed_account` |
| `src/finances/db/repositories.py` | three functions added (Part 1) |
| `src/finances/sync/simplefin.py` | new: the SimpleFIN client |
| `src/finances/sync/transport.py` | new: the one function that sends an HTTP request |
| `src/finances/sync/runner.py` | new: `run_sync` |
| `tests/integration/test_migration_0004.py`, `tests/unit/test_simplefin.py`, `tests/unit/test_transport.py`, `tests/integration/test_sync_runner.py` | given, do not change |
| `tests/integration/test_feed_account_repositories.py` | new, written by you |
| `docs/progress.md` | one new entry |

You may add private helpers and module constants to the new modules and to `repositories.py`. Do not change `sync/feed.py`, `sync/service.py`, any other production file, any existing test, `tests/conftest.py`, or the fixtures.

## Out of scope

- Commands, printed output, the Keychain, `keyring`, and scheduling. Phase 17c.
- Any other aggregator, and any abstraction for several aggregators.
- Retries, back-off, and caching. One sync is one request; a failure is reported and the next sync tries again.
- `available-balance`, `balances-only`, the `account` filter, the `version` parameter, `GET /info`, and the `extra` objects. They are ignored.
- Categories or merchant names from the aggregator.
- Choosing which aggregator account belongs to which of ours. The mapping is stored by `map_feed_account`; Phase 17c lets the user set it.
- New dependencies. HTTP is done with the standard library's `urllib.request`.

## Dependencies

None new.

## Design

### The table (migration `0004`, `down_revision = "0003"`)

`feed_accounts` says which aggregator account feeds which of our accounts.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | Integer | no | primary key `pk_feed_accounts` |
| `account_id` | Integer | no | foreign key `fk_feed_accounts_account_id_accounts` to `accounts.id`; unique constraint `uq_feed_accounts_account_id` |
| `provider_account_id` | String(200) | no | SimpleFIN's account `id`; unique constraint `uq_feed_accounts_provider_account_id` |

No index. The migration file follows `0003_feed.py`: no import from `finances`, no `server_default`, every constraint named, and a `downgrade` that drops this table only.

```python
# domain/models.py
@dataclass(frozen=True)
class FeedAccount:
    """Which aggregator account feeds one of our accounts."""

    id: int
    account_id: int
    provider_account_id: str
```

### The client, in `src/finances/sync/simplefin.py`

```python
Transport = Callable[[str, str, dict[str, str]], tuple[int, bytes]]
NO_DESCRIPTION = "(no description)"


class SyncError(Exception):
    """Raised when the aggregator cannot be reached or its answer cannot be used."""


@dataclass(frozen=True)
class ProviderAccount:
    """One account in the aggregator's answer. Amounts are from the account holder's side."""

    provider_account_id: str
    name: str
    institution: str
    currency: str
    balance_cents: int
    balance_date: date
    transactions: list[FeedTransaction]


@dataclass(frozen=True)
class ProviderAnswer:
    """The aggregator's answer: its accounts and the messages it asks to show the user."""

    accounts: list[ProviderAccount]
    messages: list[str]


def claim_access_url(setup_token: str, transport: Transport) -> str: ...
def fetch_accounts(access_url: str, start: date, end: date, transport: Transport) -> ProviderAnswer: ...
def parse_account_set(payload: dict) -> ProviderAnswer: ...
```

A **transport** is a function `(method, url, headers) -> (status, body)`. The client never opens a connection itself; it calls the transport it is given. Tests pass a fake one.

### The transport, in `src/finances/sync/transport.py`

```python
TIMEOUT_SECONDS = 60


def urllib_transport(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]: ...
```

### The sync, in `src/finances/sync/runner.py`

```python
SYNC_DAYS = 30


@dataclass(frozen=True)
class AccountSync:
    """What happened to one account in a sync."""

    provider_account_id: str
    account_id: int | None
    pull: FeedPull | None
    problem: str | None


@dataclass(frozen=True)
class SyncReport:
    """What one sync did, account by account, and the aggregator's messages."""

    accounts: list[AccountSync]
    messages: list[str]


def run_sync(
    session: Session, access_url: str, *, today: date, transport: Transport, days: int = SYNC_DAYS
) -> SyncReport: ...
```

### The synthetic answers

`tests/fixtures/simplefin/account_set_v2.json`:

```json
{
  "errlist": [
    {
      "code": "con.auth",
      "msg": "Example  Savings Bank\nneeds you to sign in again.\u0007",
      "conn_id": "CON-2"
    }
  ],
  "connections": [
    {
      "conn_id": "CON-1",
      "name": "Example Card Bank",
      "org_id": "ORG-1",
      "org_url": "example.invalid",
      "sfin_url": "https://bridge.simplefin.org/simplefin"
    },
    {
      "conn_id": "CON-2",
      "name": "Example Savings Bank",
      "org_id": "ORG-2",
      "sfin_url": "https://bridge.simplefin.org/simplefin"
    }
  ],
  "accounts": [
    {
      "id": "ACT-card-1",
      "name": "Example Rewards Card",
      "conn_id": "CON-1",
      "currency": "USD",
      "balance": "-1234.56",
      "available-balance": "8765.44",
      "balance-date": 1780282800,
      "transactions": [
        {
          "id": "TRN-1",
          "posted": 1780056000,
          "amount": "-4.50",
          "description": "ACME COFFEE #12",
          "transacted_at": 1779991200
        },
        {
          "id": "TRN-2",
          "posted": 0,
          "amount": "-25.99",
          "description": "FOOBAR  GROCERY",
          "transacted_at": 1780218000,
          "pending": true
        },
        {
          "id": "TRN-3",
          "posted": 0,
          "amount": "-10.00",
          "description": "   ",
          "pending": true
        },
        {
          "id": "TRN-4",
          "posted": 1780185600,
          "amount": "500.00",
          "description": "PAYMENT THANK YOU",
          "pending": false,
          "extra": {
            "category": "Payment"
          }
        }
      ],
      "extra": {
        "note": "synthetic"
      }
    },
    {
      "id": "ACT-sav-1",
      "name": "Example Savings",
      "conn_id": "CON-2",
      "currency": "USD",
      "balance": "10000",
      "balance-date": 1780268400,
      "transactions": []
    },
    {
      "id": "ACT-eur-1",
      "name": "Example Euro Account",
      "conn_id": "CON-2",
      "currency": "EUR",
      "balance": "1.00",
      "balance-date": 1780315200
    }
  ]
}
```

`tests/fixtures/simplefin/account_set_v1.json`:

```json
{
  "errors": [
    "Example Card Bank: connection   may need attention"
  ],
  "accounts": [
    {
      "org": {
        "domain": "example.invalid",
        "sfin-url": "https://bridge.simplefin.org/simplefin",
        "name": "Example Card Bank"
      },
      "id": "ACT-card-1",
      "name": "Example Rewards Card",
      "currency": "USD",
      "balance": "-99.01",
      "balance-date": 1780401600,
      "transactions": [
        {
          "id": "TRN-9",
          "posted": 1780315200,
          "amount": "-99.01",
          "description": "ACME HARDWARE"
        }
      ]
    }
  ]
}
```

## Requirements

### Part 1: mapping accounts

- **R1.** Migration `0004` creates `feed_accounts` exactly as designed, and its `downgrade` removes it and nothing else. `FeedAccountRow` declares the same columns and constraint names, and `to_feed_account` returns the `FeedAccount` for a row.
- **R2.** `map_feed_account(session, account_id, provider_account_id) -> FeedAccount` makes the aggregator account feed the account. When the account was already fed by another aggregator account, that mapping is changed in place and keeps its id. Mapping the same pair again changes nothing. When the aggregator account already feeds a **different** account, it raises `ValueError("feed account is already mapped to another account")` and changes nothing.
- **R3.** `list_feed_accounts(session) -> list[FeedAccount]` returns every mapping in id order.
- **R4.** `list_pending_feed_ids(session, account_id, since) -> list[str]` returns the feed ids of the account's transactions whose `source` is `aggregator`, that are pending, and whose `posted_date` is `since` or later, in transaction id order.
- **R5.** All three take the session first, return domain objects or plain values, and leave the commit to the caller.

### Part 2: the SimpleFIN client

A URL is **allowed** when its scheme is `https` and its host is `simplefin.org` or ends with `.simplefin.org`. An access URL is **usable** when it is allowed and has both a user name and a password.

- **R6.** `claim_access_url(setup_token, transport)`:
  1. Removes outer whitespace from the token and decodes it as strict Base64 to ASCII text: the claim URL. When that fails, or the claim URL is not allowed, or it carries a user name, it raises `SyncError("setup token is not valid")` without calling the transport.
  2. Calls the transport once: `("POST", claim_url, {"Content-Length": "0"})`.
  3. Status `403` raises `SyncError("setup token was already used or does not exist")`. Any other status but `200` raises `SyncError("aggregator refused the setup token")`.
  4. The body, decoded as ASCII with outer whitespace removed, is the access URL. When it cannot be decoded or is not usable, it raises `SyncError("aggregator answer could not be read")`. Otherwise it is returned.
- **R7.** `fetch_accounts(access_url, start, end, transport)`:
  1. When the access URL is not usable, raises `SyncError("stored aggregator access is not valid")` without calling the transport.
  2. Calls the transport once with `"GET"`, a URL, and the headers `{"Authorization": "Basic " + base64("user:password")}`. The URL is `https://`, the host (with its port, if the access URL has one), the access URL's path without a trailing `/`, then `/accounts`, then the query `start-date=S&end-date=E&pending=1` in that order. `S` is midnight UTC at the start of `start` in Unix seconds, and `E` is midnight UTC at the start of the day **after** `end`, so that `end` itself is included. The URL never contains the user name or the password.
  3. Status `403` raises `SyncError("aggregator access was revoked or is wrong")`, `402` raises `SyncError("aggregator subscription needs payment")`, and any other status but `200` raises `SyncError("aggregator answered with an error")`.
  4. The body is read as JSON and passed to `parse_account_set`. When the JSON or the answer cannot be read, it raises `SyncError("aggregator answer could not be read")`, raised so that neither `__cause__` nor `__context__` is shown (`from None`).
- **R8.** `parse_account_set(payload)` returns a `ProviderAnswer`, or raises `ValueError` (or `TypeError`, `KeyError`, `AttributeError`) when the payload is not an object with an `accounts` list, or anything required below is missing or cannot be read. It reads both versions of the protocol.
- **R9.** Each account becomes a `ProviderAccount`, in the order of `accounts`:

  | Field | Value |
  |---|---|
  | `provider_account_id` | the account's `id`, as text |
  | `name` | the account's `name`, cleaned as a message (R12) |
  | `institution` | the `name` of the connection whose `conn_id` is the account's `conn_id`; failing that, the `name` of the account's `org`; failing that, empty. Cleaned as a message |
  | `currency` | the account's `currency`, as given |
  | `balance_cents` | `parse_money` of the account's `balance` |
  | `balance_date` | the UTC date of `balance-date` |
  | `transactions` | one `FeedTransaction` per item of `transactions`, in order; none when the key is absent or empty |

- **R10.** Each transaction becomes a `FeedTransaction`:

  | Field | Value |
  |---|---|
  | `feed_id` | the transaction's `id`, as text |
  | `posted_date` | the UTC date of `posted` when it is not `0`; otherwise the UTC date of `transacted_at` when that is present and not `0`; otherwise the account's `balance_date` |
  | `amount_cents` | `parse_money` of `amount`, sign kept: positive is money in, negative is money out |
  | `description` | the `description` with runs of whitespace made one space and outer whitespace removed; `NO_DESCRIPTION` when that leaves nothing |
  | `is_pending` | `pending`, `False` when absent |
  | `transaction_date` | the UTC date of `transacted_at` when present and not `0`; otherwise `None` |
  | `card_last4`, `replaces_feed_id` | `None` |

  All dates are taken in UTC, whatever the computer's time zone.
- **R11.** `messages` holds the `msg` of each item of `errlist`, then each string of `errors`, each cleaned (R12). A message that is empty after cleaning is left out.
- **R12.** **Cleaning** a text makes every run of whitespace (line breaks included) one space, removes the characters that are not printable, makes runs of whitespace one space again, removes outer whitespace, and keeps the first 200 characters.

### Part 3: the transport

- **R13.** `urllib_transport(method, url, headers)` sends one request with `urllib.request`: a `Request` with that method, URL, and headers, a body of `b""` for `POST` and none for anything else, opened with `urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)`. It returns the response's status and its whole body. Certificates are verified, as `urlopen` does by default; nothing in this module turns that off.
- **R14.** An `urllib.error.HTTPError` returns its status code with an empty body. The error's own body is never read.
- **R15.** Any other failure to connect (`urllib.error.URLError`, `TimeoutError`, any `OSError`) raises `SyncError("could not reach the aggregator")` from `None`.
- **R16.** `transport.py` is the only module in the project that imports `urllib.request`, `urllib.error`, `socket`, `http.client`, or `ssl`, and nothing outside `src/finances/sync/` imports a network library.

### Part 4: a sync

- **R17.** `run_sync` calls `fetch_accounts` once, from `today` minus `days` days to `today`. A `SyncError` from it is not caught: nothing is written, and the caller sees the error.
- **R18.** For each account in the answer, in order, one `AccountSync` is added:
  - not mapped: `AccountSync(provider_account_id, None, None, "not mapped")`, and nothing is applied;
  - mapped, with a currency other than `USD`: `AccountSync(provider_account_id, account_id, None, "currency is not USD")`, and nothing is applied;
  - mapped and `USD`: its feed is applied with `apply_feed` (R19). On a `FeedError`, `AccountSync(provider_account_id, account_id, None, <the error's message>)`; otherwise `AccountSync(provider_account_id, account_id, <the FeedPull>, None)`.
- **R19.** The feed applied for an account is an `AccountFeed` with the account's transactions, its balance and balance date, and the **removed** ids: when the answer has no messages, the feed ids that `list_pending_feed_ids` gives for the account since the first day of the window and that the answer does not deliver for this account; when the answer has any message, none. A hold that SimpleFIN no longer lists is removed this way. A posted row is never removed for not being delivered, and nothing is removed when SimpleFIN may have given an incomplete answer.
- **R20.** After the accounts of the answer, each mapped account that the answer does not contain adds `AccountSync(provider_account_id, account_id, None, "not in the aggregator's answer")`, in the order of `list_feed_accounts`.
- **R21.** One account's `FeedError` does not stop the others. `run_sync` never commits or rolls back.
- **R22.** The returned `SyncReport` holds those results and the answer's messages.

## Given tests

Create these four files exactly as shown and do not change them. If one of their tests fails, the production code is wrong.

`tests/integration/test_migration_0004.py`

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
from finances.db.orm import AccountRow, Base, FeedAccountRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0004_feed_accounts.py"
COLUMNS = [
    ("id", "INTEGER", False),
    ("account_id", "INTEGER", False),
    ("provider_account_id", "VARCHAR(200)", False),
]
UNIQUES = [
    ("uq_feed_accounts_account_id", ["account_id"]),
    ("uq_feed_accounts_provider_account_id", ["provider_account_id"]),
]


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


@pytest.fixture
def at_0004(url: str) -> str:
    """A database upgraded to revision 0004 only, whatever later migrations exist."""
    command.upgrade(make_config(url), "0004")
    return url


@pytest.fixture
def with_accounts(at_0004: str) -> str:
    engine = get_engine(at_0004)
    with session_scope(engine) as session:
        session.add(AccountRow(name="Test Card", institution="Test Bank", type="credit_card"))
        session.add(AccountRow(name="Test Checking", institution="Test Bank", type="checking"))
    engine.dispose()
    return at_0004


def test_0004_follows_0003(url: str) -> None:
    scripts = ScriptDirectory.from_config(make_config(url))
    assert scripts.get_revision("0004").down_revision == "0003"
    assert len(scripts.get_heads()) == 1


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source


def test_upgrade_adds_one_table(at_0004: str) -> None:
    assert "feed_accounts" in table_names(at_0004)
    assert len(table_names(at_0004)) == 8
    assert versions(at_0004) == ["0004"]


def test_columns_keys_and_constraints(at_0004: str) -> None:
    columns = reflect(at_0004, "feed_accounts", "get_columns")
    assert [(c["name"], str(c["type"]), c["nullable"]) for c in columns] == COLUMNS
    assert [c["default"] for c in columns] == [None, None, None]
    primary_key = reflect(at_0004, "feed_accounts", "get_pk_constraint")
    assert (primary_key["name"], primary_key["constrained_columns"]) == ("pk_feed_accounts", ["id"])
    uniques = reflect(at_0004, "feed_accounts", "get_unique_constraints")
    assert sorted((u["name"], u["column_names"]) for u in uniques) == UNIQUES
    keys = reflect(at_0004, "feed_accounts", "get_foreign_keys")
    assert [(k["name"], k["constrained_columns"], k["referred_table"]) for k in keys] == [
        ("fk_feed_accounts_account_id_accounts", ["account_id"], "accounts")
    ]
    assert reflect(at_0004, "feed_accounts", "get_indexes") == []


def test_the_orm_class_matches_the_migrated_table(at_0004: str) -> None:
    declared = Base.metadata.tables["feed_accounts"]
    assert FeedAccountRow.__table__ is declared
    assert [(c.name, c.nullable) for c in declared.columns] == [
        (name, nullable) for name, _, nullable in COLUMNS
    ]
    found = {
        (constraint.name, tuple(column.name for column in constraint.columns))
        for constraint in declared.constraints
        if type(constraint).__name__ == "UniqueConstraint"
    }
    assert found == {(name, tuple(columns)) for name, columns in UNIQUES}


def test_one_mapping_per_account_and_per_aggregator_account(with_accounts: str) -> None:
    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        session.add(FeedAccountRow(account_id=1, provider_account_id="ACT-1"))
        session.add(FeedAccountRow(account_id=2, provider_account_id="ACT-2"))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(FeedAccountRow(account_id=1, provider_account_id="ACT-3"))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(FeedAccountRow(account_id=2, provider_account_id="ACT-1"))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(FeedAccountRow(account_id=99, provider_account_id="ACT-9"))
    engine.dispose()


def test_downgrade_removes_only_the_table(with_accounts: str) -> None:
    command.downgrade(make_config(with_accounts), "0003")
    assert "feed_accounts" not in table_names(with_accounts)
    assert len(table_names(with_accounts)) == 7
    assert versions(with_accounts) == ["0003"]
    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        assert session.query(AccountRow).count() == 2
    engine.dispose()
```

`tests/unit/test_simplefin.py`

```python
import base64
import json
from datetime import date
from pathlib import Path

import pytest

from finances.sync.feed import FeedTransaction
from finances.sync.simplefin import (
    NO_DESCRIPTION,
    ProviderAccount,
    ProviderAnswer,
    SyncError,
    claim_access_url,
    fetch_accounts,
    parse_account_set,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "simplefin"
ACCESS = "https://user123:secret456@bridge.simplefin.org/simplefin"
CLAIM = "https://bridge.simplefin.org/simplefin/claim/DEMO-TOKEN-1"


def payload(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def token(url: str) -> str:
    return base64.b64encode(url.encode()).decode()


class FakeTransport:
    """Answer every request with one status and body, and remember the requests."""

    def __init__(self, status: int, body: bytes) -> None:
        self.status, self.body = status, body
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append((method, url, dict(headers)))
        return self.status, self.body


def test_a_setup_token_is_claimed_with_one_post() -> None:
    transport = FakeTransport(200, (ACCESS + "\n").encode())
    assert claim_access_url("  " + token(CLAIM) + "\n", transport) == ACCESS
    assert transport.calls == [("POST", CLAIM, {"Content-Length": "0"})]


@pytest.mark.parametrize(
    "bad",
    [
        "not base64!",
        token("http://bridge.simplefin.org/simplefin/claim/X"),
        token("https://bridge.simplefin.org.evil.example/claim/X"),
        token("https://evilsimplefin.org/claim/X"),
        token("https://simplefin.org.example/claim/X"),
        token("https://example.com/simplefin/claim/X"),
        token("https://user:pass@bridge.simplefin.org/claim/X"),
        token("ftp://bridge.simplefin.org/claim/X"),
        base64.b64encode("https://bridge.simplefin.org/é".encode()).decode(),
        "",
    ],
)
def test_a_setup_token_that_is_not_a_simplefin_https_url_is_refused_unsent(bad: str) -> None:
    transport = FakeTransport(200, ACCESS.encode())
    with pytest.raises(SyncError) as caught:
        claim_access_url(bad, transport)
    assert str(caught.value) == "setup token is not valid"
    assert transport.calls == []


def test_a_used_setup_token() -> None:
    with pytest.raises(SyncError) as caught:
        claim_access_url(token(CLAIM), FakeTransport(403, b""))
    assert str(caught.value) == "setup token was already used or does not exist"


@pytest.mark.parametrize("status", [201, 400, 404, 500])
def test_another_answer_to_a_claim(status: int) -> None:
    with pytest.raises(SyncError) as caught:
        claim_access_url(token(CLAIM), FakeTransport(status, ACCESS.encode()))
    assert str(caught.value) == "aggregator refused the setup token"


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"\xff\xfe",
        b"https://bridge.simplefin.org/simplefin",
        b"http://user:pass@bridge.simplefin.org/simplefin",
        b"https://user:pass@example.com/simplefin",
        b"https://user@bridge.simplefin.org/simplefin",
        b"<html>Error</html>",
    ],
)
def test_a_claim_answer_that_is_not_a_usable_access_url(body: bytes) -> None:
    with pytest.raises(SyncError) as caught:
        claim_access_url(token(CLAIM), FakeTransport(200, body))
    assert str(caught.value) == "aggregator answer could not be read"


def test_fetch_sends_one_get_with_basic_auth_and_no_credentials_in_the_url() -> None:
    transport = FakeTransport(200, json.dumps({"accounts": []}).encode())
    answer = fetch_accounts(ACCESS, date(2026, 5, 1), date(2026, 5, 31), transport)
    assert answer == ProviderAnswer([], [])
    assert len(transport.calls) == 1
    method, url, headers = transport.calls[0]
    assert method == "GET"
    assert url == (
        "https://bridge.simplefin.org/simplefin/accounts"
        "?start-date=1777593600&end-date=1780272000&pending=1"
    )
    assert headers == {"Authorization": "Basic " + base64.b64encode(b"user123:secret456").decode()}
    assert "secret456" not in url


def test_fetch_keeps_a_port_and_a_trailing_slash_does_not_double() -> None:
    transport = FakeTransport(200, b'{"accounts": []}')
    fetch_accounts(
        "https://a:b@beta-bridge.simplefin.org:8443/simplefin/",
        date(2026, 1, 1),
        date(2026, 1, 1),
        transport,
    )
    assert transport.calls[0][1] == (
        "https://beta-bridge.simplefin.org:8443/simplefin/accounts"
        "?start-date=1767225600&end-date=1767312000&pending=1"
    )


@pytest.mark.parametrize(
    "stored",
    [
        "",
        "https://bridge.simplefin.org/simplefin",
        "http://a:b@bridge.simplefin.org/simplefin",
        "https://a:b@example.com/simplefin",
        "https://a:b@[bad/simplefin",
    ],
)
def test_a_stored_access_url_that_is_not_usable_is_not_sent(stored: str) -> None:
    transport = FakeTransport(200, b'{"accounts": []}')
    with pytest.raises(SyncError) as caught:
        fetch_accounts(stored, date(2026, 5, 1), date(2026, 5, 31), transport)
    assert str(caught.value) == "stored aggregator access is not valid"
    assert transport.calls == []


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (403, "aggregator access was revoked or is wrong"),
        (402, "aggregator subscription needs payment"),
        (500, "aggregator answered with an error"),
        (404, "aggregator answered with an error"),
        (204, "aggregator answered with an error"),
    ],
)
def test_fetch_statuses(status: int, message: str) -> None:
    with pytest.raises(SyncError) as caught:
        fetch_accounts(ACCESS, date(2026, 5, 1), date(2026, 5, 31), FakeTransport(status, b"{}"))
    assert str(caught.value) == message


def account_json(**changes: object) -> dict:
    account = {"id": "A", "name": "N", "currency": "USD", "balance": "1", "balance-date": 1}
    account.update(changes)
    return account


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"[]",
        b"{}",
        b'{"accounts": {}}',
        b'{"accounts": [{"id": "A"}]}',
        b'{"accounts": [7]}',
        json.dumps({"accounts": [account_json(balance="1.234")]}).encode(),
        json.dumps({"accounts": [account_json(**{"balance-date": "x"})]}).encode(),
        json.dumps(
            {
                "accounts": [
                    account_json(
                        transactions=[{"id": "T", "posted": 1, "amount": "abc", "description": "D"}]
                    )
                ]
            }
        ).encode(),
        json.dumps(
            {
                "accounts": [
                    account_json(transactions=[{"id": "T", "amount": "1.00", "description": "D"}])
                ]
            }
        ).encode(),
        b'{"accounts": [], "errlist": [{"code": "gen.api"}]}',
        b'{"accounts": [], "connections": [{"name": "X"}]}',
    ],
)
def test_an_answer_that_cannot_be_read(body: bytes) -> None:
    with pytest.raises(SyncError) as caught:
        fetch_accounts(ACCESS, date(2026, 5, 1), date(2026, 5, 31), FakeTransport(200, body))
    assert str(caught.value) == "aggregator answer could not be read"
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


def test_a_version_2_account_set() -> None:
    answer = parse_account_set(payload("account_set_v2"))
    assert answer.messages == ["Example Savings Bank needs you to sign in again."]
    assert answer.accounts == [
        ProviderAccount(
            provider_account_id="ACT-card-1",
            name="Example Rewards Card",
            institution="Example Card Bank",
            currency="USD",
            balance_cents=-123456,
            balance_date=date(2026, 6, 1),
            transactions=[
                FeedTransaction(
                    "TRN-1", date(2026, 5, 29), -450, "ACME COFFEE #12", False, date(2026, 5, 28)
                ),
                FeedTransaction(
                    "TRN-2", date(2026, 5, 31), -2599, "FOOBAR GROCERY", True, date(2026, 5, 31)
                ),
                FeedTransaction("TRN-3", date(2026, 6, 1), -1000, NO_DESCRIPTION, True, None),
                FeedTransaction(
                    "TRN-4", date(2026, 5, 31), 50000, "PAYMENT THANK YOU", False, None
                ),
            ],
        ),
        ProviderAccount(
            "ACT-sav-1",
            "Example Savings",
            "Example Savings Bank",
            "USD",
            1000000,
            date(2026, 5, 31),
            [],
        ),
        ProviderAccount(
            "ACT-eur-1",
            "Example Euro Account",
            "Example Savings Bank",
            "EUR",
            100,
            date(2026, 6, 1),
            [],
        ),
    ]


def test_a_version_1_account_set() -> None:
    answer = parse_account_set(payload("account_set_v1"))
    assert answer == ProviderAnswer(
        accounts=[
            ProviderAccount(
                "ACT-card-1",
                "Example Rewards Card",
                "Example Card Bank",
                "USD",
                -9901,
                date(2026, 6, 2),
                [FeedTransaction("TRN-9", date(2026, 6, 1), -9901, "ACME HARDWARE", False, None)],
            )
        ],
        messages=["Example Card Bank: connection may need attention"],
    )


def test_no_description_is_the_placeholder() -> None:
    assert NO_DESCRIPTION == "(no description)"


def test_messages_are_made_printable_short_and_blank_ones_are_left_out() -> None:
    raw = {
        "accounts": [],
        "errlist": [{"code": "gen.api", "msg": "x" * 300}, {"code": "gen.api", "msg": " \n\t "}],
        "errors": ["\u001b[31mRED\u001b[0m   alert"],
    }
    assert parse_account_set(raw).messages == ["x" * 200, "[31mRED[0m alert"]


def test_an_account_whose_institution_is_unknown_has_an_empty_institution() -> None:
    raw = {
        "accounts": [
            {
                "id": 7,
                "name": "N",
                "conn_id": "MISSING",
                "currency": "USD",
                "balance": "0",
                "balance-date": 0,
            }
        ]
    }
    account = parse_account_set(raw).accounts[0]
    assert (account.provider_account_id, account.institution, account.balance_date) == (
        "7",
        "",
        date(1970, 1, 1),
    )


def test_amounts_without_cents_and_with_one_decimal() -> None:
    raw = {
        "accounts": [
            {
                "id": "A",
                "name": "N",
                "currency": "USD",
                "balance": "-12",
                "balance-date": 0,
                "transactions": [{"id": "T", "posted": 86400, "amount": "3.5", "description": "D"}],
            }
        ]
    }
    account = parse_account_set(raw).accounts[0]
    assert (account.balance_cents, account.transactions[0].amount_cents) == (-1200, 350)
    assert account.transactions[0].posted_date == date(1970, 1, 2)
```

`tests/unit/test_transport.py`

```python
import io
import urllib.error
import urllib.request

import pytest

from finances.sync import transport as transport_module
from finances.sync.simplefin import SyncError
from finances.sync.transport import TIMEOUT_SECONDS, urllib_transport

URL = "https://bridge.simplefin.org/simplefin/accounts?pending=1"


class FakeResponse(io.BytesIO):
    def __init__(self, status: int, body: bytes) -> None:
        super().__init__(body)
        self.status = status


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list:
    """Replace urlopen so that no request leaves the machine; remember what it was given."""
    calls: list = []

    def fake(request: urllib.request.Request, timeout: float) -> FakeResponse:
        calls.append((request, timeout))
        return FakeResponse(200, b'{"accounts": []}')

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return calls


def test_the_timeout_is_a_minute() -> None:
    assert TIMEOUT_SECONDS == 60


def test_a_get_returns_status_and_body(opened: list) -> None:
    status, body = urllib_transport("GET", URL, {"Authorization": "Basic abc"})
    assert (status, body) == (200, b'{"accounts": []}')
    request, timeout = opened[0]
    assert (request.get_method(), request.full_url, request.data, timeout) == ("GET", URL, None, 60)
    assert request.get_header("Authorization") == "Basic abc"


def test_a_post_sends_an_empty_body(opened: list) -> None:
    urllib_transport("POST", URL, {"Content-Length": "0"})
    request, _ = opened[0]
    assert (request.get_method(), request.data) == ("POST", b"")
    assert request.get_header("Content-length") == "0"


@pytest.mark.parametrize("code", [402, 403, 404, 500])
def test_an_http_error_is_returned_as_its_status_with_no_body(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    def fake(request, timeout):
        raise urllib.error.HTTPError(URL, code, "no", {}, io.BytesIO(b"SECRET BODY"))

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert urllib_transport("GET", URL, {}) == (code, b"")


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
    def fake(request, timeout):
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    with pytest.raises(SyncError) as caught:
        urllib_transport("GET", URL, {})
    assert str(caught.value) == "could not reach the aggregator"
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


def test_the_module_uses_the_standard_library_only() -> None:
    names = set(vars(transport_module))
    assert {"urllib", "urllib_transport", "TIMEOUT_SECONDS", "SyncError"} <= names
    assert not names & {"requests", "httpx", "aiohttp", "ssl"}
```

`tests/integration/test_sync_runner.py`

```python
import json
from datetime import date

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import FeedItemRow, TransactionRow
from finances.db.repositories import create_account, latest_balance, map_feed_account
from finances.sync.runner import SYNC_DAYS, AccountSync, SyncReport, run_sync
from finances.sync.simplefin import SyncError

ACCESS = "https://user123:secret456@bridge.simplefin.org/simplefin"
TODAY = date(2026, 6, 1)


def epoch(day: date, hour: int = 12) -> int:
    from datetime import UTC, datetime

    return int(datetime(day.year, day.month, day.day, hour, tzinfo=UTC).timestamp())


def account(provider_id: str, balance: str, *transactions: dict, currency: str = "USD") -> dict:
    return {
        "id": provider_id,
        "name": f"Example {provider_id}",
        "conn_id": "CON-1",
        "currency": currency,
        "balance": balance,
        "balance-date": epoch(TODAY, 3),
        "transactions": list(transactions),
    }


def txn(feed_id: str, day: int, amount: str, text: str, pending: bool = False) -> dict:
    posted = 0 if pending else epoch(date(2026, 5, day))
    return {
        "id": feed_id,
        "posted": posted,
        "amount": amount,
        "description": text,
        "transacted_at": epoch(date(2026, 5, day), 9),
        "pending": pending,
    }


class Bridge:
    """A fake SimpleFIN Bridge that answers each GET with the next prepared account set."""

    def __init__(self, *answers: dict) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append((method, url))
        return 200, json.dumps(self.answers.pop(0)).encode()


def answer(*accounts: dict, errors: tuple[str, ...] = ()) -> dict:
    return {
        "errlist": [{"code": "con.auth", "msg": text} for text in errors],
        "connections": [
            {"conn_id": "CON-1", "name": "Example Bank", "org_id": "O", "sfin_url": "x"}
        ],
        "accounts": list(accounts),
    }


def ledger(session: Session, account_id: int) -> list[tuple]:
    stmt = (
        select(TransactionRow, FeedItemRow.feed_id)
        .join(FeedItemRow, FeedItemRow.transaction_id == TransactionRow.id)
        .where(TransactionRow.account_id == account_id)
        .order_by(TransactionRow.id)
    )
    return [
        (feed_id, row.posted_date.day, row.amount_cents, row.is_pending)
        for row, feed_id in session.execute(stmt).all()
    ]


@pytest.fixture
def session(db_engine: Engine):
    """A card (id 1) fed by ACT-card and a checking account (id 2) fed by ACT-chk."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Example Bank", "credit_card", last4="1111")
        create_account(opened, "Test Checking", "Example Bank", "checking", last4="2222")
        create_account(opened, "Test Unfed", "Example Bank", "savings", last4="3333")
        map_feed_account(opened, 1, "ACT-card")
        map_feed_account(opened, 2, "ACT-chk")
        yield opened


def run(session: Session, bridge: Bridge, **more) -> SyncReport:
    return run_sync(session, ACCESS, today=TODAY, transport=bridge, **more)


def test_the_window_is_thirty_days() -> None:
    assert SYNC_DAYS == 30


def test_one_request_for_the_last_thirty_days(session: Session) -> None:
    bridge = Bridge(answer())
    run(session, bridge)
    assert bridge.calls == [
        (
            "GET",
            "https://bridge.simplefin.org/simplefin/accounts"
            f"?start-date={epoch(date(2026, 5, 2), 0)}"
            f"&end-date={epoch(date(2026, 6, 2), 0)}&pending=1",
        )
    ]
    bridge = Bridge(answer())
    run(session, bridge, days=7)
    assert f"start-date={epoch(date(2026, 5, 25), 0)}&" in bridge.calls[0][1]


def test_each_mapped_account_is_applied(session: Session) -> None:
    bridge = Bridge(
        answer(
            account(
                "ACT-card",
                "-29.49",
                txn("C-1", 20, "-4.50", "ACME COFFEE"),
                txn("C-2", 25, "-24.99", "FOOBAR"),
            ),
            account("ACT-chk", "1500.00", txn("K-1", 28, "1500.00", "PAYROLL")),
        )
    )
    report = run(session, bridge)
    assert report.messages == []
    assert [
        (item.provider_account_id, item.account_id, item.problem) for item in report.accounts
    ] == [
        ("ACT-card", 1, None),
        ("ACT-chk", 2, None),
    ]
    card, checking = report.accounts[0].pull, report.accounts[1].pull
    assert (card.inserted, card.feed_total_cents, card.balance_cents, card.balance_date) == (
        2,
        -2949,
        -2949,
        TODAY,
    )
    assert (checking.inserted, checking.balance_cents) == (1, 150000)
    assert ledger(session, 1) == [("C-1", 20, -450, False), ("C-2", 25, -2499, False)]
    assert ledger(session, 2) == [("K-1", 28, 150000, False)]
    assert latest_balance(session, 1).balance_cents == -2949


def test_unmapped_missing_and_foreign_accounts_are_reported_not_applied(session: Session) -> None:
    map_feed_account(session, 3, "ACT-gone")
    bridge = Bridge(
        answer(
            account("ACT-new", "1.00", txn("N-1", 20, "1.00", "X")),
            account("ACT-card", "-1.00", txn("C-1", 20, "-1.00", "ACME"), currency="EUR"),
            account("ACT-chk", "0.00"),
        )
    )
    report = run(session, bridge)
    assert report.accounts == [
        AccountSync("ACT-new", None, None, "not mapped"),
        AccountSync("ACT-card", 1, None, "currency is not USD"),
        AccountSync("ACT-chk", 2, report.accounts[2].pull, None),
        AccountSync("ACT-gone", 3, None, "not in the aggregator's answer"),
    ]
    assert report.accounts[2].pull.inserted == 0
    assert session.scalars(select(TransactionRow)).all() == []


def test_a_hold_that_is_no_longer_delivered_is_removed(session: Session) -> None:
    first = answer(
        account(
            "ACT-card",
            "-4.50",
            txn("C-1", 20, "-4.50", "ACME COFFEE"),
            txn("H-1", 30, "-80.00", "HOTEL HOLD", pending=True),
            txn("H-2", 31, "-5.00", "GAS HOLD", pending=True),
        )
    )
    second = answer(
        account(
            "ACT-card",
            "-87.25",
            txn("C-1", 20, "-4.50", "ACME COFFEE"),
            txn("C-3", 31, "-82.75", "HOTEL"),
            txn("H-2", 31, "-5.00", "GAS HOLD", pending=True),
        )
    )
    bridge = Bridge(first, second)
    run(session, bridge)
    assert ledger(session, 1) == [
        ("C-1", 20, -450, False),
        ("H-1", 30, -8000, True),
        ("H-2", 31, -500, True),
    ]
    pull = run(session, bridge).accounts[0].pull
    assert (pull.inserted, pull.removed, pull.unchanged, pull.drift_cents) == (1, 1, 2, 0)
    assert ledger(session, 1) == [
        ("C-1", 20, -450, False),
        ("H-2", 31, -500, True),
        ("C-3", 31, -8275, False),
    ]


def test_holds_are_kept_when_the_answer_carries_a_message(session: Session) -> None:
    first = answer(account("ACT-card", "0.00", txn("H-1", 30, "-80.00", "HOLD", pending=True)))
    second = answer(account("ACT-card", "0.00"), errors=("Example Bank: incomplete listing",))
    bridge = Bridge(first, second)
    run(session, bridge)
    report = run(session, bridge)
    assert report.messages == ["Example Bank: incomplete listing"]
    assert report.accounts[0].pull.removed == 0
    assert ledger(session, 1) == [("H-1", 30, -8000, True)]


def test_holds_older_than_the_window_are_not_removed(session: Session) -> None:
    bridge = Bridge(
        answer(account("ACT-card", "0.00", txn("H-old", 1, "-1.00", "OLD HOLD", pending=True))),
        answer(account("ACT-card", "0.00")),
    )
    run(session, bridge, days=40)
    pull = run(session, bridge).accounts[0].pull
    assert pull.removed == 0
    assert ledger(session, 1) == [("H-old", 1, -100, True)]


def test_holds_of_another_account_are_not_removed(session: Session) -> None:
    bridge = Bridge(
        answer(account("ACT-chk", "0.00", txn("H-1", 30, "-1.00", "HOLD", pending=True))),
        answer(
            account("ACT-card", "0.00"),
            account("ACT-chk", "0.00", txn("H-1", 30, "-1.00", "HOLD", pending=True)),
        ),
    )
    run(session, bridge)
    report = run(session, bridge)
    assert [item.pull.removed for item in report.accounts] == [0, 0]
    assert ledger(session, 2) == [("H-1", 30, -100, True)]


def test_a_feed_one_account_cannot_take_does_not_stop_the_others(session: Session) -> None:
    bridge = Bridge(
        answer(
            account("ACT-card", "-1.00", txn("X" * 101, 20, "-1.00", "ACME")),
            account("ACT-chk", "5.00", txn("K-1", 20, "5.00", "DEPOSIT")),
        )
    )
    report = run(session, bridge)
    assert report.accounts[0] == AccountSync(
        "ACT-card", 1, None, "feed has an unusable transaction id"
    )
    assert report.accounts[1].pull.inserted == 1
    assert ledger(session, 1) == []
    assert latest_balance(session, 1) is None


def test_a_failed_fetch_raises_and_writes_nothing(session: Session) -> None:
    def refused(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        return 403, b""

    with pytest.raises(SyncError) as caught:
        run_sync(session, ACCESS, today=TODAY, transport=refused)
    assert str(caught.value) == "aggregator access was revoked or is wrong"
    assert session.scalars(select(TransactionRow)).all() == []


def test_with_no_mapping_nothing_is_applied(db_engine: Engine) -> None:
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Example Bank", "credit_card", last4="1111")
        report = run_sync(
            opened,
            ACCESS,
            today=TODAY,
            transport=Bridge(answer(account("ACT-card", "1.00", txn("C-1", 20, "1.00", "X")))),
        )
        assert report == SyncReport([AccountSync("ACT-card", None, None, "not mapped")], [])
        assert opened.scalars(select(TransactionRow)).all() == []


def test_posted_rows_that_are_not_delivered_again_are_kept(session: Session) -> None:
    bridge = Bridge(
        answer(account("ACT-card", "-4.50", txn("C-1", 20, "-4.50", "ACME COFFEE"))),
        answer(account("ACT-card", "-4.50")),
    )
    run(session, bridge)
    pull = run(session, bridge).accounts[0].pull
    assert (pull.removed, pull.unchanged) == (0, 0)
    assert ledger(session, 1) == [("C-1", 20, -450, False)]
```

## Tests to write

`tests/integration/test_feed_account_repositories.py`, on the `db_engine` fixture:

- R1: `to_feed_account` for a row; the `FeedAccount` fields in order and frozen
- R2: a first mapping; a second aggregator account for the same account keeps the id and replaces the old one, which is then free for another account; the same pair twice; the `ValueError` with its exact message, and that nothing changed after it; a mapping for an account that does not exist raises `IntegrityError`
- R3: empty, then id order
- R4: posted rows, statement rows, rows of another account, and rows before `since` are left out; a row dated `since` is included; transaction id order; a pending row whose feed id was replaced (Phase 17a) appears under its current feed id
- that a later session sees what an earlier one wrote

Every line and branch of `finances.sync`, `finances.db`, and `finances.domain` must be reached by a test.

## Rules for this phase

- **The network.** Only `transport.py` opens connections. No test opens one: every test passes a fake transport or replaces `urllib.request.urlopen`. Running the test suite with the network switched off must give the same result.
- **Secrets.** The access URL and the setup token are credentials. They never appear in a URL sent anywhere (the access URL's credentials go in a header), in an exception message, in a log, in printed output, or in a test that is not plainly synthetic. Nothing in this phase logs or prints.
- **Constant messages.** The thirteen messages in R2, R6, R7, R15, R18, and R20 are the only ones this phase creates. Messages from SimpleFIN are passed on only after cleaning (R12), in `ProviderAnswer.messages`. Nothing from an answer goes into an exception.
- **Money is `int` cents**, read with `parse_money`. No `float`.
- **Signs.** SimpleFIN's signs are the account holder's (positive is money in) and are kept as they are. If a real card's balance comes with the opposite sign, the drift of Phase 17a shows it; do not guess a correction.
- **Database access** stays in `src/finances/db/`. No dialect-specific SQL. The shipped migrations are not edited.
- **Synthetic data only** in tests: invented institutions, accounts, ids, and amounts, and credentials that are plainly fake.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, at least N + 84 passed, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/integration/test_migration_0004.py tests/unit/test_simplefin.py tests/unit/test_transport.py tests/integration/test_sync_runner.py --no-cov` | exactly `84 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| each of the four searches below | no output |
| `git diff HEAD --stat -- src/finances/sync/feed.py src/finances/sync/service.py src/finances/ingest src/finances/cli src/finances/config.py src/finances/db/migrations/versions/0001_accounts.py src/finances/db/migrations/versions/0002_statements.py src/finances/db/migrations/versions/0003_feed.py tests/conftest.py tests/fixtures pyproject.toml` | no output |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.sync --cov=finances.db --cov=finances.domain --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -E "^ *(import|from) +(requests|httpx|urllib|socket|http|aiohttp|ssl|ftplib|smtplib)" -- src/finances ':!src/finances/sync' ':!src/finances/config.py'`

`git grep -n --untracked -E "^ *(import|from) +(urllib\.request|urllib\.error|socket|http\.client|ssl)" -- src/finances ':!src/finances/sync/transport.py'`

`git grep -n --untracked -E "float|(^|[^_a-zA-Z.])print\(|logging" -- src/finances/sync`

`git grep -n --untracked -E "finances\.(ingest|cli)" -- src/finances/sync src/finances/db src/finances/domain`

The first search must stay silent: the only network library used anywhere outside `src/finances/sync/` is `urllib.parse` in `config.py`, which parses text and opens nothing, and the search leaves `config.py` out for that reason.

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 17b: syncing from SimpleFIN (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. Under "Deviations", list your design choices (private helpers, constants) and anything you did that the spec did not ask for, or `None`. Do not contact SimpleFIN, and do not report anything about a real SimpleFIN account.

In your final message, give the output line of each acceptance command, and for each of R1 to R22 the name of a test that covers it.
