# Phase 17a: the feed core

## Goal

Build the half of the aggregator feed that does not depend on which aggregator is chosen. A later phase (17b) will fetch data from a provider and turn it into an `AccountFeed`: a plain list of transactions, a list of removed ids, and a balance, for one account. This phase stores an `AccountFeed`.

After this phase, `apply_feed(session, account_id, feed)`:

- stores new feed transactions as **provisional** rows (`source = aggregator`);
- changes a stored row when the feed reports it differently, and turns a pending row into its posted row **without changing the stored id**, so that a category or note attached to the row later survives;
- deletes rows the feed says no longer exist;
- never changes or deletes a row that a statement has confirmed;
- records the balance the feed reports, and measures **drift**: how far that balance moved beyond what the posted rows explain.

This phase has no network code, no provider, no command, and no token. It is storage and arithmetic.

## Read first

- `AGENTS.md`: "Running commands", "Privacy rules", "Money and signs", "Architecture rules"
- `docs/architecture.md`: "Data flow", "Privacy boundary", "Data model"
- `src/finances/domain/models.py`, `src/finances/db/orm.py`, `src/finances/db/repositories.py`
- `src/finances/db/migrations/versions/0002_statements.py` and `tests/integration/test_migration_0002.py`: the pattern the new migration follows
- `src/finances/ingest/service.py`: how the statement import uses the repositories
- `tests/conftest.py`: `db_url`, `db_engine`

## Starting state

- Phase 6 is committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `1038` when Phase 6 is the last phase built.
- The newest migration is `0002`. The `transactions` table already has `source`, `is_pending`, and `fingerprint` columns, and a unique constraint on (`account_id`, `fingerprint`). `DataSource.AGGREGATOR` exists. No code stores an aggregator row yet.
- `src/finances/sync/` does not exist.
- `add_balance_snapshot` returns the stored snapshot unchanged when one exists for the same account, date, and source. That is right for statements and wrong for a feed, which can report a new balance twice in a day. This phase adds `set_balance_snapshot` and leaves `add_balance_snapshot` alone.
- `finances.db` and `finances.domain` are at 100% line and branch coverage.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/migrations/versions/0003_feed.py` | new: tables `feed_items` and `feed_pulls` |
| `src/finances/domain/models.py` | one class added: `FeedPull` |
| `src/finances/db/orm.py` | added: `FeedItemRow`, `FeedPullRow`, `to_feed_pull` |
| `src/finances/db/repositories.py` | nine functions added (Part 3) |
| `src/finances/sync/__init__.py` | new: a docstring only |
| `src/finances/sync/feed.py` | new: `FeedError`, `FeedTransaction`, `AccountFeed`, `feed_fingerprint` |
| `src/finances/sync/service.py` | new: `apply_feed` |
| `tests/integration/test_migration_0003.py`, `tests/integration/test_feed_service.py` | given, do not change |
| `tests/unit/test_feed_models.py`, `tests/integration/test_feed_repositories.py` | new, written by you |
| `docs/progress.md` | one new entry |

You may add private helpers and module constants to `sync/service.py` and `db/repositories.py`. Existing classes, functions, and columns are not changed: `Transaction`, `NewTransaction`, `TransactionRow`, `insert_transactions`, and `add_balance_snapshot` stay exactly as they are. Do not change any existing test, `tests/conftest.py`, or any file outside the table.

## Out of scope

- Any network code, HTTP library, provider name, access token, or `keyring`. Phase 17b.
- Any command (`fin sync ...`), and any change to `fin transactions list` or `fin doctor`.
- Matching a feed row to a statement line, or a statement upgrading a provisional row. Phase 8. In this phase a row is "confirmed by a statement" only when a test sets its `source` to `statement` by hand.
- Mapping a provider's account to one of ours. `apply_feed` is given the account id.
- A column added to `transactions`. The feed id lives in its own table so that the ledger table and its tests stay as they are.
- Categories, merchant names from the provider, or any other field the neutral feed does not have.
- Scheduling, retries, and logging of pulls.
- New dependencies.

## Dependencies

None new.

## Design

### The tables (migration `0003`, `down_revision = "0002"`)

`feed_items` says which feed transaction a stored transaction came from.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | Integer | no | primary key `pk_feed_items` |
| `account_id` | Integer | no | foreign key `fk_feed_items_account_id_accounts` to `accounts.id` |
| `feed_id` | String(100) | no | the provider's id for the transaction |
| `transaction_id` | Integer | no | foreign key `fk_feed_items_transaction_id_transactions` to `transactions.id` |

Unique constraints: `uq_feed_items_account_feed` on (`account_id`, `feed_id`), and `uq_feed_items_transaction_id` on (`transaction_id`). No index.

`feed_pulls` has one row for each feed that was applied to an account.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | Integer | no | primary key `pk_feed_pulls` |
| `account_id` | Integer | no | foreign key `fk_feed_pulls_account_id_accounts` to `accounts.id`; index `ix_feed_pulls_account_id` |
| `inserted`, `updated`, `removed`, `unchanged` | Integer | no | counts of rows |
| `feed_total_cents` | BigInteger | no | see R19 |
| `balance_cents` | BigInteger | yes | |
| `balance_date` | Date | yes | |
| `drift_cents` | BigInteger | yes | |
| `pulled_at` | DateTime(timezone=True) | no | set by the ORM default, as `created_at` is elsewhere |

The migration file follows `0002_statements.py`: it imports nothing from `finances`, uses no `server_default`, names every constraint, and its `downgrade` drops both tables and nothing else.

### The feed, in `src/finances/sync/feed.py`

```python
class FeedError(Exception):
    """Raised when a feed cannot be applied. Nothing is written."""


@dataclass(frozen=True)
class FeedTransaction:
    """One transaction as the feed reports it. Amounts are from the account holder's side."""

    feed_id: str
    posted_date: date
    amount_cents: int
    description: str
    is_pending: bool = False
    transaction_date: date | None = None
    card_last4: str | None = None
    replaces_feed_id: str | None = None


