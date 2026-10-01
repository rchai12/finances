# Phase 2: Database and accounts

## Goal

A versioned database schema for accounts, import batches, transactions, and balance snapshots; repository functions to use it; money helpers; and CLI commands to create and list accounts.

## Read first

- `AGENTS.md` (money, sign convention, DB portability)
- `docs/architecture.md` (layering, data model overview)
- `docs/progress.md` (what Phase 1 actually built)

## In scope

- Domain dataclasses, enums, money helpers
- SQLAlchemy engine/session, ORM models
- Alembic setup and the initial migration
- Repository functions
- `fin db upgrade`, `fin accounts add`, `fin accounts list`

## Out of scope

Importing files, categories, reports. The `transactions` table is created now but nothing writes to it except tests.

## Dependencies

Add runtime: `sqlalchemy>=2.0`, `alembic>=1.13`

## Deliverables

### 1. Domain (`src/finances/domain/`)

No imports from other project packages.

`money.py`
- `parse_money(text: str) -> int`: returns cents. Must handle:
  | Input | Result |
  |---|---|
  | `"12.34"` | `1234` |
  | `"-12.34"` | `-1234` |
  | `"$1,234.56"` | `123456` |
  | `"(12.34)"` | `-1234` (accounting negative) |
  | `"12.34-"` | `-1234` (trailing minus) |
  | `"  7 "` | `700` |
  | `"12.345"` | raise `ValueError` (more than 2 decimal places) |
  | `""`, `"abc"` | raise `ValueError` |
  Use `Decimal`. Never `float`.
- `format_cents(cents: int) -> str`: `123456 -> "$1,234.56"`, `-1234 -> "-$12.34"`.

`models.py`
- `AccountType(StrEnum)`: `checking`, `savings`, `credit_card`, `other`.
- `BalanceSource(StrEnum)`: `statement`, `csv`, `manual`.
- `TransactionSource(StrEnum)`: `statement`, `csv`, `manual`.
- Frozen dataclasses mirroring the tables below: `Account`, `ImportBatch`, `Transaction`, `BalanceSnapshot`. Repositories return these, not ORM objects.

### 2. Database (`src/finances/db/`)

`engine.py`
- `get_engine(url: str | None = None)`: defaults to `get_settings().effective_database_url`. For SQLite, ensure the parent directory exists and enable `PRAGMA foreign_keys=ON` on every connection (SQLAlchemy `event.listens_for(engine, "connect")`).
- `session_scope(engine)` context manager: commit on success, rollback on exception.

`orm.py`: SQLAlchemy 2.0 declarative models (`Mapped[...]`, `mapped_column`). Use only portable types. Store enums as `String`, not native DB enums. All timestamps UTC, `DateTime(timezone=True)`.

**accounts**
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| name | String(100) | unique, user-facing label like "Chase Checking" |
| institution | String(100) | |
| type | String(20) | `AccountType` value |
| currency | String(3) | default `"USD"` |
| last4 | String(4), nullable | digits only, validated |
| is_active | Boolean | default true |
| created_at | DateTime(tz) | |

**import_batches** (one row per imported file; for PDF statements it also records the statement itself)
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| account_id | FK accounts.id | |
| source_filename | String(255) | basename only, never the full path |
| file_sha256 | String(64) | |
| format | String(10) | `pdf` / `csv` / `ofx` |
| parser_name | String(50), nullable | e.g. `capital_one_card`, or a CSV profile name |
| period_start | Date, nullable | statement period |
| period_end | Date, nullable | |
| opening_balance_cents | BigInteger, nullable | holder perspective (card debt negative) |
| closing_balance_cents | BigInteger, nullable | |
| reconciled | Boolean | true if opening + sum(lines) == closing |
| imported_at | DateTime(tz) | |
| rows_read | Integer | |
| rows_inserted | Integer | |
| rows_duplicate | Integer | |
Constraint: `UniqueConstraint(account_id, file_sha256)`.

**transactions**
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| account_id | FK accounts.id, indexed | |
| import_batch_id | FK import_batches.id, nullable | |
| posted_date | Date, indexed | |
| transaction_date | Date, nullable | date of purchase if the source gives it; reports prefer this over `posted_date` |
| amount_cents | BigInteger | sign convention from AGENTS.md |
| raw_description | String(500) | exactly as in the file |
| description_normalized | String(500) | |
| section | String(30), nullable | source section, e.g. `purchases`, `payments_credits`, `fees`, `interest`, `deposits`, `withdrawals` |
| card_last4 | String(4), nullable | which card on a multi-card account |
| cardholder | String(100), nullable | name as printed; stays local, never sent to the LLM |
| external_id | String(100), nullable | e.g. OFX FITID or statement reference number |
| source | String(10) | `statement` / `csv` / `manual`; server default `statement`. CSV rows are provisional until a statement covers them (Phase 8) |
| fingerprint | String(64) | dedup key, see Phase 3 |
| created_at | DateTime(tz) | |
Constraint: `UniqueConstraint(account_id, fingerprint)`.

