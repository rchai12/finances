# Phase 3c: storing and importing statements

## Goal

Take a statement from PDF bytes to rows in the database. After this phase one function call reads a statement, recognizes it, checks that it adds up, matches it to an account, and stores what is new, and a second call with the same file changes nothing.

Five parts, each built on the one before:

1. **Domain types** for a stored statement, a transaction, and a balance snapshot.
2. **ORM tables** for the three, and the converters to the domain types.
3. **Migration `0002`** that creates the three tables.
4. **Repositories** to save and query them.
5. **The import service**: `import_statement` and `import_folder`.

There are no commands yet (Phase 3d adds `fin import` and the list commands) and no real bank parser (Phase 4). The tests use a made-up bank format whose parser is given in `tests/conftest.py`.

This phase joins what was planned as two sub-phases, because the service is the only user of the new repositories and each shows whether the other is right.

## Read first

- `AGENTS.md`: "Running commands", "Privacy rules", "Money and signs", "Architecture rules"
- `docs/architecture.md`: "Data model" and "Statement parsing design"
- `docs/testing.md`
- `src/finances/domain/models.py`, `src/finances/db/orm.py`, `src/finances/db/repositories.py`, `src/finances/db/engine.py`
- `src/finances/db/migrations/versions/0001_accounts.py` and `src/finances/db/migrations/env.py`
- `src/finances/ingest/`: `statement.py`, `reconcile.py`, `dedup.py`, `pdf_text.py`, `parsers/__init__.py`, `parsers/helpers.py`
- `tests/conftest.py`

## Starting state

- Phase 3b is committed. `git status --short` prints nothing.
- `.venv/bin/python -m pytest` ends with `516 passed`.
- The database has one table, `accounts`, created by migration `0001`. `head_revision()` returns `"0001"`.
- The existing tests no longer assume that `0001` is the newest migration. They ask `head_revision()` for it, or upgrade to a named revision. Adding `0002` must not require changing any of them.
- `finances.ingest`, `finances.db`, and `finances.domain` are at 100% line and branch coverage.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/models.py` | adds `DataSource`, `Statement`, `NewTransaction`, `Transaction`, `BalanceSnapshot` |
| `src/finances/db/orm.py` | adds `StatementRow`, `TransactionRow`, `BalanceSnapshotRow`, `to_statement`, `to_transaction`, `to_balance_snapshot` |
| `src/finances/db/migrations/versions/0002_statements.py` | new |
| `src/finances/db/repositories.py` | adds eight functions |
| `src/finances/ingest/service.py` | new: `ImportStatus`, `StatementImportResult`, `import_statement`, `import_folder` |
| `tests/conftest.py` | replaced with the given file |
| `tests/integration/test_migration_0002.py` | given, do not change |
| `tests/unit/test_statement_models.py`, `tests/unit/test_statement_orm.py`, `tests/integration/test_statement_repositories.py`, `tests/integration/test_import_service.py` | new, written by you |
| `docs/progress.md` | one new entry |

You may add private helpers (names starting with `_`) inside the listed source modules. Do not create any other production module, do not change any production file that is not in this table, and do not change any existing test file other than `tests/conftest.py`.

## Out of scope

- Commands: no `fin import`, `fin statements`, or `fin transactions`. Nothing under `src/finances/cli/` changes.
- A real bank parser, or any parser registered by production code.
- An override that imports a statement which does not reconcile. A statement that does not add up is never stored.
- Aggregator code. `DataSource.AGGREGATOR` and `is_pending` exist so that Phase 17 needs no schema change; nothing in this phase writes them except tests.
- Updating or deleting stored rows, and any "re-import" or "replace" mode.
- Categories, merchants, or any normalizing of descriptions beyond collapsing whitespace.
- Editing migration `0001`, `env.py`, or anything in `src/finances/ingest/` other than adding `service.py`.
- New dependencies.

## Dependencies

None new.

## Design

### `src/finances/domain/models.py`

`domain` imports nothing from this project, so `section` is plain text here and `Section` stays in `finances.ingest`.

```python
class DataSource(StrEnum):
    STATEMENT = "statement"
    AGGREGATOR = "aggregator"