@dataclass(frozen=True)
class AccountFeed:
    """Everything one pull delivers for one account."""

    transactions: list[FeedTransaction] = field(default_factory=list)
    removed_feed_ids: list[str] = field(default_factory=list)
    balance_cents: int | None = None
    balance_date: date | None = None


def feed_fingerprint(account_id: int, feed_id: str) -> str:
    """Return the fingerprint stored for a transaction that came from the feed."""
```

`replaces_feed_id` is how a provider says "this posted transaction is the pending one you saw earlier under another id". Amounts and balances already follow `AGENTS.md`: money leaving the holder is negative, and a card balance owed is negative. Turning a provider's signs into these is Phase 17b's work.

### The domain class, in `src/finances/domain/models.py`

```python
@dataclass(frozen=True)
class FeedPull:
    """What applying one aggregator feed did to one account, as stored."""

    id: int
    account_id: int
    inserted: int
    updated: int
    removed: int
    unchanged: int
    feed_total_cents: int
    balance_cents: int | None
    balance_date: date | None
    drift_cents: int | None
    pulled_at: datetime
```

### The service, in `src/finances/sync/service.py`

```python
def apply_feed(session: Session, account_id: int, feed: AccountFeed) -> FeedPull:
    """Store what the feed delivers for one account. The caller commits."""
