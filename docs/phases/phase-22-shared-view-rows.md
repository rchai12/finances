# Phase 22: one source for the rows the command line and the web show

## Goal

**No behaviour changes.** Every command prints exactly what it prints today and every page shows exactly what it shows today. Only where the code lives changes.

Today each view that has both a terminal command and a web page builds its rows twice: once as Rich table cells in `cli/`, once as dictionaries in `web/app.py`. `fin sync run` also keeps its own 60-line loop over the links, although `sync/runner.run_links` does the same and the web already uses it. Phase 16d paid for this: "which links to run" and "how many new accounts" had to be added in both places. After this phase:

- a new package, `finances.views`, builds each view's rows once, as small frozen dataclasses whose field names are the keys the templates already use;
- the command line only turns rows into table cells (`dataclasses.astuple`), and the web only hands them to the templates;
- `fin sync run` uses `run_links`, which now also says what kind of failure stopped a link, so the command keeps its exact messages;
- the setup offers for new SimpleFIN accounts move out of the web page into `views/sync.py`, ready for a future command;
- the account-name lookup, written eight times, becomes one repository function, and the `••1234` mask one function.

This is the first of two clean-up phases from the code audit. Phase 23 will give text rules, column limits, and typed-input checks one home.

## Read first

- `AGENTS.md` (layering: `cli` and `web` are thin), `docs/architecture.md`
- `src/finances/cli/sync.py` (`run_command`, `status_command`, `_run_cells`, `_drift`, `_balance_date`, `_account_names`), `src/finances/cli/accounts.py` (`list_command`), `src/finances/cli/people.py` (`list_command`), `src/finances/cli/listing.py` (`_transaction_cells`, `_account_names`, `_BULLETS`)
- `src/finances/web/app.py` (`_transaction_row`, `_keychain`, `_drift`, `_sync_row`, `_run_row`, `_accounts_page`, `_people_page`, `_sync_page`, the `POST /sync/run` route)
- `src/finances/sync/runner.py` (`LinkRun`, `run_links`), `tests/unit/test_run_links.py`
- `tests/e2e/test_cli_sync.py`, `tests/integration/test_web_pages.py`, `tests/integration/test_web_new_accounts.py`: they pin today's output, and must pass unchanged

## Starting state

- Phase 10 is committed. `git status --short` prints nothing.
- Run `.venv/bin/python scripts/check.py`; it ends with `All checks passed.`. Note the number of tests passed in its `tests` step. This spec calls it **N**. It is `1986` when Phase 10 is the last phase built.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/views/__init__.py`, `format.py`, `accounts.py`, `people.py`, `transactions.py`, `sync.py` | new (Part 1) |
| `src/finances/db/repositories.py` | new: `account_names` |
| `src/finances/sync/runner.py` | `LinkRun` gains `failure` and `cause`; three constants (Part 2) |
| `src/finances/cli/sync.py`, `cli/accounts.py`, `cli/people.py`, `cli/listing.py` | use the views and `run_links` (Part 3) |
| `src/finances/web/app.py` | uses the views (Part 3) |
| `docs/architecture.md` | one paragraph (R16) |
| `tests/integration/test_views.py`, `tests/unit/test_link_run_failures.py` | new: given, do not change |
| `docs/progress.md` | one new entry |

No template, migration, or existing test changes.

## Out of scope

- Any change to what a command prints, its exit code, or what a page shows. If a test pinned today's output, it passes unchanged; if you find yourself wanting to change one, stop and report.
- Phase 23's work: `domain/text.py`, column-limit constants, moving input checks (feed id, owner, account type) into the repositories, `_fail` in `cli/common.py`, `_squeezed`, the zone helper.
- Splitting `web/app.py` or `db/repositories.py`.
- A new command or page.

## Dependencies

None new.

## Design

```python
# src/finances/views/format.py
BULLETS = "••"
def mask_last4(last4: str | None) -> str: ...            # "••1234", or "" for None or ""
def drift_text(pull: FeedPull | None) -> str: ...        # format_cents(drift), or ""
def balance_date_text(pull: FeedPull | None) -> str: ... # the balance date in ISO form, or ""
def last_pull_text(pull: FeedPull | None) -> str: ...    # "YYYY-MM-DD HH:MM UTC", or "never"
```

```python
# src/finances/views/accounts.py
@dataclass(frozen=True)
class AccountRow:
    name: str
    institution: str
    type: str       # the type's value
    last4: str      # mask_last4
    active: str     # "yes" or "no"
    owner: str      # a person's name, "Joint", or ""