```

Three frozen dataclasses for stored rows and one for a row about to be stored. Fields are in this order, and none has a default.

| `Statement` | Type |
|---|---|
| `id` | `int` |
| `account_id` | `int` |
| `source_filename` | `str` |
| `file_sha256` | `str` |
| `parser_name` | `str` |
| `period_start` | `date` |
| `period_end` | `date` |
| `opening_balance_cents` | `int` |
| `closing_balance_cents` | `int` |
| `lines_parsed` | `int` |
| `rows_inserted` | `int` |
| `rows_duplicate` | `int` |
| `imported_at` | `datetime` |

| `NewTransaction` | Type |
|---|---|
| `account_id` | `int` |
| `statement_id` | `int \| None` |
| `posted_date` | `date` |
| `transaction_date` | `date \| None` |
| `amount_cents` | `int` |
| `description` | `str` |
| `section` | `str \| None` |
| `card_last4` | `str \| None` |
| `cardholder` | `str \| None` |
| `external_id` | `str \| None` |
| `source` | `DataSource` |
| `is_pending` | `bool` |
| `fingerprint` | `str` |

`Transaction` has `id: int` first, then the thirteen fields of `NewTransaction` in the same order, then `created_at: datetime`.

| `BalanceSnapshot` | Type |
|---|---|
| `id` | `int` |
| `account_id` | `int` |
| `as_of_date` | `date` |
| `balance_cents` | `int` |
| `source` | `DataSource` |
| `created_at` | `datetime` |

### `src/finances/db/orm.py`

Three classes on the existing `Base`, in the style of `AccountRow`. "Null" says whether the column allows null.

**`StatementRow`**, table `statements`: one row per imported statement file.

| Column | Column type | Null | Other |
|---|---|---|---|
| `id` | `Integer` | no | primary key |
| `account_id` | `Integer` | no | foreign key to `accounts.id` |
| `source_filename` | `String(255)` | no | |
| `file_sha256` | `String(64)` | no | unique |
| `parser_name` | `String(50)` | no | |
| `period_start` | `Date` | no | |
| `period_end` | `Date` | no | |
| `opening_balance_cents` | `BigInteger` | no | |
| `closing_balance_cents` | `BigInteger` | no | |
| `lines_parsed` | `Integer` | no | |
| `rows_inserted` | `Integer` | no | |
| `rows_duplicate` | `Integer` | no | |
| `imported_at` | `DateTime(timezone=True)` | no | Python default: the current time in UTC |

**`TransactionRow`**, table `transactions`.

| Column | Column type | Null | Other |
|---|---|---|---|
| `id` | `Integer` | no | primary key |
| `account_id` | `Integer` | no | foreign key to `accounts.id`; indexed |
| `statement_id` | `Integer` | yes | foreign key to `statements.id` |
| `posted_date` | `Date` | no | indexed |
| `transaction_date` | `Date` | yes | |
| `amount_cents` | `BigInteger` | no | |
| `description` | `String(500)` | no | |
| `section` | `String(30)` | yes | |
| `card_last4` | `String(4)` | yes | |
| `cardholder` | `String(100)` | yes | |
| `external_id` | `String(100)` | yes | |
| `source` | `String(20)` | no | a `DataSource` value, stored as text |
| `is_pending` | `Boolean` | no | Python default `False` |
| `fingerprint` | `String(64)` | no | |
| `created_at` | `DateTime(timezone=True)` | no | Python default: the current time in UTC |

**`BalanceSnapshotRow`**, table `balance_snapshots`.

| Column | Column type | Null | Other |
|---|---|---|---|
| `id` | `Integer` | no | primary key |
| `account_id` | `Integer` | no | foreign key to `accounts.id` |
| `as_of_date` | `Date` | no | |
| `balance_cents` | `BigInteger` | no | |
| `source` | `String(20)` | no | a `DataSource` value, stored as text |
| `created_at` | `DateTime(timezone=True)` | no | Python default: the current time in UTC |

Names in the database:

| Kind | Names |
|---|---|
| Primary keys | `pk_statements`, `pk_transactions`, `pk_balance_snapshots` |
| Foreign keys | `fk_statements_account_id_accounts`, `fk_transactions_account_id_accounts`, `fk_transactions_statement_id_statements`, `fk_balance_snapshots_account_id_accounts` |
| Unique constraints | `uq_statements_file_sha256` on `file_sha256`; `uq_transactions_account_fingerprint` on `(account_id, fingerprint)`; `uq_balance_snapshots_account_date_source` on `(account_id, as_of_date, source)` |
| Indexes | `ix_transactions_account_id`, `ix_transactions_posted_date`; neither is unique |

`Base` already carries a naming convention that produces the primary key names, the foreign key names, `uq_statements_file_sha256`, and the two index names. The two multi-column unique constraints need their names given, because the convention would name them after their first column only.

```python
def to_statement(row: StatementRow) -> Statement
def to_transaction(row: TransactionRow) -> Transaction
def to_balance_snapshot(row: BalanceSnapshotRow) -> BalanceSnapshot
```

### `src/finances/db/repositories.py`

```python
def create_statement(
    session: Session,
    *,
    account_id: int,
    source_filename: str,
    file_sha256: str,
    parser_name: str,
    period_start: date,
    period_end: date,
    opening_balance_cents: int,
    closing_balance_cents: int,
    lines_parsed: int,
    rows_inserted: int,
    rows_duplicate: int,
) -> Statement
def find_statement_by_hash(session: Session, file_sha256: str) -> Statement | None
def list_statements(session: Session, account_id: int | None = None) -> list[Statement]
def existing_fingerprints(session: Session, account_id: int, fingerprints: Iterable[str]) -> set[str]
def insert_transactions(session: Session, rows: list[NewTransaction]) -> int
def list_transactions(
    session: Session,
    account_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = 100,
) -> list[Transaction]
def add_balance_snapshot(
    session: Session, account_id: int, as_of_date: date, balance_cents: int, source: DataSource
) -> BalanceSnapshot
def latest_balance(session: Session, account_id: int) -> BalanceSnapshot | None
```

### `src/finances/ingest/service.py`

```python
class ImportStatus(StrEnum):
    IMPORTED = "imported"
    DRY_RUN = "dry_run"
    ALREADY_IMPORTED = "already_imported"
    FAILED = "failed"