```

### Layering

`sync` imports from `db` and `domain`. It imports nothing from `ingest` or `cli`. `db` and `domain` import nothing from `sync`.

## Requirements

### Part 1: the migration and the ORM

- **R1.** Migration `0003` creates the two tables exactly as designed, and its `downgrade` removes them and leaves every other table and row in place.
- **R2.** `FeedItemRow` (table `feed_items`) and `FeedPullRow` (table `feed_pulls`) declare the same columns, in the same order, with the same types, nullability, and constraint names as the migration. `pulled_at` has the same default as `StatementRow.imported_at`.
- **R3.** `to_feed_pull(row)` returns the `FeedPull` for a row, with `pulled_at` in UTC as the other converters do it.
- **R4.** `FeedPull` is the frozen dataclass under Design, with those fields in that order and no defaults.

### Part 2: the feed types

- **R5.** `FeedError`, `FeedTransaction`, and `AccountFeed` are as under Design: frozen dataclasses, those fields in that order, those defaults. Two `AccountFeed()` values do not share a list.
- **R6.** `feed_fingerprint(account_id, feed_id)` is the SHA-256 hex digest of the UTF-8 text `feed`, a newline, the account id in decimal, a newline, and the feed id. For account 7 and id `abc-123` the text is `"feed\n7\nabc-123"`. A statement fingerprint can never equal it, because statement fingerprints start with the account id.

### Part 3: repository functions

All take the session first and leave the commit to the caller. All return domain objects, never ORM rows.

- **R7.** `get_account(session, account_id) -> Account | None` returns the account with that id, or `None`.
- **R8.** `set_balance_snapshot(session, account_id, as_of_date, balance_cents, source) -> BalanceSnapshot` stores the balance for that account, date, and source. When a snapshot for the three already exists, its `balance_cents` is replaced and its id is kept.
- **R9.** `find_feed_transactions(session, account_id, feed_ids) -> dict[str, Transaction]` maps each of the given feed ids that has a `feed_items` row in that account to its transaction. Ids of other accounts and unknown ids are absent. It accepts any iterable, including an empty one, and works for thousands of ids (ask in chunks, as `existing_fingerprints` does).
- **R10.** `insert_feed_transaction(session, item: NewTransaction, feed_id: str) -> Transaction` adds the transaction and its `feed_items` row, and returns the stored transaction.
- **R11.** `update_feed_transaction(session, transaction_id, *, feed_id, posted_date, transaction_date, amount_cents, description, card_last4, is_pending, fingerprint) -> Transaction` sets those seven columns of the transaction and the `feed_id` of its `feed_items` row, and returns the stored transaction. Nothing else about the row changes: its id, account, source, statement, section, cardholder, external id, and creation time stay. When the transaction does not exist or has no `feed_items` row, it raises `ValueError("transaction did not come from the feed")`.
- **R12.** `delete_feed_transaction(session, transaction_id) -> bool` deletes the transaction and its `feed_items` row and returns `True`. When the transaction has no `feed_items` row it deletes nothing and returns `False`: a row that did not come from the feed can never be deleted through this function.
- **R13.** `feed_posted_total(session, account_id) -> int` is the sum of `amount_cents` over the account's transactions that have a `feed_items` row and are not pending, whatever their `source`. It is `0` when there are none, and always an `int`.
- **R14.** `create_feed_pull(session, *, account_id, inserted, updated, removed, unchanged, feed_total_cents, balance_cents, balance_date, drift_cents) -> FeedPull` adds one record and returns it.
- **R15.** `latest_feed_pull(session, account_id, *, with_balance=False) -> FeedPull | None` returns the account's pull with the highest id, or `None`. With `with_balance=True` only pulls whose `balance_cents` is not null are considered.

### Part 4: applying a feed

`apply_feed` first checks the whole feed (R16). Only when every check passes does it write anything.

- **R16.** Each of these raises `FeedError` with the message shown, and after any of them the database holds exactly what it held before the call. The account is checked first. When a feed breaks several of the other rules, the message of any one of them is acceptable.

  | Check | Message |
  |---|---|
  | no account has `account_id` | `account not found` |
  | a transaction's `feed_id`, a `replaces_feed_id` that is not `None`, or a removed id is **unusable**: empty, longer than 100 characters, or with whitespace at either end | `feed has an unusable transaction id` |
  | a description is empty once its whitespace is collapsed | `feed has an empty description` |
  | a `card_last4` that `validate_last4` rejects | `feed has unusable card digits` |
  | two transactions of the feed have the same `feed_id` | `feed has a duplicate transaction id` |
  | an id is both a transaction's `feed_id` and a removed id | `feed removes a transaction it also delivers` |
  | exactly one of `balance_cents` and `balance_date` is `None` | `feed balance and its date must come together` |

  No message contains anything from the feed.
- **R17.** A description is stored with runs of whitespace made one space and outer whitespace removed, then cut to its first 500 characters, then with trailing whitespace removed again. Everywhere below, "the description" is that stored form.
- **R18.** Transactions are handled first, in feed order, then removals. For each transaction:
  1. **Find the stored row.** It is the stored transaction whose feed id in this account equals `feed_id`. If there is none, and `replaces_feed_id` names a stored transaction of this account whose `source` is `aggregator`, that one is the stored row.
  2. **No stored row: insert.** The new row has `source` `aggregator`, the feed's `posted_date`, `transaction_date`, `amount_cents`, `card_last4`, and `is_pending`, the description, the fingerprint `feed_fingerprint(account_id, feed_id)`, and `None` for `statement_id`, `section`, `cardholder`, and `external_id`. Its feed id is `feed_id`. Counted in `inserted`.
  3. **A stored row whose `source` is `statement`: leave it.** Counted in `unchanged`. A statement is the record; the feed never changes what one confirmed.
  3. **A stored row that already has exactly the feed's values** (posted date, transaction date, amount, description, card digits, pending flag, and feed id): nothing is written. Counted in `unchanged`.
  4. **Otherwise: update in place** with `update_feed_transaction`, giving it the feed's values, the feed id `feed_id`, and the fingerprint for that id. The row keeps its id. Counted in `updated`. This is also how a pending row becomes posted, under the same id or under a new one.

  Then, for each distinct removed id: when it names a stored transaction of this account whose `source` is `aggregator`, that row is deleted and counted in `removed`. An unknown id, an id whose row was just given a new feed id by step 5, and a row whose `source` is `statement` are passed over without counting.
- **R19.** `feed_total_cents` is `feed_posted_total` for the account after all of R18.
- **R20.** When the feed has a balance, it is stored with `set_balance_snapshot` for `balance_date` with source `aggregator`. When it has none, no snapshot is written.
- **R21.** `drift_cents` is `None` when the feed has no balance, and when no earlier pull of this account has a balance. Otherwise, with *previous* the account's latest earlier pull that has a balance:

  `drift = (balance − previous.balance_cents) − (feed_total − previous.feed_total_cents)`

  It is `0` when the balance moved by exactly the posted amounts that arrived, changed, or left since that pull. Pending rows are not part of it.
- **R22.** `apply_feed` stores one `feed_pulls` row with the four counts, `feed_total_cents`, the feed's balance and date (or `None`), and the drift, and returns it as a `FeedPull`. A feed that changes nothing still stores a row.
- **R23.** `apply_feed` raises nothing but `FeedError` for the checks of R16. It never calls `commit` or `rollback`.

## Given tests

Create these two files exactly as shown and do not change them. If one of their tests fails, the production code is wrong.

`tests/integration/test_migration_0003.py`

```python
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import finances.db
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, Base, FeedItemRow, FeedPullRow, TransactionRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0003_feed.py"
COLUMNS = {
    "feed_items": [
        ("id", "INTEGER", False),
        ("account_id", "INTEGER", False),
        ("feed_id", "VARCHAR(100)", False),
        ("transaction_id", "INTEGER", False),
    ],
    "feed_pulls": [
        ("id", "INTEGER", False),
        ("account_id", "INTEGER", False),
        ("inserted", "INTEGER", False),
        ("updated", "INTEGER", False),
        ("removed", "INTEGER", False),
        ("unchanged", "INTEGER", False),
        ("feed_total_cents", "BIGINT", False),
        ("balance_cents", "BIGINT", True),
        ("balance_date", "DATE", True),
        ("drift_cents", "BIGINT", True),
        ("pulled_at", "DATETIME", False),
    ],
}
UNIQUES = {
    "feed_items": [
        ("uq_feed_items_account_feed", ["account_id", "feed_id"]),
        ("uq_feed_items_transaction_id", ["transaction_id"]),
    ],
    "feed_pulls": [],
}
FOREIGN_KEYS = {
    "feed_items": [
        ("fk_feed_items_account_id_accounts", ["account_id"], "accounts"),
        ("fk_feed_items_transaction_id_transactions", ["transaction_id"], "transactions"),
    ],
    "feed_pulls": [("fk_feed_pulls_account_id_accounts", ["account_id"], "accounts")],
}
INDEXES = {"feed_items": [], "feed_pulls": [("ix_feed_pulls_account_id", ["account_id"])]}
TABLES = sorted(COLUMNS)


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


def transaction(account_id: int, fingerprint: str) -> TransactionRow:
    return TransactionRow(
        account_id=account_id,
        posted_date=date(2026, 1, 5),
        amount_cents=-450,
        description="ACME COFFEE",
        source="aggregator",
        fingerprint=fingerprint,
    )


def pull(account_id: int, **changes: object) -> FeedPullRow:
    values = {"inserted": 0, "updated": 0, "removed": 0, "unchanged": 0, "feed_total_cents": 0}
    return FeedPullRow(account_id=account_id, **{**values, **changes})


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def at_0003(url: str) -> str:
    """A database upgraded to revision 0003 only, whatever later migrations exist."""
    command.upgrade(make_config(url), "0003")
    return url


@pytest.fixture
def with_rows(at_0003: str) -> str:
    """Two accounts, and three transactions: ids 1 and 2 in account 1, id 3 in account 2."""
    engine = get_engine(at_0003)
    with session_scope(engine) as session:
        session.add(AccountRow(name="Test Card", institution="Test Bank", type="credit_card"))
        session.add(AccountRow(name="Test Checking", institution="Test Bank", type="checking"))
        session.flush()
        session.add(transaction(1, "a" * 64))
        session.add(transaction(1, "b" * 64))
        session.add(transaction(2, "c" * 64))
    engine.dispose()
    return at_0003


