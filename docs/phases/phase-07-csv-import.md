# Phase 7: CSV import

## Goal

Import CSV exports (Truist checking, Citi card) as **provisional** transactions that fill the gap after the latest statement. Profiles are auto-detected from the header row. CSV rows that match a transaction on an already-imported statement are skipped. (Phase 8 handles the reverse case: a statement arriving after CSV rows.)

## Read first

- `AGENTS.md` (rule 6 applies to the real CSVs in `data/samples/` too)
- `docs/statement-formats.md`, sections 6 and 7 and "Cross-source notes"
- `docs/progress.md`
- `src/finances/ingest/service.py`, `dedup.py`, `parsers/helpers.py`

## In scope

- Migration adding `bank_merchant`, `bank_category` to `transactions`
- CSV profile format, built-in profiles, user overrides
- CSV parser with header auto-detection
- End-of-day running balance check
- Shared transaction matcher (amount + nearby date), also used by Phase 8
- CSV import service, including skipping rows already on an imported statement
- `fin import csv`, CSV support in `fin import folder`, `fin profiles list`

## Out of scope

Replacing CSV rows when a statement arrives (Phase 8). Categorization (Phase 9).

## Dependencies

None new (stdlib `csv`, `tomllib`).

## Deliverables

### 1. Migration

New Alembic revision adding to `transactions`:
| Column | Type | Notes |
|---|---|---|
| bank_merchant | String(200), nullable | institution's merchant name, a hint only |
| bank_category | String(200), nullable | `"Category / Sub-category"`, a hint only |

Update the domain `Transaction` dataclass and repositories accordingly.

### 2. Profile format (`src/finances/ingest/csv_profiles.py`)

A profile is a TOML file. Built-ins go in `src/finances/ingest/csv_profiles/*.toml` (package data). User profiles in `<data_dir>/profiles/*.toml` override built-ins with the same `name`.

```toml
name = "truist_checking_csv"
institution = "Truist"
account_type = "checking"

[detect]
header = ["Posted Date", "Transaction Date", "Transaction Type", "Check/Serial #",
          "Full description", "Merchant name", "Category name", "Sub-category name",
          "Amount", "Daily Posted Balance"]
filename_last4 = 'acct_(\d{4})_'          # optional regex, group 1 = account last4

[csv]
encoding = "utf-8-sig"
delimiter = ","

[columns]
posted_date = "Posted Date"
transaction_date = "Transaction Date"       # optional
description = "Full description"
amount = "Amount"                          # EITHER amount OR debit + credit
running_balance = "Daily Posted Balance"   # optional
bank_merchant = "Merchant name"            # optional
bank_category = ["Category name", "Sub-category name"]   # optional, joined with " / ", blanks dropped

[parse]
date_format = "%m/%d/%Y"
```

```toml
name = "citi_card_csv"
institution = "Citi"
account_type = "credit_card"

[detect]
header = ["Status", "Date", "Description", "Debit", "Credit", "Member Name"]

[columns]
posted_date = "Date"
description = "Description"
debit = "Debit"
credit = "Credit"
status = "Status"
cardholder = "Member Name"

[parse]
date_format = "%m/%d/%Y"
include_status = ["Cleared"]
```

Rules:
- Required: `name`, `institution`, `account_type`, `detect.header`, `columns.posted_date`, `columns.description`, `parse.date_format`, and exactly one of `amount` / (`debit` + `credit`).
- Debit/credit mode: exactly one of the two cells must be non-empty; use the **absolute value**; debit → negative, credit → positive.
- Single amount mode: `parse_money` handles `($1.50)` and `$2000.00`; value is already holder perspective.
- If `include_status` is set, rows whose status is not listed are skipped and counted.
- Invalid profiles raise `ProfileError`.

### 3. Parser (`src/finances/ingest/csv_parser.py`)