@dataclass(frozen=True)
class StatementImportResult:
    filename: str
    status: ImportStatus
    message: str
    parser_name: str | None = None
    account_name: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    lines_parsed: int = 0
    inserted: int = 0
    duplicates: int = 0


def import_statement(
    session: Session,
    *,
    filename: str,
    content: bytes,
    account_name: str | None = None,
    dry_run: bool = False,
) -> StatementImportResult
def import_folder(engine: Engine, folder: Path, *, dry_run: bool = False) -> list[StatementImportResult]
```

A result holds names, dates, and counts. It never holds a description or an amount.

## Requirements

### Part 1: domain types

- **R1.** `DataSource` is a `StrEnum` with the two members shown, in that order.
- **R2.** `Statement`, `NewTransaction`, `Transaction`, and `BalanceSnapshot` are frozen dataclasses with exactly the fields in the Design tables, in that order, with those types and no defaults.
- **R3.** `domain/models.py` still imports only from the standard library.

### Part 2: ORM tables and converters

- **R4.** The three classes define exactly the columns, types, null settings, keys, constraints, indexes, and names in the Design tables. Amounts are `BigInteger`. `source` and `section` are plain `String` columns, not SQLAlchemy `Enum`.
- **R5.** The Python defaults are `False` for `is_pending` and a function returning `datetime.now(UTC)` for the three timestamps. No column has a `server_default`.
- **R6.** Each converter returns the domain dataclass with every field copied from the row. `source` becomes a `DataSource` member, so an unknown value raises `ValueError`.
- **R7.** SQLite returns timestamps without a time zone. A converter treats such a value as UTC (`replace(tzinfo=UTC)`) and leaves a value that already has a time zone unchanged, as `to_account` does.

### Part 3: migration `0002`

- **R8.** `0002_statements.py` has `revision = "0002"` and `down_revision = "0001"`. Its `upgrade` creates the three tables so that a database at `0002` matches the ORM classes exactly: `test_fully_migrated_database_matches_the_orm` in the existing `test_migrations.py` must pass, and so must the given `test_migration_0002.py`, which checks every column, key, constraint, index, and name.
- **R9.** `downgrade` removes the three tables and their indexes and nothing else. The `accounts` table and its rows are untouched in both directions.
- **R10.** The migration imports only `sqlalchemy` and `alembic`, has no `server_default`, and declares each timestamp as `sa.DateTime(timezone=True)`. Migration `0001` is not edited.

### Part 4: repositories

No repository function commits, rolls back, or closes the session. Each one that writes calls `session.flush()` so that ids are assigned and constraints are checked before it returns. The caller's `session_scope` commits.

- **R11.** `create_statement` adds one `statements` row from its arguments and returns it as a `Statement` with its new `id` and `imported_at`.
- **R12.** `find_statement_by_hash` returns the statement whose `file_sha256` equals the argument, or `None`.
- **R13.** `list_statements` returns statements ordered by `period_end`, latest first, and by `id`, highest first, where the period ends are equal. With `account_id` it returns only that account's.
- **R14.** `existing_fingerprints` returns the subset of the given fingerprints that already belong to a transaction **of that account**, as a `set`. It accepts any iterable, including a generator and an empty one. It may be asked about more fingerprints than a database accepts in one query, so no single query carries more than 500 of them.
- **R15.** `insert_transactions` adds one `transactions` row per `NewTransaction`, copying every field, with `source` stored as its text value, and returns how many it added. An empty list adds nothing and returns `0`.
- **R16.** `list_transactions` returns transactions ordered by `posted_date`, latest first, and by `id`, highest first, where the dates are equal, cut off after `limit` rows. `account_id` restricts it to one account. `start` and `end` restrict `posted_date` and are both inclusive; either can be given alone.
- **R17.** `list_transactions` with `limit` below `1` raises `ValueError("limit must be at least 1")`.
- **R18.** `add_balance_snapshot` adds a row and returns it. When a snapshot already exists for the same account, date, and source, it adds nothing, changes nothing, and returns the existing one: the first balance recorded for a day is kept.
- **R19.** `latest_balance` returns the account's snapshot with the latest `as_of_date`, the one with the highest `id` when several share that date, or `None` when the account has none.

### Part 5: the import service

`import_statement` goes through these stages in order and stops at the first that ends the import. It never raises for a statement it cannot use: it returns a result with status `FAILED`. It never commits.

Every result carries `filename`, which is the final path component of the `filename` argument (`Path(filename).name`): a caller may pass a full path, and only the file's own name is kept or stored.

- **R20. Already imported.** Compute the SHA-256 hex digest of `content`. If a statement with that hash is stored, return status `ALREADY_IMPORTED` with message `already imported`. This comes before anything is read or parsed, applies in a dry run too, and leaves the other result fields at their defaults.
- **R21. Read and parse.** Call `extract_pages(content)`, `detect_parser(pages)`, and the parser's `parse(pages)`. A `StatementError` from any of the three gives status `FAILED` with the error's own message, and the other result fields at their defaults. Those messages are constant texts by the rules of earlier phases, so they are safe to pass on.
- From here on, every result also carries `parser_name`, `period_start`, `period_end`, and `lines_parsed` (the number of lines the parser returned), whatever its status.
- **R22. Named account.** When `account_name` is given, look it up with `get_account_by_name`. No such account gives `FAILED` with message `account not found`. An account whose `last4` is set and differs from the statement's `account_last4` gives `FAILED` with message `account does not match the statement`. An account with no `last4` accepts any statement.
- **R23. Matched account.** When `account_name` is not given, call `find_accounts_by_last4` with the statement's `account_last4`. Exactly one account: use it. None: `FAILED` with a message that tells the user the command to run, built from the statement's `account_last4`, `institution`, and `account_type`. For the default fake statement it is exactly:

  `no account ends in 1111; add one with: fin accounts add --name "NAME" --institution "Fake Bank" --type credit_card --last4 1111`

  More than one: `FAILED` with message `more than one account ends in these digits; name the account`. If `find_accounts_by_last4` raises `ValueError` because the statement's digits are not four digits: `FAILED` with message `statement has no usable account digits`.
- Once an account is chosen, every result also carries `account_name`, the account's stored name.
- **R24. Reconcile.** Call `reconcile`. When it is not `ok`, the status is `FAILED` and the message is `statement does not reconcile: off by N cents`, where `N` is `difference_cents` as a signed decimal (`3`, `-3`, `0`). When `section_mismatches` is not empty, the message continues with `; section totals differ: ` and the mismatched sections' values in the order `reconcile` reported them, joined by `, `. Example: `statement does not reconcile: off by 0 cents; section totals differ: fees, interest`. The message gives the size of the difference and section names only, never a balance or a line.
- **R25. Find what is new.** Compute `fingerprint_lines(account.id, lines)` and ask `existing_fingerprints` which the account already has. `duplicates` is the number of lines whose fingerprint exists, and `inserted` is the number of the rest.
- **R26. Dry run.** With `dry_run=True`, return status `DRY_RUN` with message `dry run: nothing written` and the counts from R25. Nothing has been written at this point or before it.
- **R27. Store.** Otherwise write, in this session:
  1. one statement record (`create_statement`) with the account, the file name from the rule above, the hash, the parser name, the period, both balances, and the three counts;
  2. one transaction per new line (`insert_transactions`), in the statement's order, with `statement_id` set to that record, `description` passed through `collapse_ws`, `section` as the section's text value, `external_id` from the line's `external_ref`, `source` `DataSource.STATEMENT`, `is_pending` `False`, the line's fingerprint, and the remaining fields copied;
  3. one balance snapshot (`add_balance_snapshot`) for the account at `period_end` with the closing balance and source `DataSource.STATEMENT`.

  Return status `IMPORTED` with message `imported` and the counts from R25. A statement whose lines are all duplicates is still recorded, with `rows_inserted` `0`.
- **R28. Nothing partial.** A `FAILED`, `ALREADY_IMPORTED`, or `DRY_RUN` result means no row was added to any table.

`import_folder`:

- **R29.** It imports every file directly inside `folder` whose name ends in `.pdf` in any letter case. Files in subfolders, and files with other endings, are ignored.
- **R30.** Files are handled in order of file name (plain string order), and the results are returned in that order.
- **R31.** Each file is read and passed to `import_statement` inside its own `session_scope(engine)`, with `dry_run` passed through and no `account_name`. A file that ends as `FAILED` does not stop the files after it, and the files before it stay committed.
- **R32.** An empty folder gives an empty list.

## Given tests

Create this file exactly as shown and do not change it. It checks migration `0002` against the Design tables. If one of its tests fails, the migration or the ORM class is wrong.

`tests/integration/test_migration_0002.py`:

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
from finances.db.orm import AccountRow, BalanceSnapshotRow, StatementRow, TransactionRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0002_statements.py"
COLUMNS = {
    "statements": [
        ("id", "INTEGER", False),
        ("account_id", "INTEGER", False),
        ("source_filename", "VARCHAR(255)", False),
        ("file_sha256", "VARCHAR(64)", False),
        ("parser_name", "VARCHAR(50)", False),
        ("period_start", "DATE", False),
        ("period_end", "DATE", False),
        ("opening_balance_cents", "BIGINT", False),
        ("closing_balance_cents", "BIGINT", False),
        ("lines_parsed", "INTEGER", False),
        ("rows_inserted", "INTEGER", False),
        ("rows_duplicate", "INTEGER", False),
        ("imported_at", "DATETIME", False),
    ],
    "transactions": [
        ("id", "INTEGER", False),
        ("account_id", "INTEGER", False),
        ("statement_id", "INTEGER", True),
        ("posted_date", "DATE", False),
        ("transaction_date", "DATE", True),
        ("amount_cents", "BIGINT", False),
        ("description", "VARCHAR(500)", False),
        ("section", "VARCHAR(30)", True),
        ("card_last4", "VARCHAR(4)", True),
        ("cardholder", "VARCHAR(100)", True),
        ("external_id", "VARCHAR(100)", True),
        ("source", "VARCHAR(20)", False),
        ("is_pending", "BOOLEAN", False),
        ("fingerprint", "VARCHAR(64)", False),
        ("created_at", "DATETIME", False),
    ],
    "balance_snapshots": [
        ("id", "INTEGER", False),
        ("account_id", "INTEGER", False),
        ("as_of_date", "DATE", False),
        ("balance_cents", "BIGINT", False),
        ("source", "VARCHAR(20)", False),
        ("created_at", "DATETIME", False),
    ],
}
UNIQUES = {
    "statements": [("uq_statements_file_sha256", ["file_sha256"])],
    "transactions": [("uq_transactions_account_fingerprint", ["account_id", "fingerprint"])],
    "balance_snapshots": [
        ("uq_balance_snapshots_account_date_source", ["account_id", "as_of_date", "source"])
    ],
}
FOREIGN_KEYS = {
    "statements": [("fk_statements_account_id_accounts", ["account_id"], "accounts")],
    "transactions": [
        ("fk_transactions_account_id_accounts", ["account_id"], "accounts"),
        ("fk_transactions_statement_id_statements", ["statement_id"], "statements"),
    ],
    "balance_snapshots": [("fk_balance_snapshots_account_id_accounts", ["account_id"], "accounts")],
}
INDEXES = {
    "statements": [],
    "transactions": [
        ("ix_transactions_account_id", ["account_id"]),
        ("ix_transactions_posted_date", ["posted_date"]),
    ],
    "balance_snapshots": [],
}
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
        source="statement",
        fingerprint=fingerprint,
    )


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def at_0002(url: str) -> str:
    """A database upgraded to revision 0002 only, whatever later migrations exist."""
    command.upgrade(make_config(url), "0002")
    return url


@pytest.fixture
def with_accounts(at_0002: str) -> str:
    engine = get_engine(at_0002)
    with session_scope(engine) as session:
        session.add(AccountRow(name="Test Card", institution="Test Bank", type="credit_card"))
        session.add(AccountRow(name="Test Checking", institution="Test Bank", type="checking"))
    engine.dispose()
    return at_0002


def test_0002_follows_0001(url: str) -> None:
    scripts = ScriptDirectory.from_config(make_config(url))
    assert scripts.get_revision("0002").down_revision == "0001"
    assert len(scripts.get_heads()) == 1


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source
    assert source.count("DateTime(timezone=True)") == 3


def test_upgrade_adds_the_three_tables(at_0002: str) -> None:
    assert table_names(at_0002) == [
        "accounts",
        "alembic_version",
        "balance_snapshots",
        "statements",
        "transactions",
    ]
    assert versions(at_0002) == ["0002"]


@pytest.mark.parametrize("table", TABLES)
def test_columns_types_and_nulls(at_0002: str, table: str) -> None:
    columns = reflect(at_0002, table, "get_columns")
    found = [(column["name"], str(column["type"]), column["nullable"]) for column in columns]
    assert found == COLUMNS[table]
    assert [column["default"] for column in columns] == [None] * len(columns)


@pytest.mark.parametrize("table", TABLES)
def test_primary_key_is_named(at_0002: str, table: str) -> None:
    primary_key = reflect(at_0002, table, "get_pk_constraint")
    assert primary_key["name"] == f"pk_{table}"
    assert primary_key["constrained_columns"] == ["id"]


@pytest.mark.parametrize("table", TABLES)
def test_unique_constraints(at_0002: str, table: str) -> None:
    uniques = reflect(at_0002, table, "get_unique_constraints")
    assert [(unique["name"], unique["column_names"]) for unique in uniques] == UNIQUES[table]


@pytest.mark.parametrize("table", TABLES)
def test_foreign_keys(at_0002: str, table: str) -> None:
    keys = reflect(at_0002, table, "get_foreign_keys")
    found = sorted((key["name"], key["constrained_columns"], key["referred_table"]) for key in keys)
    assert found == FOREIGN_KEYS[table]
    assert all(key["referred_columns"] == ["id"] for key in keys)


@pytest.mark.parametrize("table", TABLES)
def test_indexes(at_0002: str, table: str) -> None:
    indexes = reflect(at_0002, table, "get_indexes")
    found = sorted((index["name"], index["column_names"]) for index in indexes)
    assert found == INDEXES[table]
    assert all(not index["unique"] for index in indexes)


def test_upgrade_keeps_existing_accounts(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0001")
    engine = get_engine(url)
    with session_scope(engine) as session:
        session.add(AccountRow(name="Test Card", institution="Test Bank", type="credit_card"))
    engine.dispose()
    command.upgrade(config, "0002")
    engine = get_engine(url)
    with session_scope(engine) as session:
        names = [row.name for row in session.query(AccountRow).all()]
    engine.dispose()
    assert names == ["Test Card"]


def test_the_tables_work_with_the_orm(with_accounts: str) -> None:
    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        statement = StatementRow(
            account_id=1,
            source_filename="jan.pdf",
            file_sha256="a" * 64,
            parser_name="fake_bank",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            opening_balance_cents=-10000,
            closing_balance_cents=-10450,
            lines_parsed=1,
            rows_inserted=1,
            rows_duplicate=0,
        )
        session.add(statement)
        session.flush()
        row = transaction(1, "f" * 64)
        row.statement_id = statement.id
        session.add(row)
        session.add(
            BalanceSnapshotRow(
                account_id=1, as_of_date=date(2026, 1, 31), balance_cents=-10450, source="statement"
            )
        )
    with session_scope(engine) as session:
        stored = session.query(TransactionRow).one()
        found = (stored.statement_id, stored.is_pending, stored.transaction_date, stored.section)
        assert found == (1, False, None, None)
        assert session.query(StatementRow).one().imported_at is not None
        assert session.query(BalanceSnapshotRow).one().balance_cents == -10450
    engine.dispose()


def test_amounts_beyond_32_bits_are_stored_exactly(with_accounts: str) -> None:
    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        row = transaction(1, "f" * 64)
        row.amount_cents = -9007199254740993
        session.add(row)
    with session_scope(engine) as session:
        assert session.query(TransactionRow).one().amount_cents == -9007199254740993
    engine.dispose()


def test_a_transaction_needs_a_real_account(with_accounts: str) -> None:
    engine = get_engine(with_accounts)
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(transaction(99, "f" * 64))
    engine.dispose()


def test_a_fingerprint_is_unique_within_one_account(with_accounts: str) -> None:
    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        session.add(transaction(1, "f" * 64))
        session.add(transaction(2, "f" * 64))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(transaction(1, "f" * 64))
    engine.dispose()


def test_a_file_hash_is_stored_once(with_accounts: str) -> None:
    def statement(account_id: int) -> StatementRow:
        return StatementRow(
            account_id=account_id,
            source_filename="jan.pdf",
            file_sha256="a" * 64,
            parser_name="fake_bank",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            opening_balance_cents=0,
            closing_balance_cents=0,
            lines_parsed=0,
            rows_inserted=0,
            rows_duplicate=0,
        )

    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        session.add(statement(1))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(statement(2))
    engine.dispose()


def test_one_balance_per_account_date_and_source(with_accounts: str) -> None:
    def snapshot(account_id: int, day: int, source: str) -> BalanceSnapshotRow:
        return BalanceSnapshotRow(
            account_id=account_id, as_of_date=date(2026, 1, day), balance_cents=0, source=source
        )

    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        session.add(snapshot(1, 31, "statement"))
        session.add(snapshot(1, 31, "aggregator"))
        session.add(snapshot(1, 30, "statement"))
        session.add(snapshot(2, 31, "statement"))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(snapshot(1, 31, "statement"))
    engine.dispose()


def test_downgrade_removes_only_the_three_tables(with_accounts: str) -> None:
    command.downgrade(make_config(with_accounts), "0001")
    assert table_names(with_accounts) == ["accounts", "alembic_version"]
    assert versions(with_accounts) == ["0001"]
    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        assert session.query(AccountRow).count() == 2
    engine.dispose()


def test_downgrade_then_upgrade_restores_the_tables(at_0002: str) -> None:
    config = make_config(at_0002)
    command.downgrade(config, "0001")
    command.upgrade(config, "0002")
    assert table_names(at_0002)[2:] == ["balance_snapshots", "statements", "transactions"]
    assert reflect(at_0002, "transactions", "get_indexes") != []
```