def test_0003_follows_0002(url: str) -> None:
    scripts = ScriptDirectory.from_config(make_config(url))
    assert scripts.get_revision("0003").down_revision == "0002"
    assert len(scripts.get_heads()) == 1


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source
    assert source.count("DateTime(timezone=True)") == 1


def test_upgrade_adds_the_two_tables(at_0003: str) -> None:
    assert table_names(at_0003) == [
        "accounts",
        "alembic_version",
        "balance_snapshots",
        "feed_items",
        "feed_pulls",
        "statements",
        "transactions",
    ]
    assert versions(at_0003) == ["0003"]


@pytest.mark.parametrize("table", TABLES)
def test_columns_types_and_nulls(at_0003: str, table: str) -> None:
    columns = reflect(at_0003, table, "get_columns")
    found = [(column["name"], str(column["type"]), column["nullable"]) for column in columns]
    assert found == COLUMNS[table]
    assert [column["default"] for column in columns] == [None] * len(columns)


@pytest.mark.parametrize("table", TABLES)
def test_primary_key_is_named(at_0003: str, table: str) -> None:
    primary_key = reflect(at_0003, table, "get_pk_constraint")
    assert primary_key["name"] == f"pk_{table}"
    assert primary_key["constrained_columns"] == ["id"]


@pytest.mark.parametrize("table", TABLES)
def test_unique_constraints(at_0003: str, table: str) -> None:
    uniques = reflect(at_0003, table, "get_unique_constraints")
    found = sorted((unique["name"], unique["column_names"]) for unique in uniques)
    assert found == UNIQUES[table]


@pytest.mark.parametrize("table", TABLES)
def test_foreign_keys(at_0003: str, table: str) -> None:
    keys = reflect(at_0003, table, "get_foreign_keys")
    found = sorted((key["name"], key["constrained_columns"], key["referred_table"]) for key in keys)
    assert found == FOREIGN_KEYS[table]
    assert all(key["referred_columns"] == ["id"] for key in keys)


@pytest.mark.parametrize("table", TABLES)
def test_indexes(at_0003: str, table: str) -> None:
    indexes = reflect(at_0003, table, "get_indexes")
    found = sorted((index["name"], index["column_names"]) for index in indexes)
    assert found == INDEXES[table]
    assert all(not index["unique"] for index in indexes)


@pytest.mark.parametrize("table", TABLES)
def test_the_orm_class_matches_the_migrated_table(at_0003: str, table: str) -> None:
    declared = Base.metadata.tables[table]
    columns = reflect(at_0003, table, "get_columns")
    assert [column.name for column in declared.columns] == [column["name"] for column in columns]
    assert [column.nullable for column in declared.columns] == [
        column["nullable"] for column in columns
    ]
    declared_uniques = {
        (constraint.name, tuple(column.name for column in constraint.columns))
        for constraint in declared.constraints
        if type(constraint).__name__ == "UniqueConstraint"
    }
    assert declared_uniques == {(name, tuple(columns)) for name, columns in UNIQUES[table]}
    assert {
        (index.name, tuple(column.name for column in index.columns)) for index in declared.indexes
    } == {(name, tuple(columns)) for name, columns in INDEXES[table]}