```python
@dataclass(frozen=True)
class CsvRow:
    line_number: int
    posted_date: date
    transaction_date: date | None
    description: str
    amount_cents: int
    running_balance_cents: int | None
    cardholder: str | None
    bank_merchant: str | None
    bank_category: str | None

@dataclass(frozen=True)
class CsvParseResult:
    profile: CsvProfile
    rows: list[CsvRow]
    errors: list[RowError]            # line number + field + reason, no row contents
    skipped_status: int

def detect_profile(content: bytes) -> CsvProfile        # exact header match after stripping BOM/whitespace
def parse_csv(content: bytes, profile: CsvProfile) -> CsvParseResult
```
- Takes bytes. Blank lines skipped. Bad dates/amounts become `RowError`s; parsing continues.
- No header match → `ProfileError` listing known profile names. Multiple matches → `ProfileError`.

### 4. Running balance check (`src/finances/ingest/csv_balance.py`)

```python
def check_daily_balances(rows: list[CsvRow]) -> ReconcileResult
```
Only when the profile has `running_balance`:
- Group rows by `posted_date`; every row in a day must carry the same balance.
- For each day after the earliest: `previous_day_balance + sum(day amounts) == day_balance`.
- Works regardless of file order (sort by date first).
- Returns the existing `ReconcileResult` shape (difference and the first failing date in the message; no descriptions).

### 5. Matcher (`src/finances/ingest/matching.py`)

One rule for "is this the same real transaction from a different source", used here and in Phase 8.

```python
MATCH_MAX_DAYS = 4

@dataclass(frozen=True)
class MatchItem:
    key: int                  # caller's identifier (row index or transaction id)
    posted_date: date
    amount_cents: int
    description: str

def match_one_to_one(left: list[MatchItem], right: list[MatchItem],
                     max_days: int = MATCH_MAX_DAYS) -> list[tuple[int, int]]
```
- A candidate pair needs **equal `amount_cents`** and `abs(left.posted_date - right.posted_date) <= max_days`.
- One-to-one, greedy by smallest date difference; ties broken by description similarity (`difflib.SequenceMatcher` ratio on upper-cased, whitespace-collapsed descriptions, higher first), then by `left.key`, then `right.key`. Deterministic regardless of input order.
- Returns `(left.key, right.key)` pairs. Pure function.
- Why a date window: the same transaction can carry a purchase date in one source and a posting date in the other (e.g. the Citi CSV has a single date column), typically 1 to 3 days apart.

### 6. Import service (`src/finances/ingest/csv_service.py`)