## Given fixtures

Replace the whole content of `tests/conftest.py` with this. Everything that was there is unchanged. The additions are a parser for a made-up bank format and two fixtures:

- `fake_bank` registers `FakeBankParser` for the test (through `parser_registry`) and returns it.
- `fake_statement_pdf(**changes)` returns PDF bytes of a fake statement. With no arguments it is balanced: last4 `1111`, a credit card, 2026-01-01 to 2026-01-31, opening `-100.00`, closing `-84.99`, and the four rows in `FAKE_ROWS`, two of which are identical. Pass `last4`, `account_type`, `start`, `end`, `opening`, `closing`, `rows`, or `totals` to change it. The format is described in the parser's docstring.

Use these for every service test. The service is tested with real PDF bytes going through `extract_pages`, not with a patched function.

```python
import io
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from sqlalchemy import Engine

from finances.config import Settings, get_settings
from finances.db.engine import get_engine
from finances.db.migrate import upgrade_to_head
from finances.domain.models import AccountType
from finances.ingest.parsers import register, registered_parsers, unregister
from finances.ingest.parsers.helpers import parse_amount
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

_ENV_KEYS = ("FIN_ENVIRONMENT", "FIN_DATA_DIR", "FIN_DATABASE_URL", "FIN_LOG_LEVEL")


@pytest.fixture
def tmp_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Settings]:
    """Settings whose data dir is under tmp_path, with no .env file in reach."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FIN_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    """URL of a SQLite database file under tmp_path. The file does not exist yet."""
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def db_engine(db_url: str) -> Iterator[Engine]:
    """Engine for a temporary database that has been migrated to the newest revision."""
    upgrade_to_head(db_url)
    engine = get_engine(db_url)
    yield engine
    engine.dispose()


def _build_pdf(pages: list[list[str]]) -> bytes:
    objects = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        operators = ["BT", "/F1 10 Tf"]
        for index, line in enumerate(lines):
            for column, cell in enumerate(line.split("\t")):
                text = cell.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                position = f"1 0 0 1 {72 + 180 * column} {720 - 14 * index} Tm"
                operators.append(f"{position} ({text}) Tj")
        operators.append("ET")
        stream = "\n".join(operators).encode("latin-1")
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        resources = b"/Resources << /Font << /F1 3 0 R >> >>"
        page = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] %s /Contents %d 0 R >>"
        objects.append(page % (resources, len(objects)))
        kids.append(len(objects))
    references = b" ".join(b"%d 0 R" % kid for kid in kids)
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (references, len(kids))
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1)
    out += b"startxref\n%d\n%%%%EOF\n" % xref
    return bytes(out)


@pytest.fixture
def make_pdf() -> Callable[[list[list[str]]], bytes]:
    """Return a function that builds a PDF: one inner list of text lines per page.

    A tab inside a line starts a new column 180 points to the right, the way statement
    tables are printed: three separate pieces of text on one row.
    """
    return _build_pdf


@pytest.fixture
def encrypt_pdf() -> Callable[[bytes, str], bytes]:
    """Return a function that encrypts PDF bytes so that opening them needs user_password."""

    def encrypt(content: bytes, user_password: str) -> bytes:
        writer = PdfWriter(clone_from=PdfReader(io.BytesIO(content)))
        writer.encrypt(user_password=user_password, owner_password="owner", algorithm="RC4-128")
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    return encrypt


@pytest.fixture
def parser_registry() -> Iterator[None]:
    """Give the test an empty parser registry, and put the real one back afterwards."""
    saved = registered_parsers()
    for parser in saved:
        unregister(parser.name)
    yield
    for parser in registered_parsers():
        unregister(parser.name)
    for parser in saved:
        register(parser)


FAKE_ROWS = (
    "2026-01-05|2026-01-04|purchases|-4.50|2222|-|ACME COFFEE #12",
    "2026-01-06|-|purchases|-25.99|2222|7838|FOOBAR   GROCERY",
    "2026-01-05|2026-01-04|purchases|-4.50|2222|-|ACME COFFEE #12",
    "2026-01-20|-|payments_credits|50.00|-|-|PAYMENT THANK YOU",
)


class FakeBankParser:
    """A parser for a made-up text format, so import tests need no real bank layout.

    FAKEBANK STATEMENT
    ACCOUNT <last4> <account type>
    PERIOD <start> <end>
    OPENING <amount>
    CLOSING <amount>
    TOTAL <section> <amount>          (optional, any number)
    ROW <posted>|<transaction or ->|<section>|<amount>|<card last4 or ->|<reference or ->|<text>
    """

    name = "fake_bank"

    def detect(self, first_page: str) -> bool:
        return first_page.lstrip().startswith("FAKEBANK STATEMENT")

    def parse(self, pages: list[str]) -> ParsedStatement:
        try:
            return self._parse([line.strip() for page in pages for line in page.splitlines()])
        except (KeyError, ValueError, IndexError):
            raise StatementError("fake statement is malformed") from None

    def _parse(self, lines: list[str]) -> ParsedStatement:
        fields = {}
        totals = {}
        rows = []
        for line in lines:
            keyword, _, rest = line.partition(" ")
            if keyword == "TOTAL":
                section, amount = rest.split()
                totals[Section(section)] = parse_amount(amount)
            elif keyword == "ROW":
                posted, transaction, section, amount, card, reference, text = rest.split("|", 6)
                rows.append(
                    StatementLine(
                        posted_date=date.fromisoformat(posted),
                        transaction_date=None
                        if transaction == "-"
                        else date.fromisoformat(transaction),
                        description=text,
                        amount_cents=parse_amount(amount),
                        section=Section(section),
                        card_last4=None if card == "-" else card,
                        external_ref=None if reference == "-" else reference,
                    )
                )
            elif keyword in {"ACCOUNT", "PERIOD", "OPENING", "CLOSING"}:
                fields[keyword] = rest.split()
        return ParsedStatement(
            parser_name=self.name,
            institution="Fake Bank",
            account_type=AccountType(fields["ACCOUNT"][1]),
            account_last4=fields["ACCOUNT"][0],
            period_start=date.fromisoformat(fields["PERIOD"][0]),
            period_end=date.fromisoformat(fields["PERIOD"][1]),
            opening_balance_cents=parse_amount(fields["OPENING"][0]),
            closing_balance_cents=parse_amount(fields["CLOSING"][0]),
            lines=rows,
            declared_section_totals=totals,
        )


def _fake_statement_lines(
    *,
    last4: str = "1111",
    account_type: str = "credit_card",
    start: str = "2026-01-01",
    end: str = "2026-01-31",
    opening: str = "-100.00",
    closing: str = "-84.99",
    rows: tuple[str, ...] = FAKE_ROWS,
    totals: tuple[str, ...] = (),
) -> list[str]:
    return [
        "FAKEBANK STATEMENT",
        f"ACCOUNT {last4} {account_type}",
        f"PERIOD {start} {end}",
        f"OPENING {opening}",
        f"CLOSING {closing}",
        *(f"TOTAL {total}" for total in totals),
        *(f"ROW {row}" for row in rows),
    ]


@pytest.fixture
def fake_bank(parser_registry: None) -> FakeBankParser:
    """Register the fake bank parser for this test and return it."""
    parser = FakeBankParser()
    register(parser)
    return parser


@pytest.fixture
def fake_statement_pdf() -> Callable[..., bytes]:
    """Return a function that builds a fake bank statement as PDF bytes.

    With no arguments it is a balanced card statement for last4 1111: four rows (two of
    them identical), opening -100.00, closing -84.99. Keyword arguments replace parts of
    it: last4, account_type, start, end, opening, closing, rows, totals.
    """

    def build(**changes: object) -> bytes:
        return _build_pdf([_fake_statement_lines(**changes)])

    return build
```