**balance_snapshots**
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| account_id | FK accounts.id | |
| as_of_date | Date | |
| balance_cents | BigInteger | credit card debt is negative |
| source | String(20) | `BalanceSource` value |
| created_at | DateTime(tz) | |
Constraint: `UniqueConstraint(account_id, as_of_date, source)`.

`repositories.py`: plain functions taking a `Session` as the first argument and returning domain dataclasses.
- `create_account(session, name, institution, type, currency="USD", last4=None) -> Account`. Raise `AccountExistsError` on duplicate name (case-insensitive check). Raise `ValueError` if `last4` is not exactly 4 digits.
- `get_account_by_name(session, name) -> Account | None` (case-insensitive).
- `find_accounts_by_last4(session, last4) -> list[Account]` (used to auto-match statements to accounts).
- `list_accounts(session, include_inactive=False) -> list[Account]` ordered by name.
- `create_import_batch(session, ...) -> ImportBatch`, `find_import_batch_by_hash(session, account_id, sha256) -> ImportBatch | None`, `update_import_batch_counts(session, batch_id, rows_read, rows_inserted, rows_duplicate)`.
- `insert_transactions(session, rows: list[NewTransaction]) -> int` where `NewTransaction` is a domain dataclass without `id`/`created_at`. Returns count inserted.
- `existing_fingerprints(session, account_id, fingerprints: Iterable[str]) -> set[str]`. Query in chunks of 500 to stay under parameter limits on all databases.
- `list_transactions(session, account_id=None, start=None, end=None, limit=100) -> list[Transaction]` newest first.
- `add_balance_snapshot(...)`, `latest_balance(session, account_id) -> BalanceSnapshot | None`.

### 3. Alembic

- `alembic.ini` at repo root, `migrations/` directory.
- `migrations/env.py` gets the URL from `get_settings().effective_database_url` (not from `alembic.ini`) and uses `target_metadata` from `orm.py`.
- Set `render_as_batch=True` (required for SQLite ALTER TABLE support in later phases).
- One migration `0001_initial` creating the four tables. Use a readable revision id `"0001"`.
- `src/finances/db/migrate.py`: `upgrade_to_head(url: str | None = None)` runs Alembic programmatically. It must work regardless of the current working directory (locate `alembic.ini` relative to the package, or build the Alembic `Config` in code).

### 4. CLI

New Typer sub-apps, registered in `cli/main.py`:
- `fin db upgrade`: runs `upgrade_to_head()`, prints the resulting revision.
- `fin accounts add --name TEXT --institution TEXT --type [checking|savings|credit_card|other] [--currency USD] [--last4 1234]`
- `fin accounts list`: Rich table: name, institution, type, last4 shown as `••1234`, active.
- Errors (duplicate name, bad last4) print a one-line message and exit 1, no traceback.
- Extend `fin doctor` with a check: "Database schema" shows current revision vs head (`FAIL` with hint `run: fin db upgrade` if behind).

## Tests

Use a fixture that creates a fresh SQLite database under `tmp_path` and runs `upgrade_to_head` on it (tests the migration, not `metadata.create_all`).

- `test_money.py`: every row of the `parse_money` table; `format_cents` both signs and zero.
- `test_migrations.py`: after upgrade, all four tables exist; running upgrade twice is a no-op.
- `test_repositories.py`
  - create and fetch account; duplicate name (different case) raises; bad last4 raises.
  - `insert_transactions` + `existing_fingerprints` round trip; unique constraint on `(account_id, fingerprint)` enforced; same fingerprint allowed on a different account.
  - `existing_fingerprints` with 1,200 inputs works (chunking).
  - foreign keys enforced (insert transaction with unknown account fails).
  - `latest_balance` returns the newest `as_of_date`.
- `test_cli_accounts.py`: add then list shows the account; duplicate add exits 1.

## Acceptance criteria

```powershell
ruff check . ; ruff format --check . ; pytest
fin db upgrade
fin accounts add --name "Test Checking" --institution "Test Bank" --type checking --last4 1234
fin accounts list
fin doctor
```

All succeed; `data/finances.db` is created and not tracked by git.

Append your entry to `docs/progress.md`.