def account_rows(session: Session, *, include_inactive: bool = False) -> list[AccountRow]: ...
```

```python
# src/finances/views/people.py
@dataclass(frozen=True)
class PersonRow:
    name: str
    owns: str          # account names joined with ", "
    cardholders: str   # cardholder names joined with ", "

def people_rows(session: Session) -> list[PersonRow]: ...
```

```python
# src/finances/views/transactions.py
@dataclass(frozen=True)
class TransactionRow:
    date: str
    account: str
    description: str
    amount: str
    card: str
    section: str
    person: str

def transaction_row(item: Transaction, person: str | None, names: dict[int, str]) -> TransactionRow: ...
```

```python
# src/finances/views/sync.py
@dataclass(frozen=True)
class StatusRow:
    link: str
    account: str
    feed_account: str
    keychain: str       # "yes", "no", or "unknown"
    last_pull: str
    balance_date: str
    drift: str

@dataclass(frozen=True)
class RunRow:
    link: str
    account: str
    feed_account: str
    new: str
    changed: str
    removed: str
    same: str
    drift: str
    problem: str

@dataclass(frozen=True)
class SetupOffer:
    link: str
    feed_account: str
    name: str
    institution: str
    guess: AccountGuess
    owner: str | None
    suggestion: str | None

def keychain_state(link: str) -> str: ...
def status_rows(session: Session) -> list[StatusRow]: ...
def run_rows(runs: list[LinkRun], names: dict[int, str]) -> list[RunRow]: ...
def waiting_counts(session: Session, runs: list[LinkRun]) -> list[tuple[str, int]]: ...
def simplefin_messages(runs: list[LinkRun]) -> list[tuple[str, str]]: ...
def unmapped_accounts(session: Session) -> list[Account]: ...
def setup_offers(session: Session) -> list[SetupOffer]: ...
```

```python
# src/finances/db/repositories.py
def account_names(session: Session) -> dict[int, str]: ...   # every account, closed included
```

```python
# src/finances/sync/runner.py
KEYCHAIN_FAILED = "keychain"
NOT_SET_UP = "not set up"
AGGREGATOR_FAILED = "aggregator"


@dataclass(frozen=True)
class LinkRun:
    # What one link's sync did, or why it could not run.
    link: str
    report: SyncReport | None
    error: str | None
    failure: str | None = field(default=None, compare=False)
    cause: str | None = field(default=None, compare=False)