## Tests to write

Synthetic data only. Every requirement in Parts 1, 2, 4, and 5 needs at least one test that fails when the requirement is broken; R8 to R10 are covered by the given file. Integration tests use the `db_engine` fixture, which migrates a temporary database, and never call `metadata.create_all`.

`tests/unit/test_statement_models.py` (R1 to R3): the enum's members and order; each dataclass's field names, order, and types; that each is frozen and has no defaults.

`tests/unit/test_statement_orm.py` (R4 to R7), without a database, in the way `tests/unit/test_orm.py` inspects `AccountRow.__table__`:

- column names in order, types and lengths, and null settings, for each table
- the Python defaults, and the absence of server defaults
- each converter copying every field, giving a `DataSource`, and rejecting an unknown source
- a timestamp without a time zone coming back as UTC, and one with a time zone unchanged

`tests/integration/test_statement_repositories.py` (R11 to R19):

- each function's result, and what a second session sees after the first commits
- that none of the writing functions commits: after `session.rollback()` nothing is stored
- orderings, with rows inserted in an order that differs from the expected one, and ties
- `existing_fingerprints` with more than 1,000 fingerprints, with a generator, with an empty iterable, and with another account holding the same fingerprint
- both ends of a date range being inclusive, each end alone, and the default limit
- the exact `ValueError` message for a bad limit
- `add_balance_snapshot` called twice for the same account, date, and source with different balances