```python
def import_csv(session, *, filename: str, content: bytes, account_name: str | None = None,
               dry_run: bool = False, allow_mismatch: bool = False,
               skip_bad_rows: bool = False) -> CsvImportResult
```
Steps:
1. File hash already imported → `already_imported`.
2. Detect profile, parse. Errors and not `skip_bad_rows` → `failed`, nothing written.
3. Resolve account: `--account`, else `filename_last4` + `find_accounts_by_last4`, else fail with a message asking for `--account`. If both are available and disagree, fail.
4. Balance check (if applicable). Failure and not `allow_mismatch` → `failed`.
5. **Skip rows already on a statement** (match, don't just compare dates). For each reconciled statement batch of this account, with `W = MATCH_MAX_DAYS`:
   - Candidate CSV rows: `posted_date` in `[period_start - W, period_end + W]`.
   - Candidate statement rows: this account's `source = "statement"` transactions in the same window.
   - Run `match_one_to_one(csv_candidates, statement_rows)`. Each statement row can be claimed once per import.
   - Then classify each candidate CSV row:
     | Situation | Action | Counted as |
     |---|---|---|
     | Matched a statement row | skip | `covered_by_statement` |
     | Unmatched, `posted_date` in `(period_end - W, period_end + W]` (boundary zone) | keep, insert as provisional | (normal insert) |
     | Unmatched, `posted_date` in `[period_start, period_end - W]` (deep inside a closed, reconciled period) | skip | `conflicts` |
   - Why: near the end of a period, a CSV row dated by purchase date can belong to the *next* statement (bought Jan 23, posted Jan 24). Keeping it as provisional avoids a temporary gap; the next statement absorbs it (Phase 8). Deep inside a reconciled period, the statement is the truth, and an unmatched CSV row would double-count.
   - If `conflicts > 0`, the CLI prints a warning with the count only.
6. Fingerprint the remaining rows in a separate namespace: `sha256(f"{account_id}|csv|{posted}|{amount}|{UPPER(collapsed desc)}|{occurrence}")`; drop existing fingerprints (`duplicates`). Overlapping CSV downloads therefore never duplicate.
7. Dry run → counts only.
8. One DB transaction: import batch (format `csv`, `parser_name` = profile name, no period or balances), transactions with `source = "csv"`, and, if a running balance exists, a `balance_snapshots` row for the latest date (`source = "csv"`; skip if one exists).

`CsvImportResult` mirrors `StatementImportResult` and adds `skipped_status`, `covered_by_statement`, and `conflicts`.

### 7. CLI

- `fin import csv PATH [--account NAME] [--dry-run] [--allow-mismatch] [--skip-bad-rows]`: prints profile, account, date range, read / inserted / duplicates / covered by statement / conflicts / skipped status, balance check result, and up to 10 errors (`line N, field: reason`).
- `fin import folder DIR`: now also picks up `*.csv` (case-insensitive) and routes them to `import_csv`. A CSV whose account cannot be resolved is reported as `failed` with the `--account` hint; other files continue.
- `fin profiles list`: name, institution, source (built-in / user).
- `fin transactions list`: add a dim `csv` marker for provisional rows.

## Fixtures (`tests/fixtures/csv/`)

Synthetic only, following the layouts in the formats doc:
- `truist/acct_1111_08_01_2026_to_08_31_2026.csv`: ~12 rows across 5 days, consistent daily balances, one Zelle-style row with an invented name, fee rows.
- `truist/bad_balance.csv`: one day's balance off by 1 cent.
- `citi/recent.csv`: newest-first, one payment with negative credit, one blank member name, one `Pending` row.
- `citi/both_columns.csv`: a row with both debit and credit filled.
- `unknown_header.csv`.

## Tests

- Profiles: built-ins load and validate; user override by name; invalid profiles raise.
- Detection: each fixture maps to the right profile; unknown header raises.
- Parsing: signs (parentheses, negative credit), bank category joining, cardholder blank → `None`, status filtering count.
- Balance check: passes on good fixture; off-by-1 fails with difference 1; same-day rows with different balances fail; order independence.
- Service (migrated temp DB):
  - Truist account resolved from filename last4; Citi requires `--account`.
  - Rows stored with `source = "csv"`; balance snapshot written for Truist only.
  - Re-import same file → `already_imported`; a second, overlapping file → only new rows inserted.
  - With a reconciled statement batch covering part of the CSV's range (create it via the fake parser from Phase 3), CSV rows matching statement rows are skipped and counted as `covered_by_statement`.
  - **Boundary case**: statement period ends Jan 23; a CSV row dated Jan 23 whose amount is not on the statement is inserted as provisional (not skipped).
  - **Sale vs post date**: statement row posted Jan 20, CSV row dated Jan 18, same amount → skipped as covered.
  - **Conflict**: CSV row dated Jan 10, inside the reconciled period, not on the statement → skipped, `conflicts == 1`.
  - Two identical-amount CSV rows near one statement row: only one is covered; the other follows the table above.
- Matcher unit tests: equal amount within window matches; 5 days apart does not; 1-cent difference does not; closest date wins; description similarity breaks ties; shuffled inputs give identical output.
  - Balance failure writes nothing; `allow_mismatch` overrides.
- CLI: `import folder` handles a mix of fake-statement and CSV files.
- Real-sample harness: extend to `*.csv` in `data/samples/`: detect profile, parse with zero errors, balance check ok where applicable. Same no-content rules.

## Acceptance criteria

```powershell
ruff check . ; ruff format --check . ; pytest
$env:FIN_REAL_SAMPLES=1; pytest -m real_samples; Remove-Item Env:FIN_REAL_SAMPLES
fin import csv "data/samples/<citi csv>" --account "<your Citi account name>" --dry-run
fin import folder data/samples --dry-run
```
Both real CSVs detect, parse, and (Truist) pass the daily balance check.

Append your entry to `docs/progress.md`.