```

`compare=False` keeps the equality of Phase 16b's `LinkRun` tests, which build a `LinkRun` from three values.

## Requirements

### Part 1: the views

- **R1.** `finances.views` imports from `finances.db`, `finances.domain`, `finances.analysis`, and `finances.sync` only, never from `finances.cli`, `finances.web`, `typer`, `rich`, `fastapi`, or `jinja2`. Its rows hold already formatted text.
- **R2.** `views/format.py` as in the design. `last_pull_text` formats `pulled_at` with `%Y-%m-%d %H:%M UTC`.
- **R3.** `account_rows(session, include_inactive=...)` gives one `AccountRow` per account of `list_accounts(session, include_inactive=...)`, in its order: the type's value, `mask_last4`, `yes` or `no`, and the owner from `load_attribution` (`Joint` for a joint account, empty when there is none). This is what `fin accounts list` and `GET /accounts` show today.
- **R4.** `people_rows(session)` gives one `PersonRow` per person of `list_people`, in its order: the names of the accounts, closed included, the person owns, in `list_accounts` order; and the person's cardholder names, sorted. Both joined with `, `.
- **R5.** `transaction_row(item, person, names)`: the posted date in ISO form, `names[item.account_id]`, the description, `format_cents` of the amount, `mask_last4` of the card digits, the section or empty, and the person or empty.
- **R6.** `keychain_state(link)` is `yes` when `load_access_url` finds an access URL, `no` when it finds none, and `unknown` when it raises `SyncError`.
- **R7.** `status_rows(session)` gives one `StatusRow` per mapping of `list_feed_accounts(session)`, in its order: the link, the account's name, the SimpleFIN id, `keychain_state` (read once per link), `last_pull_text` of the latest pull, and `balance_date_text` and `drift_text` of the latest pull with a balance.
- **R8.** `run_rows(runs, names)` gives, for each run with a report, in order, one `RunRow` per `AccountSync`: the link; the account's name, or empty when `account_id` is `None`; the SimpleFIN id; the pull's `inserted`, `updated`, `removed`, `unchanged` as text, each empty without a pull; `drift_text` of the pull; and the problem or empty.
- **R9.** `waiting_counts(session, runs)` gives, for each run with a report, in order, `(link, count)` with `count = len(list_new_feed_accounts(session, link))`, leaving out counts of 0. `simplefin_messages(runs)` gives `(link, message)` for each message of each run with a report, in order.
- **R10.** `unmapped_accounts(session)` gives the active accounts of `list_accounts(session)`, in its order, that have no mapping under any link. `setup_offers(session)` gives one `SetupOffer` per account of `list_new_feed_accounts(session)`, in its order: the seen account's link, id, name, and institution; `guess_account(name, institution)`; `guess_owner(link, people's names)`; and `suggest_existing(guess, candidates)` where the candidates are `(name, last4)` of `unmapped_accounts`. This is the logic `_sync_page` holds today.
- **R11.** `account_names(session)` maps the id of every account, closed included, to its name.

### Part 2: what stopped a link

- **R12.** `run_links` keeps its behaviour and its `error` texts, and also sets `failure` and `cause`: a `SyncError` reading the keychain gives `KEYCHAIN_FAILED` and the error's text; no access URL gives `NOT_SET_UP` and `None`; a `SyncError` from the sync gives `AGGREGATOR_FAILED` and the error's text. A link that ran has both `None`.

### Part 3: the interfaces use them

- **R13.** The command line:
  - `fin accounts list`, `fin people list`, and `fin transactions list` build their rows with `account_rows`, `people_rows`, and `transaction_row` and add each row's cells in field order;
  - `fin sync status` uses `status_rows`;
  - `fin sync run` calls `run_links(engine, links, today=..., transport=transport.urllib_transport, days=days)`, then prints, for each run with a `failure`, in order, on stderr: `Error: CAUSE` for `KEYCHAIN_FAILED`, `Error: link LINK is not set up (run: fin sync link --link LINK)` for `NOT_SET_UP`, and `Error: link LINK: CAUSE` for `AGGREGATOR_FAILED`. It builds the table from `run_rows`, the new-accounts lines from `waiting_counts`, and SimpleFIN's lines from `simplefin_messages`; it exits 1 when any run failed. `run_sync` is no longer imported by the command line.
  - The listing of statements and every other place that needs account names use `account_names`.
- **R14.** The web: `GET /accounts` and its pages after a refused form use `account_rows` (active only, or all with `closed=true`); `GET /people` uses `people_rows`; `GET /transactions` uses `transaction_row`; the SimpleFIN page uses `status_rows`, `setup_offers`, and `unmapped_accounts`, and turns each offer into the dictionary the template reads today (`guess` as `name`, `institution`, the type's value, and `last4` or empty; `owner` and `suggestion` as text or empty); `POST /sync/run` uses `run_rows`, `waiting_counts`, and `simplefin_messages`. Templates receive the dataclass rows directly: their attribute names are the keys used today.
- **R15.** These private helpers are gone, because the views replace them: in `cli/sync.py` `_run_cells`, `_drift`, `_balance_date`, `_account_names`; in `cli/listing.py` `_transaction_cells`, `_account_names`, `_BULLETS`; in `web/app.py` `_transaction_row`, `_keychain`, `_drift`, `_sync_row`, `_run_row`, `_BULLETS`. No `•` remains in `cli/` or `web/app.py`.

### Part 4: the documents

- **R16.** In `docs/architecture.md`, after the paragraph that starts `transactions.source` records where a row came from, add a paragraph: `The command line and the web show the same views. finances.views builds each view's rows once, as plain text in small dataclasses (Phase 22); cli renders them with Rich and web with Jinja, and neither builds rows of its own.` (with `finances.views`, `cli`, and `web` in code style).

## Given tests

Create these two files exactly as shown and do not change them. If one fails, the code is wrong. Every existing test, in particular those of the command line and the web pages, must pass unchanged: they are this phase's safety net. There are no tests for you to write.

`tests/integration/test_views.py`

```python
from dataclasses import astuple, fields
from datetime import UTC, date, datetime

import keyring
import keyring.backend
import keyring.errors
import pytest
from finances.views.accounts import AccountRow, account_rows
from finances.views.format import (
    BULLETS,
    balance_date_text,
    drift_text,
    last_pull_text,
    mask_last4,
)
from finances.views.people import PersonRow, people_rows
from finances.views.sync import (
    RunRow,
    SetupOffer,
    StatusRow,
    keychain_state,
    run_rows,
    setup_offers,
    simplefin_messages,
    status_rows,
    unmapped_accounts,
    waiting_counts,
)
from finances.views.transactions import TransactionRow, transaction_row
from sqlalchemy import Engine

from finances.db.engine import session_scope
from finances.db.orm import AccountRow as AccountTable
from finances.db.repositories import (
    account_names,
    create_account,
    create_feed_pull,
    create_person,
    map_feed_account,
    record_seen_feed_account,
    set_account_owner,
    set_cardholder_alias,
    set_feed_account_ignored,
)
from finances.domain.feed_setup import AccountGuess
from finances.domain.models import AccountType, DataSource, FeedPull, Transaction
from finances.sync.runner import AccountSync, LinkRun, SyncReport

SERVICE = "finances-simplefin"
DAY = date(2026, 5, 9)
NOON = datetime(2026, 5, 9, 12, 30, tzinfo=UTC)


class BrokenKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringError("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.KeyringError("locked")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.KeyringError("locked")


def pull(**changes: object) -> FeedPull:
    values = {
        "id": 1,
        "account_id": 1,
        "inserted": 3,
        "updated": 1,
        "removed": 0,
        "unchanged": 7,
        "feed_total_cents": -100,
        "balance_cents": -100,
        "balance_date": date(2026, 5, 8),
        "drift_cents": -250,
        "pulled_at": NOON,
    }
    return FeedPull(**{**values, **changes})


@pytest.fixture
def household(db_engine: Engine) -> Engine:
    """Card (Alex), Checking (Joint), Savings (no owner, closed), Old Card (Sam, closed)."""
    with session_scope(db_engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        savings = create_account(session, "Test Savings", "Test Bank", "savings", last4="3333")
        old = create_account(session, "Test Old Card", "Test Bank", "credit_card", last4="4444")
        alex = create_person(session, "Alex")
        sam = create_person(session, "Sam")
        set_account_owner(session, card.id, alex.id)
        set_account_owner(session, checking.id, None)
        set_account_owner(session, old.id, sam.id)
        set_cardholder_alias(session, "SAM DOE", sam.id)
        set_cardholder_alias(session, "S DOE", sam.id)
        session.get(AccountTable, savings.id).is_active = False
        session.get(AccountTable, old.id).is_active = False
    return db_engine


# Formatting


def test_the_mask() -> None:
    assert BULLETS == "••"
    assert (mask_last4("1234"), mask_last4(None), mask_last4("")) == ("••1234", "", "")


def test_pull_texts() -> None:
    assert (drift_text(pull()), drift_text(pull(drift_cents=None)), drift_text(None)) == (
        "-$2.50",
        "",
        "",
    )
    assert (balance_date_text(pull()), balance_date_text(pull(balance_date=None))) == (
        "2026-05-08",
        "",
    )
    assert balance_date_text(None) == ""
    assert (last_pull_text(pull()), last_pull_text(None)) == ("2026-05-09 12:30 UTC", "never")


# Accounts and people


def test_account_rows(household: Engine) -> None:
    with session_scope(household) as session:
        assert account_rows(session) == [
            AccountRow("Test Card", "Test Bank", "credit_card", "••1111", "yes", "Alex"),
            AccountRow("Test Checking", "Test Bank", "checking", "", "yes", "Joint"),
        ]
        every = account_rows(session, include_inactive=True)
    assert [row.name for row in every] == [
        "Test Card",
        "Test Checking",
        "Test Old Card",
        "Test Savings",
    ]
    assert every[2:] == [
        AccountRow("Test Old Card", "Test Bank", "credit_card", "••4444", "no", "Sam"),
        AccountRow("Test Savings", "Test Bank", "savings", "••3333", "no", ""),
    ]


def test_an_account_row_lists_its_cells_in_column_order() -> None:
    names = [item.name for item in fields(AccountRow)]
    assert names == ["name", "institution", "type", "last4", "active", "owner"]
    assert astuple(AccountRow("a", "b", "c", "d", "e", "f")) == ("a", "b", "c", "d", "e", "f")


def test_people_rows(household: Engine) -> None:
    with session_scope(household) as session:
        assert people_rows(session) == [
            PersonRow("Alex", "Test Card", ""),
            PersonRow("Sam", "Test Old Card", "S DOE, SAM DOE"),
        ]
    assert [item.name for item in fields(PersonRow)] == ["name", "owns", "cardholders"]


def test_account_names_include_closed_accounts(household: Engine) -> None:
    with session_scope(household) as session:
        assert account_names(session) == {
            1: "Test Card",
            2: "Test Checking",
            3: "Test Savings",
            4: "Test Old Card",
        }


def test_no_people_or_accounts(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        assert (account_rows(session), people_rows(session), account_names(session)) == (
            [],
            [],
            {},
        )


# Transactions


def transaction(**changes: object) -> Transaction:
    values = {
        "id": 1,
        "account_id": 2,
        "statement_id": None,
        "posted_date": date(2026, 5, 3),
        "transaction_date": None,
        "amount_cents": -450,
        "description": "ACME COFFEE",
        "section": "purchases",
        "card_last4": "2222",
        "cardholder": None,
        "external_id": None,
        "source": DataSource.STATEMENT,
        "is_pending": False,
        "fingerprint": "f" * 64,
        "created_at": NOON,
    }
    return Transaction(**{**values, **changes})


def test_transaction_row() -> None:
    names = {2: "Test Checking"}
    assert transaction_row(transaction(), "Sam", names) == TransactionRow(
        "2026-05-03", "Test Checking", "ACME COFFEE", "-$4.50", "••2222", "purchases", "Sam"
    )
    assert transaction_row(transaction(card_last4=None, section=None), None, names) == (
        TransactionRow("2026-05-03", "Test Checking", "ACME COFFEE", "-$4.50", "", "", "")
    )
    assert [item.name for item in fields(TransactionRow)] == [
        "date",
        "account",
        "description",
        "amount",
        "card",
        "section",
        "person",
    ]


# SimpleFIN status


def test_keychain_state(keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = "https://u:p@bridge.simplefin.org/x"
    assert (keychain_state("alex"), keychain_state("sam")) == ("yes", "no")


def test_keychain_state_when_the_keychain_fails() -> None:
    previous = keyring.get_keyring()
    keyring.set_keyring(BrokenKeyring())
    try:
        assert keychain_state("alex") == "unknown"
    finally:
        keyring.set_keyring(previous)


def test_status_rows(household: Engine, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = "https://u:p@bridge.simplefin.org/x"
    with session_scope(household) as session:
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
        create_feed_pull(
            session,
            account_id=1,
            inserted=0,
            updated=0,
            removed=0,
            unchanged=1,
            feed_total_cents=-100,
            balance_cents=None,
            balance_date=None,
            drift_cents=None,
        )
    with session_scope(household) as session:
        rows = status_rows(session)
    assert [astuple(row)[:4] for row in rows] == [
        ("alex", "Test Card", "ACT-1", "yes"),
        ("sam", "Test Checking", "ACT-2", "no"),
    ]
    assert rows[0].last_pull.endswith(" UTC") and len(rows[0].last_pull) == 20
    assert (rows[0].balance_date, rows[0].drift) == ("2026-05-09", "-$2.50")
    assert rows[1] == StatusRow("sam", "Test Checking", "ACT-2", "no", "never", "", "")


def test_no_status_rows_without_mappings(household: Engine) -> None:
    with session_scope(household) as session:
        assert status_rows(session) == []


# Sync now and fin sync run


def test_run_rows_messages_and_failures() -> None:
    report = SyncReport(
        [
            AccountSync("ACT-1", 1, pull(), None),
            AccountSync("ACT-9", None, None, "not mapped"),
            AccountSync("ACT-2", 2, None, "currency is not USD"),
        ],
        ["Probe note"],
    )
    runs = [
        LinkRun("alex", report, None),
        LinkRun("bob", None, "link bob is not set up"),
        LinkRun("sam", SyncReport([], ["Sam note", "Other note"]), None),
    ]
    assert run_rows(runs, {1: "Test Card", 2: "Test Checking"}) == [
        RunRow("alex", "Test Card", "ACT-1", "3", "1", "0", "7", "-$2.50", ""),
        RunRow("alex", "", "ACT-9", "", "", "", "", "", "not mapped"),
        RunRow("alex", "Test Checking", "ACT-2", "", "", "", "", "", "currency is not USD"),
    ]
    assert simplefin_messages(runs) == [
        ("alex", "Probe note"),
        ("sam", "Sam note"),
        ("sam", "Other note"),
    ]
    assert [item.name for item in fields(RunRow)] == [
        "link",
        "account",
        "feed_account",
        "new",
        "changed",
        "removed",
        "same",
        "drift",
        "problem",
    ]


def test_waiting_counts_only_links_that_ran(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        for link, feed_id in (("sam", "S-1"), ("alex", "A-1"), ("alex", "A-2"), ("bob", "B-1")):
            record_seen_feed_account(session, link, feed_id, "Probe", "Probe Bank", DAY)
        record_seen_feed_account(session, "kim", "K-1", "Probe", "Probe Bank", DAY)
        set_feed_account_ignored(session, "kim", "K-1", True)
    runs = [
        LinkRun("sam", SyncReport([], []), None),
        LinkRun("bob", None, "link bob is not set up"),
        LinkRun("kim", SyncReport([], []), None),
        LinkRun("alex", SyncReport([], []), None),
    ]
    with session_scope(db_engine) as session:
        assert waiting_counts(session, runs) == [("sam", 1), ("alex", 2)]


# Setting up new SimpleFIN accounts


def test_unmapped_accounts_are_open_and_have_no_mapping(household: Engine) -> None:
    with session_scope(household) as session:
        map_feed_account(session, 1, "ACT-1", "alex")
        assert [item.name for item in unmapped_accounts(session)] == ["Test Checking"]


def test_setup_offers(household: Engine) -> None:
    with session_scope(household) as session:
        create_account(session, "Probe Savings", "Probe Bank", "savings", last4="4321")
        create_person(session, "Kim")
        record_seen_feed_account(
            session, "kim", "K-1", "High Yield Savings 4321", "Probe Bank", DAY
        )
        record_seen_feed_account(session, "kim", "K-2", "Brokerage", "", DAY)
        record_seen_feed_account(session, "kim", "K-3", "Ignored", "Probe Bank", DAY)
        set_feed_account_ignored(session, "kim", "K-3", True)
    with session_scope(household) as session:
        offers = setup_offers(session)
    assert offers == [
        SetupOffer(
            "kim",
            "K-1",
            "High Yield Savings 4321",
            "Probe Bank",
            AccountGuess("High Yield Savings 4321", "Probe Bank", AccountType.SAVINGS, "4321"),
            "Kim",
            "Probe Savings",
        ),
        SetupOffer(
            "kim",
            "K-2",
            "Brokerage",
            "",
            AccountGuess("Brokerage", "", AccountType.OTHER, None),
            "Kim",
            None,
        ),
    ]


def test_no_offers_without_seen_accounts(household: Engine) -> None:
    with session_scope(household) as session:
        assert setup_offers(session) == []
```

`tests/unit/test_link_run_failures.py`

```python
import base64
import json
from datetime import date

import keyring
import keyring.backend
import keyring.errors
from sqlalchemy import Engine

from finances.sync.runner import (
    AGGREGATOR_FAILED,
    KEYCHAIN_FAILED,
    NOT_SET_UP,
    LinkRun,
    SyncReport,
    run_links,
)

TODAY = date(2026, 5, 20)
SERVICE = "finances-simplefin"
ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"


def key(access: str) -> str:
    user, password = access.split("//")[1].split("@")[0].split(":")
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


class BrokenKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringError("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.KeyringError("locked")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.KeyringError("locked")


def test_the_kinds_of_failure() -> None:
    assert (KEYCHAIN_FAILED, NOT_SET_UP, AGGREGATOR_FAILED) == (
        "keychain",
        "not set up",
        "aggregator",
    )


def test_a_failure_and_its_cause_do_not_change_equality() -> None:
    assert LinkRun("alex", None, "link alex is not set up") == LinkRun(
        "alex", None, "link alex is not set up", NOT_SET_UP, None
    )
    assert LinkRun("alex", None, "x", KEYCHAIN_FAILED, "a") == LinkRun(
        "alex", None, "x", AGGREGATOR_FAILED, "b"
    )


def test_each_failure_says_what_kind_it_is(db_engine: Engine, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    empty = {"errlist": [], "connections": [], "accounts": []}

    def bridge(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        if headers["Authorization"] == key(ALEX):
            return 403, b""
        return 200, json.dumps(empty).encode()

    alex, bob = run_links(db_engine, ["alex", "bob"], today=TODAY, transport=bridge)
    assert (alex.error, alex.failure, alex.cause) == (
        "link alex: aggregator access was revoked or is wrong",
        AGGREGATOR_FAILED,
        "aggregator access was revoked or is wrong",
    )
    assert (bob.error, bob.failure, bob.cause) == ("link bob is not set up", NOT_SET_UP, None)
    keychain.passwords[(SERVICE, "sam")] = "https://sam-user:sam-pass@bridge.simplefin.org/x"
    (sam,) = run_links(db_engine, ["sam"], today=TODAY, transport=bridge)
    assert (sam.report, sam.error, sam.failure, sam.cause) == (SyncReport([], []), None, None, None)


def test_a_keychain_failure(db_engine: Engine) -> None:
    previous = keyring.get_keyring()
    keyring.set_keyring(BrokenKeyring())
    try:
        (alex,) = run_links(db_engine, ["alex"], today=TODAY, transport=lambda *_: (500, b""))
    finally:
        keyring.set_keyring(previous)
    assert (alex.error, alex.failure, alex.cause) == (
        "link alex: could not use the system keychain",
        KEYCHAIN_FAILED,
        "could not use the system keychain",
    )
```

## Rules for this phase

- **Same output, byte for byte.** Commands, exit codes, stderr, and pages are unchanged.
- **Layering.** `views` sits between the domain and the interfaces; `cli` and `web` render only.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; in the `tests` step, 0 failed, 0 skipped, 0 xfailed, at least N + 21 passed |
| `.venv/bin/python -m pytest tests/integration/test_views.py tests/unit/test_link_run_failures.py --no-cov` | exactly `21 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| each of the three searches below | no output |
| `git diff HEAD --stat -- tests src/finances/web/templates src/finances/db/migrations` | nothing (only new test files, which `git status` lists) |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.views --cov=finances.cli --cov=finances.web --cov=finances.sync --cov=finances.db --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n -E "def (_run_cells|_transaction_cells|_sync_row|_run_row|_transaction_row|_drift|_balance_date|_keychain|_account_names)\(|_BULLETS|u2022|run_sync|guess_account|guess_owner|suggest_existing" -- src/finances/cli/sync.py src/finances/cli/accounts.py src/finances/cli/people.py src/finances/cli/listing.py src/finances/web/app.py`

`git grep -n -E "(item|account)\.id: (item|account)\.name" -- src/finances/cli src/finances/web`

`git grep -n --untracked -E "^ *(from|import) +(finances\.(cli|web)|typer|rich|fastapi|jinja2)" -- src/finances/views`

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 22: one source for view rows (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. In your final message, give the last ten lines of `scripts/check.py`'s output and the output line of each other acceptance command.