def test_upgrade_keeps_existing_transactions(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0002")
    engine = get_engine(url)
    with session_scope(engine) as session:
        session.add(AccountRow(name="Test Card", institution="Test Bank", type="credit_card"))
        session.flush()
        session.add(transaction(1, "a" * 64))
    engine.dispose()
    command.upgrade(config, "0003")
    engine = get_engine(url)
    with session_scope(engine) as session:
        assert [row.fingerprint for row in session.query(TransactionRow).all()] == ["a" * 64]
    engine.dispose()


def test_the_tables_work_with_the_orm(with_rows: str) -> None:
    engine = get_engine(with_rows)
    with session_scope(engine) as session:
        session.add(FeedItemRow(account_id=1, feed_id="feed-1", transaction_id=1))
        session.add(pull(1))
        session.add(
            pull(1, balance_cents=-(2**40), balance_date=date(2026, 1, 31), drift_cents=2**40 + 1)
        )
    with session_scope(engine) as session:
        assert session.query(FeedItemRow).one().feed_id == "feed-1"
        first, second = session.query(FeedPullRow).order_by(FeedPullRow.id).all()
        assert (first.balance_cents, first.balance_date, first.drift_cents) == (None, None, None)
        assert first.pulled_at is not None
        assert (second.balance_cents, second.drift_cents) == (-(2**40), 2**40 + 1)
        assert second.balance_date == date(2026, 1, 31)
    engine.dispose()


def test_a_feed_id_is_unique_within_one_account(with_rows: str) -> None:
    engine = get_engine(with_rows)
    with session_scope(engine) as session:
        session.add(FeedItemRow(account_id=1, feed_id="same", transaction_id=1))
        session.add(FeedItemRow(account_id=2, feed_id="same", transaction_id=3))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(FeedItemRow(account_id=1, feed_id="same", transaction_id=2))
    engine.dispose()


def test_a_transaction_has_at_most_one_feed_id(with_rows: str) -> None:
    engine = get_engine(with_rows)
    with session_scope(engine) as session:
        session.add(FeedItemRow(account_id=1, feed_id="one", transaction_id=1))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(FeedItemRow(account_id=1, feed_id="two", transaction_id=1))
    engine.dispose()


def test_a_feed_item_needs_a_real_transaction_and_account(with_rows: str) -> None:
    engine = get_engine(with_rows)
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(FeedItemRow(account_id=1, feed_id="one", transaction_id=99))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(FeedItemRow(account_id=99, feed_id="one", transaction_id=1))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(pull(99))
    engine.dispose()


def test_downgrade_removes_only_the_two_tables(with_rows: str) -> None:
    command.downgrade(make_config(with_rows), "0002")
    assert table_names(with_rows) == [
        "accounts",
        "alembic_version",
        "balance_snapshots",
        "statements",
        "transactions",
    ]
    assert versions(with_rows) == ["0002"]
    engine = get_engine(with_rows)
    with session_scope(engine) as session:
        assert session.query(TransactionRow).count() == 3
    engine.dispose()


def test_downgrade_then_upgrade_restores_the_tables(at_0003: str) -> None:
    config = make_config(at_0003)
    command.downgrade(config, "0002")
    command.upgrade(config, "0003")
    assert table_names(at_0003)[3:5] == ["feed_items", "feed_pulls"]
    assert reflect(at_0003, "feed_pulls", "get_indexes") != []
```

`tests/integration/test_feed_service.py` fixes the behavior of `apply_feed`, including every drift calculation.

```python
import hashlib
from datetime import date

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import BalanceSnapshotRow, FeedItemRow, FeedPullRow, TransactionRow
from finances.db.repositories import create_account, insert_transactions, latest_balance
from finances.domain.models import DataSource, FeedPull, NewTransaction
from finances.sync.feed import AccountFeed, FeedError, FeedTransaction, feed_fingerprint
from finances.sync.service import apply_feed

MAY = date(2026, 5, 1)


def day(number: int) -> date:
    return date(2026, 5, number)


def tx(feed_id: str, number: int, cents: int, text: str, **more: object) -> FeedTransaction:
    return FeedTransaction(feed_id, day(number), cents, text, **more)


def feed(*items: FeedTransaction, removed: tuple[str, ...] = (), balance=None, on=None):
    return AccountFeed(list(items), list(removed), balance, on)


def counts(pull: FeedPull) -> tuple[int, int, int, int]:
    return (pull.inserted, pull.updated, pull.removed, pull.unchanged)


def ledger(session: Session, account_id: int = 1) -> list[tuple]:
    """Every stored transaction of the account with its feed id, in id order."""
    stmt = (
        select(TransactionRow, FeedItemRow.feed_id)
        .outerjoin(FeedItemRow, FeedItemRow.transaction_id == TransactionRow.id)
        .where(TransactionRow.account_id == account_id)
        .order_by(TransactionRow.id)
    )
    return [
        (row.id, feed_id, row.posted_date.day, row.amount_cents, row.description, row.is_pending)
        for row, feed_id in session.execute(stmt).all()
    ]


@pytest.fixture
def session(db_engine: Engine):
    """A session on a migrated database with a card (id 1) and a checking account (id 2)."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card", last4="1111")
        create_account(opened, "Test Checking", "Test Bank", "checking", last4="2222")
        yield opened


def audit(session: Session, transaction_id: int) -> None:
    """Mark a stored row as confirmed by a statement, as Phase 8 will."""
    session.get(TransactionRow, transaction_id).source = "statement"
    session.flush()


def test_the_fingerprint_of_a_feed_row() -> None:
    expected = hashlib.sha256(b"feed\n7\nabc-123").hexdigest()
    assert feed_fingerprint(7, "abc-123") == expected
    assert feed_fingerprint(8, "abc-123") != expected
    assert feed_fingerprint(7, "abc-124") != expected


def test_the_first_feed_inserts_every_row(session: Session) -> None:
    pull = apply_feed(
        session,
        1,
        feed(
            tx("a", 1, -450, "ACME  COFFEE "),
            tx("b", 2, -1299, "FOOBAR GROCERY", transaction_date=MAY, card_last4="1111"),
            tx("c", 3, -700, "ACME GAS", is_pending=True),
        ),
    )
    assert counts(pull) == (3, 0, 0, 0)
    assert (pull.id, pull.account_id) == (1, 1)
    assert (pull.balance_cents, pull.balance_date, pull.drift_cents) == (None, None, None)
    assert pull.feed_total_cents == -1749
    assert pull.pulled_at.tzinfo is not None
    assert ledger(session) == [
        (1, "a", 1, -450, "ACME COFFEE", False),
        (2, "b", 2, -1299, "FOOBAR GROCERY", False),
        (3, "c", 3, -700, "ACME GAS", True),
    ]
    rows = session.scalars(select(TransactionRow).order_by(TransactionRow.id)).all()
    assert [row.source for row in rows] == ["aggregator"] * 3
    assert [row.fingerprint for row in rows] == [feed_fingerprint(1, name) for name in "abc"]
    assert [(row.transaction_date, row.card_last4) for row in rows] == [
        (None, None),
        (MAY, "1111"),
        (None, None),
    ]
    assert [(row.statement_id, row.section, row.cardholder, row.external_id) for row in rows] == [
        (None, None, None, None)
    ] * 3
    assert session.scalars(select(BalanceSnapshotRow)).all() == []


def test_the_same_feed_again_changes_nothing(session: Session) -> None:
    items = (tx("a", 1, -450, "ACME COFFEE"), tx("b", 2, -1299, "FOOBAR GROCERY"))
    apply_feed(session, 1, feed(*items))
    before = ledger(session)
    pull = apply_feed(session, 1, feed(*items))
    assert counts(pull) == (0, 0, 0, 2)
    assert pull.id == 2
    assert ledger(session) == before


def test_a_changed_row_is_updated_in_place(session: Session) -> None:
    apply_feed(session, 1, feed(tx("a", 1, -450, "ACME COFFEE"), tx("b", 2, -1299, "FOOBAR")))
    pull = apply_feed(
        session,
        1,
        feed(tx("a", 4, -475, "ACME COFFEE #12", card_last4="9999"), tx("b", 2, -1299, "FOOBAR")),
    )
    assert counts(pull) == (0, 1, 0, 1)
    assert pull.feed_total_cents == -1774
    assert ledger(session) == [
        (1, "a", 4, -475, "ACME COFFEE #12", False),
        (2, "b", 2, -1299, "FOOBAR", False),
    ]
    assert session.get(TransactionRow, 1).card_last4 == "9999"


@pytest.mark.parametrize(
    "changed",
    [
        tx("a", 2, -450, "ACME COFFEE", transaction_date=MAY, card_last4="1111"),
        tx("a", 1, -451, "ACME COFFEE", transaction_date=MAY, card_last4="1111"),
        tx("a", 1, -450, "ACME COFFEE 2", transaction_date=MAY, card_last4="1111"),
        tx("a", 1, -450, "ACME COFFEE", transaction_date=day(2), card_last4="1111"),
        tx("a", 1, -450, "ACME COFFEE", card_last4="1111"),
        tx("a", 1, -450, "ACME COFFEE", transaction_date=MAY, card_last4="2222"),
        tx("a", 1, -450, "ACME COFFEE", transaction_date=MAY),
        tx("a", 1, -450, "ACME COFFEE", transaction_date=MAY, card_last4="1111", is_pending=True),
    ],
)
def test_a_change_to_any_one_field_is_an_update(session: Session, changed: FeedTransaction) -> None:
    apply_feed(
        session, 1, feed(tx("a", 1, -450, "ACME COFFEE", transaction_date=MAY, card_last4="1111"))
    )
    assert counts(apply_feed(session, 1, feed(changed))) == (0, 1, 0, 0)
    row = session.get(TransactionRow, 1)
    assert (
        row.posted_date,
        row.amount_cents,
        row.description,
        row.transaction_date,
        row.card_last4,
        row.is_pending,
    ) == (
        changed.posted_date,
        changed.amount_cents,
        changed.description,
        changed.transaction_date,
        changed.card_last4,
        changed.is_pending,
    )


def test_a_pending_row_that_posts_under_the_same_id(session: Session) -> None:
    apply_feed(session, 1, feed(tx("a", 1, -700, "ACME GAS", is_pending=True)))
    pull = apply_feed(session, 1, feed(tx("a", 2, -712, "ACME GAS #4")))
    assert counts(pull) == (0, 1, 0, 0)
    assert pull.feed_total_cents == -712
    assert ledger(session) == [(1, "a", 2, -712, "ACME GAS #4", False)]


def test_a_posted_row_replaces_its_pending_row_and_keeps_the_stored_id(session: Session) -> None:
    apply_feed(
        session,
        1,
        feed(tx("keep", 1, -100, "ACME"), tx("pend-1", 1, -700, "ACME GAS", is_pending=True)),
    )
    pull = apply_feed(
        session,
        1,
        feed(tx("post-1", 3, -712, "ACME GAS #4", replaces_feed_id="pend-1"), removed=("pend-1",)),
    )
    assert counts(pull) == (0, 1, 0, 0)
    assert ledger(session) == [
        (1, "keep", 1, -100, "ACME", False),
        (2, "post-1", 3, -712, "ACME GAS #4", False),
    ]
    assert session.get(TransactionRow, 2).fingerprint == feed_fingerprint(1, "post-1")
    assert session.scalars(select(FeedItemRow.feed_id).order_by(FeedItemRow.id)).all() == [
        "keep",
        "post-1",
    ]
    again = apply_feed(
        session, 1, feed(tx("post-1", 3, -712, "ACME GAS #4", replaces_feed_id="pend-1"))
    )
    assert counts(again) == (0, 0, 0, 1)


def test_a_replacement_whose_pending_row_is_unknown_is_inserted(session: Session) -> None:
    pull = apply_feed(session, 1, feed(tx("post-1", 3, -712, "ACME", replaces_feed_id="gone")))
    assert counts(pull) == (1, 0, 0, 0)
    assert ledger(session) == [(1, "post-1", 3, -712, "ACME", False)]


def test_removed_rows_are_deleted_and_unknown_ids_are_ignored(session: Session) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("a", 1, -450, "ACME COFFEE"),
            tx("b", 2, -700, "ACME GAS", is_pending=True),
            tx("c", 3, -900, "FOOBAR"),
        ),
    )
    pull = apply_feed(session, 1, feed(removed=("b", "c", "never-seen", "b")))
    assert counts(pull) == (0, 0, 2, 0)
    assert pull.feed_total_cents == -450
    assert ledger(session) == [(1, "a", 1, -450, "ACME COFFEE", False)]
    assert session.scalars(select(FeedItemRow.feed_id)).all() == ["a"]


def test_a_row_confirmed_by_a_statement_is_never_changed_or_deleted(session: Session) -> None:
    apply_feed(session, 1, feed(tx("a", 1, -450, "ACME COFFEE"), tx("b", 2, -900, "FOOBAR")))
    audit(session, 1)
    audit(session, 2)
    pull = apply_feed(session, 1, feed(tx("a", 9, -999, "CHANGED BY THE FEED"), removed=("b",)))
    assert counts(pull) == (0, 0, 0, 1)
    assert pull.feed_total_cents == -1350
    assert ledger(session) == [
        (1, "a", 1, -450, "ACME COFFEE", False),
        (2, "b", 2, -900, "FOOBAR", False),
    ]


def test_a_replacement_does_not_touch_a_row_confirmed_by_a_statement(session: Session) -> None:
    apply_feed(session, 1, feed(tx("old", 1, -450, "ACME COFFEE")))
    audit(session, 1)
    pull = apply_feed(session, 1, feed(tx("new", 2, -460, "ACME COFFEE", replaces_feed_id="old")))
    assert counts(pull) == (1, 0, 0, 0)
    assert ledger(session) == [
        (1, "old", 1, -450, "ACME COFFEE", False),
        (2, "new", 2, -460, "ACME COFFEE", False),
    ]


def test_accounts_do_not_share_feed_ids(session: Session) -> None:
    apply_feed(session, 1, feed(tx("same", 1, -450, "ACME COFFEE")))
    pull = apply_feed(session, 2, feed(tx("same", 1, 2500, "PAYROLL"), balance=2500, on=day(1)))
    assert counts(pull) == (1, 0, 0, 0)
    assert (pull.account_id, pull.feed_total_cents) == (2, 2500)
    assert ledger(session, 1) == [(1, "same", 1, -450, "ACME COFFEE", False)]
    assert ledger(session, 2) == [(2, "same", 1, 2500, "PAYROLL", False)]
    apply_feed(session, 2, feed(removed=("same",)))
    assert ledger(session, 1) == [(1, "same", 1, -450, "ACME COFFEE", False)]
    assert ledger(session, 2) == []


def test_statement_rows_are_not_part_of_the_feed(session: Session) -> None:
    insert_transactions(
        session,
        [
            NewTransaction(
                account_id=1,
                statement_id=None,
                posted_date=day(1),
                transaction_date=None,
                amount_cents=-5000,
                description="ACME COFFEE",
                section="purchases",
                card_last4=None,
                cardholder=None,
                external_id="a",
                source=DataSource.STATEMENT,
                is_pending=False,
                fingerprint="f" * 64,
            )
        ],
    )
    pull = apply_feed(session, 1, feed(tx("a", 1, -450, "ACME COFFEE"), removed=("f" * 64,)))
    assert counts(pull) == (1, 0, 0, 0)
    assert pull.feed_total_cents == -450
    assert ledger(session) == [
        (1, None, 1, -5000, "ACME COFFEE", False),
        (2, "a", 1, -450, "ACME COFFEE", False),
    ]


def test_a_balance_is_stored_as_an_aggregator_snapshot(session: Session) -> None:
    pull = apply_feed(session, 1, feed(tx("a", 1, -450, "ACME"), balance=-10450, on=day(2)))
    assert (pull.balance_cents, pull.balance_date, pull.drift_cents) == (-10450, day(2), None)
    snapshot = latest_balance(session, 1)
    assert (snapshot.as_of_date, snapshot.balance_cents, snapshot.source) == (
        day(2),
        -10450,
        DataSource.AGGREGATOR,
    )


def test_a_second_balance_on_the_same_day_replaces_the_first(session: Session) -> None:
    apply_feed(session, 1, feed(balance=-10000, on=day(2)))
    apply_feed(session, 1, feed(tx("a", 2, -450, "ACME"), balance=-10450, on=day(2)))
    rows = session.scalars(select(BalanceSnapshotRow)).all()
    assert [(row.as_of_date, row.balance_cents, row.source) for row in rows] == [
        (day(2), -10450, "aggregator")
    ]


def test_drift_is_zero_when_the_balance_moves_with_the_posted_rows(session: Session) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("a", 1, -450, "ACME"),
            tx("p", 1, -700, "GAS", is_pending=True),
            balance=-10450,
            on=day(1),
        ),
    )
    pull = apply_feed(
        session,
        1,
        feed(
            tx("b", 2, -1299, "FOOBAR"),
            tx("c", 2, 5000, "PAYMENT"),
            tx("q", 2, -300, "SNACK", is_pending=True),
            balance=-6749,
            on=day(2),
        ),
    )
    assert (pull.feed_total_cents, pull.drift_cents) == (3251, 0)
    pull = apply_feed(
        session,
        1,
        feed(
            tx("p2", 3, -712, "GAS #4", replaces_feed_id="p"),
            removed=("p", "q"),
            balance=-7461,
            on=day(3),
        ),
    )
    assert counts(pull) == (0, 1, 1, 0)
    assert (pull.feed_total_cents, pull.drift_cents) == (2539, 0)


def test_drift_is_what_the_balance_moved_beyond_the_posted_rows(session: Session) -> None:
    apply_feed(session, 1, feed(tx("a", 1, -450, "ACME"), balance=-10450, on=day(1)))
    pull = apply_feed(session, 1, feed(tx("b", 2, -1299, "FOOBAR"), balance=-11800, on=day(2)))
    assert pull.drift_cents == -51
    pull = apply_feed(session, 1, feed(tx("c", 3, -100, "ACME"), balance=-11849, on=day(3)))
    assert pull.drift_cents == 51
    pull = apply_feed(session, 1, feed(balance=-11849, on=day(4)))
    assert pull.drift_cents == 0


def test_drift_looks_back_to_the_last_pull_that_had_a_balance(session: Session) -> None:
    apply_feed(session, 1, feed(tx("a", 1, -450, "ACME"), balance=-10450, on=day(1)))
    middle = apply_feed(session, 1, feed(tx("b", 2, -1299, "FOOBAR")))
    assert (middle.balance_cents, middle.drift_cents, middle.feed_total_cents) == (
        None,
        None,
        -1749,
    )
    pull = apply_feed(session, 1, feed(tx("c", 3, -1, "ACME"), balance=-11750, on=day(3)))
    assert pull.drift_cents == 0
    stored = session.scalars(select(FeedPullRow).order_by(FeedPullRow.id)).all()
    assert [(row.balance_cents, row.drift_cents) for row in stored] == [
        (-10450, None),
        (None, None),
        (-11750, 0),
    ]


def test_drift_is_kept_per_account(session: Session) -> None:
    apply_feed(session, 1, feed(tx("a", 1, -450, "ACME"), balance=-10450, on=day(1)))
    first = apply_feed(session, 2, feed(tx("a", 1, 2500, "PAYROLL"), balance=90000, on=day(1)))
    assert first.drift_cents is None
    second = apply_feed(session, 2, feed(tx("b", 2, -2000, "RENT"), balance=88000, on=day(2)))
    assert second.drift_cents == 0


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (feed(tx("", 1, -1, "ACME")), "feed has an unusable transaction id"),
        (feed(tx(" a", 1, -1, "ACME")), "feed has an unusable transaction id"),
        (feed(tx("x" * 101, 1, -1, "ACME")), "feed has an unusable transaction id"),
        (
            feed(tx("b", 1, -1, "ACME", replaces_feed_id="")),
            "feed has an unusable transaction id",
        ),
        (feed(removed=("a ",)), "feed has an unusable transaction id"),
        (feed(tx("b", 1, -1, " \t ")), "feed has an empty description"),
        (feed(tx("b", 1, -1, "ACME", card_last4="12a4")), "feed has unusable card digits"),
        (
            feed(tx("b", 1, -1, "ACME"), tx("b", 2, -2, "FOOBAR")),
            "feed has a duplicate transaction id",
        ),
        (
            feed(tx("b", 1, -1, "ACME"), removed=("b",)),
            "feed removes a transaction it also delivers",
        ),
        (feed(balance=-100), "feed balance and its date must come together"),
        (feed(on=day(1)), "feed balance and its date must come together"),
    ],
)
def test_a_feed_that_cannot_be_applied_writes_nothing(
    session: Session, bad: AccountFeed, message: str
) -> None:
    apply_feed(session, 1, feed(tx("a", 1, -450, "ACME COFFEE")))
    before = ledger(session)
    whole = AccountFeed(
        [tx("good", 5, -5, "GOOD ROW"), *bad.transactions],
        ["a", *bad.removed_feed_ids],
        bad.balance_cents,
        bad.balance_date,
    )
    with pytest.raises(FeedError) as caught:
        apply_feed(session, 1, whole)
    assert str(caught.value) == message
    assert ledger(session) == before
    assert len(session.scalars(select(FeedPullRow)).all()) == 1
    assert session.scalars(select(BalanceSnapshotRow)).all() == []


def test_an_unknown_account(session: Session) -> None:
    with pytest.raises(FeedError) as caught:
        apply_feed(session, 99, feed(tx("a", 1, -450, "ACME COFFEE")))
    assert str(caught.value) == "account not found"
    assert session.scalars(select(TransactionRow)).all() == []


def test_a_long_id_and_a_long_description(session: Session) -> None:
    apply_feed(session, 1, feed(tx("x" * 100, 1, -1, "A" * 499 + " " + "B" * 10)))
    row = session.get(TransactionRow, 1)
    assert row.description == "A" * 499
    assert session.scalars(select(FeedItemRow.feed_id)).one() == "x" * 100
    assert counts(
        apply_feed(session, 1, feed(tx("x" * 100, 1, -1, "A" * 499 + " " + "B" * 10)))
    ) == (
        0,
        0,
        0,
        1,
    )
```

## Tests to write

`tests/unit/test_feed_models.py`, without a database:

- R4 and R5: field names in order, types, defaults, frozen, and that two `AccountFeed()` values do not share lists
- R3: `to_feed_pull` for a row built in memory, with a `pulled_at` that has a time zone and one that has none
- R2: `FeedItemRow` and `FeedPullRow` table names, column names in order, and that `pulled_at` has a default

`tests/integration/test_feed_repositories.py`, on the `db_engine` fixture, one function at a time:

- R7: found and not found
- R8: a new snapshot; a second call for the same account, date, and source keeps the id and replaces the balance; another source and another date make new rows; a balance beyond 32 bits
- R9: an empty iterable; ids of another account are not returned; more than 1,000 ids in one call
- R10: the returned `Transaction` has every field of the `NewTransaction`; the same feed id twice in one account raises `IntegrityError`
- R11: every one of the eight values changes and nothing else does; the `ValueError` for an unknown id and for a transaction that has no feed id, with its exact message
- R12: `True` and both rows gone; `False` and nothing deleted for a statement row; `False` for an unknown id
- R13: zero for an account with nothing; pending rows and rows without a feed id are left out; a row whose `source` was changed to `statement` is still counted; another account's rows are not
- R14 and R15: the stored values, `pulled_at` with a time zone, the highest id wins, `with_balance=True` skips pulls without one, and `None` for an account with no pull
- that a later session sees what an earlier session wrote, for one function of each kind

Every line and branch of `finances.sync`, `finances.db`, and `finances.domain` must be reached by a test.

## Rules for this phase

- **Money is `int` cents.** `float` does not appear in `src/finances/sync/` or in the new repository functions. `feed_posted_total` returns an `int` even when the database returns another numeric type.
- **Signs are from the account holder's side** (`AGENTS.md`). This phase never changes a sign.
- **No network.** Nothing in this phase imports a network library. `src/finances/sync/` is where network code will live, which is a reason to keep it out until 17b, not a licence to add it.
- **Constant messages.** The seven messages in R16 and the one in R11 are the only ones this phase creates. Nothing from a feed (an id, a description, an amount) goes into an exception, and nothing is logged or printed.
- **Database access** is SQLAlchemy 2.0 style, in `src/finances/db/` only. `sync/service.py` calls repository functions and never touches an ORM class or writes a query. No dialect-specific SQL.
- **The shipped migrations `0001` and `0002` are not edited.**
- **Synthetic data only** in tests.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, at least N + 61 passed, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/integration/test_migration_0003.py tests/integration/test_feed_service.py --no-cov` | exactly `61 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| each of the three searches below | no output |
| `git diff HEAD --stat -- src/finances/db/migrations/versions/0001_accounts.py src/finances/db/migrations/versions/0002_statements.py src/finances/ingest src/finances/cli tests/conftest.py` | no output |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.sync --cov=finances.db --cov=finances.domain --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -E "float|(^|[^_a-zA-Z.])print\(|logging" -- src/finances/sync`

`git grep -n --untracked -E "^ *(import|from) +(requests|httpx|urllib|socket|http|aiohttp|ssl|ftplib|smtplib)" -- src/finances/sync`

`git grep -n --untracked -E "finances\.(ingest|cli)" -- src/finances/sync src/finances/db src/finances/domain`

Then check by hand that `git diff HEAD -- src/finances/domain/models.py src/finances/db/orm.py src/finances/db/repositories.py` only adds lines, apart from import lines that gained a name.

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 17a: the feed core (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. Under "Deviations", list your design choices (private helpers, constants, how the stored rows are looked up) and anything you did that the spec did not ask for, or `None`.

In your final message, give the output line of each acceptance command, and for each of R1 to R23 the name of a test that covers it.