`tests/integration/test_import_service.py` (R20 to R32), with the `fake_bank` and `fake_statement_pdf` fixtures:

- a successful import: the whole result, and every stored field of the statement, the transactions, and the balance snapshot, including that the two identical rows are both stored and that fingerprints equal `fingerprint_lines` for the account
- the same bytes again, and again as a dry run
- a second statement that repeats some rows of the first and adds one
- a dry run on an empty database: the counts, and no row in any of the three tables
- each `FAILED` message in R21 to R24, exactly, and no row written by any of them; for R21 use bytes that are not a PDF, a PDF no parser recognizes, and a fake statement the parser rejects
- an account chosen by name among two that share the digits, and a named account with no digits
- a `filename` given as a path
- that `import_statement` does not commit
- `import_folder`: name order, upper-case `.PDF`, a subfolder and a non-PDF file ignored, a failing file in the middle, a dry run, and an empty folder

## Rules for this phase

- **Money is `int` cents** in every dataclass, column, and test. `float` does not appear in the listed modules.
- **A statement that does not reconcile is not stored.** There is no flag to override this.
- **Privacy.** Nothing is logged or printed. Result messages and exception messages contain no description, amount, or balance. The only statement-derived text in a message is the last four digits, institution name, and account type in the R23 hint, and section names and a difference in cents in R24.
- **Layering.** `domain` imports nothing from the project. `db` imports `domain`. `ingest` imports `domain` and `db`. Nothing here imports `cli`.
- **Portable SQL.** Queries are built with SQLAlchemy's `select`; no SQL text and nothing SQLite-specific.
- **Migrations.** One new migration. `0001` and `env.py` are not edited. Tests migrate with `upgrade_to_head` or Alembic, never `metadata.create_all`.
- **Earlier tests stay as they are.** If an existing test fails, the new code is wrong.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, at least `543 passed`, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/integration/test_migration_0002.py tests/integration/test_migrations.py --no-cov` | exactly `44 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| the search below | no output |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.ingest --cov=finances.db --cov=finances.domain --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -E "float|print\(|logging|server_default|create_all|finances\.cli" -- src/finances/domain src/finances/db/orm.py src/finances/db/repositories.py src/finances/db/migrations/versions/0002_statements.py src/finances/ingest/service.py`

The coverage command measures three packages that are at 100% today. A line no test reaches is either missing a test or is code no requirement asks for.

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 3c: storing and importing statements (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give the final passed count. Under "Deviations", list every design choice the spec left to you (private helpers, how the stages of `import_statement` are divided) and anything you did that the spec did not ask for, or `None`.

In your final message, give the output line of each acceptance command, and for each of R1 to R7 and R11 to R32 the name of a test that covers it.
