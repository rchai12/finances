# Phase 3: Statement import core

## Goal

Shared machinery for importing PDF statements: text extraction, a common parsed-statement model, a parser registry, year inference, reconciliation, dedup, and an import service plus CLI. **No real bank parser yet.** Phases 4 to 6 each add bank parsers that plug into this.

## Read first

- `AGENTS.md` (especially privacy rule 6 about real samples)
- `docs/architecture.md`
- `docs/statement-formats.md` (skim, to understand what parsers will need)
- `docs/progress.md`, `src/finances/db/repositories.py`, `src/finances/domain/`

## In scope

- PDF to page-text extraction
- `ParsedStatement` / `StatementLine` model
- `StatementParser` protocol and registry with auto-detection
- Date helpers (year inference)
- Reconciliation
- Fingerprinting
- Import service (single file and folder)
- CLI: `fin import statement`, `fin import folder`, `fin statements list`, `fin transactions list`
- Opt-in real-sample test harness

## Out of scope

Any real bank parser (Phases 4 to 6), categories, merchant cleanup, CSV.

## Dependencies

Add runtime: `pypdf>=5` (pure Python; layout extraction mode required).

## Deliverables

### 1. PDF text (`src/finances/ingest/pdf_text.py`)

```python
def extract_pages(content: bytes) -> list[str]
```
- Uses `pypdf.PdfReader(io.BytesIO(content))` and `page.extract_text(extraction_mode="layout")`.
- Suppress pypdf's warnings (e.g. "Rotated text discovered") from reaching the console; log them at DEBUG.
- Encrypted PDF or unreadable file → raise `StatementError("could not read PDF: <reason>")`.
- Takes bytes, not a path.

### 2. Model (`src/finances/ingest/statement.py`)

```python
@dataclass(frozen=True)
class StatementLine:
    posted_date: date
    transaction_date: date | None
    description: str            # raw, whitespace-collapsed
    amount_cents: int           # holder perspective (AGENTS.md)
    section: str                # payments_credits | purchases | fees | interest | deposits | withdrawals | checks
    card_last4: str | None = None
    cardholder: str | None = None
    external_ref: str | None = None

@dataclass(frozen=True)
class ParsedStatement:
    parser_name: str            # e.g. "capital_one_card"
    institution: str            # display name, e.g. "Capital One"
    account_type: AccountType
    account_last4: str
    period_start: date
    period_end: date
    opening_balance_cents: int  # holder perspective
    closing_balance_cents: int
    lines: list[StatementLine]
    declared_section_totals: dict[str, int] = field(default_factory=dict)  # optional, holder perspective
```

### 3. Parser protocol and registry (`src/finances/ingest/parsers/__init__.py`)

```python
class StatementParser(Protocol):
    name: str
    def detect(self, first_page: str) -> bool: ...
    def parse(self, pages: list[str]) -> ParsedStatement: ...

def register(parser: StatementParser) -> None
def registered_parsers() -> list[StatementParser]
def detect_parser(pages: list[str]) -> StatementParser
```
- `detect_parser` calls `detect(pages[0])` on every registered parser. Zero matches → `StatementError("unrecognized statement format")`. More than one → `StatementError` naming the matches.
- Parsers operate on **text only**. That keeps them testable with synthetic text fixtures; no PDFs are needed in tests.
- The registry starts empty in this phase. Bank parsers register themselves in later phases (e.g. imported in `parsers/__init__.py`).

### 4. Shared parsing helpers (`src/finances/ingest/parsers/helpers.py`)

- `infer_year(month: int, day: int, period_start: date, period_end: date) -> date`: try years `period_end.year` and `period_end.year - 1`; return the candidate that lies within `[period_start - 60 days, period_end + 7 days]`. If none or both qualify, raise `StatementError`. (Transactions can predate the period slightly, e.g. trans date Dec 23 in a period starting Dec 24.)
- `parse_month_day(text: str, period_start, period_end) -> date` for `"Jan 5"` and `"01/05"` styles.
- `parse_amount(text: str) -> int`: wraps `parse_money` and also accepts `"- $1,234.56"`, `"-$12.00"`, `"+ $3.00"`, `"= $10.00"` (the `=` is ignored).
- `collapse_ws(text) -> str`.
- `find_labeled_amount(pages_text: str, label_regex: str) -> int | None`: finds the first money value following a label on the same line. Many summaries need this.

### 5. Reconciliation (`src/finances/ingest/reconcile.py`)

```python
@dataclass(frozen=True)
class ReconcileResult:
    ok: bool
    expected_closing_cents: int    # opening + sum(lines)
    actual_closing_cents: int
    difference_cents: int
    section_mismatches: dict[str, tuple[int, int]]   # section -> (declared, computed)

def reconcile(stmt: ParsedStatement) -> ReconcileResult
```
- `ok` only if `opening + sum(line amounts) == closing` exactly **and** every declared section total matches the computed sum for that section.
- This is the main safeguard against parser bugs. Do not loosen it with tolerances.

### 6. Fingerprints (`src/finances/ingest/dedup.py`)

```python
def fingerprint_lines(account_id: int, lines: list[StatementLine]) -> list[str]
```
- If `external_ref` is present: `sha256(f"{account_id}|ref|{posted_date}|{external_ref}|{amount_cents}")`.
- Otherwise: key `(posted_date, amount_cents, upper(collapse_ws(description)), card_last4 or "")` plus an occurrence counter for repeats of the same key within this statement (0, 1, 2...). Hash `account_id|key fields|occurrence`.
- Two identical $5.00 purchases on the same day both survive; re-importing the same statement produces identical fingerprints.

### 7. Import service (`src/finances/ingest/service.py`)

```python
@dataclass(frozen=True)
class StatementImportResult:
    filename: str
    parser_name: str | None
    account_name: str | None
    period: tuple[date, date] | None
    lines_parsed: int
    inserted: int
    duplicates: int
    reconcile: ReconcileResult | None
    status: Literal["imported", "dry_run", "already_imported", "failed"]
    message: str           # short, no transaction contents

def import_statement(session, *, filename: str, content: bytes,
                     account_name: str | None = None,
                     dry_run: bool = False,
                     allow_mismatch: bool = False) -> StatementImportResult
```
Steps:
1. `sha256(content)`. If any batch has this hash → status `already_imported` (not an error).
2. Extract pages, detect parser, parse.
3. Resolve account:
   - if `account_name` is given, use it; if its `last4` is set and differs from `account_last4`, fail with a clear message.
   - else `find_accounts_by_last4(account_last4)`: exactly one → use it; zero → fail with a hint: `fin accounts add --name "..." --institution "<institution>" --type <type> --last4 <last4>`; several → fail asking for `--account`.
4. Reconcile. If not ok and not `allow_mismatch` → `failed`, message includes the difference in cents and any section mismatches. Write nothing.
5. Fingerprint, drop lines whose fingerprint already exists for the account.
6. `dry_run` → return counts, write nothing.
7. In one transaction: create the import batch (format `pdf`, parser name, period, opening/closing, `reconciled` flag), insert transactions (`description_normalized` = upper + collapsed whitespace), and add a `balance_snapshots` row (`as_of_date = period_end`, `source = statement`, closing balance). If a snapshot already exists for that account/date/source, leave it.

```python
def import_folder(session_factory, folder: Path, **kwargs) -> list[StatementImportResult]
```
- Every `*.pdf` (case-insensitive) in the folder, sorted by name; each file in its own transaction; one failure does not stop the rest.

### 8. CLI

- `fin import statement PATH [--account NAME] [--dry-run] [--allow-mismatch]`: prints parser, account, period, lines, inserted, duplicates, reconciliation status. Exit 1 on `failed`.
- `fin import folder DIR [--dry-run]`: one summary row per file in a Rich table (file, parser, account, period, inserted, status). Exit 1 if any failed.
- `fin statements list [--account NAME]`: batches with period, opening, closing, reconciled flag.
- `fin transactions list [--account NAME] [--from DATE] [--to DATE] [--limit 50]`: amounts via `format_cents`, negatives red, shows cardholder initials and card last4 when present.

### 9. Real-sample harness (`tests/test_real_samples.py`)

- Register a pytest marker `real_samples` in `pyproject.toml`.
- Skipped unless env `FIN_REAL_SAMPLES=1` **and** `data/samples/` exists.
- Parametrized over each PDF in `data/samples/`. For each: extract, detect, parse, reconcile. Assert that reconciliation is ok and that at least one line was parsed when opening != closing. Assert nothing about content.
- Test IDs must be generic (`sample_0`, `sample_1`), **not filenames**, and failure messages must contain only parser name, counts, and cent differences. No descriptions, no names.
- In this phase every sample is expected to fail detection (no parsers yet). Mark them `xfail(strict=False)` when no parser detects the file, so the harness is ready for Phases 4 to 6.

## Tests (synthetic only)

Create a fake parser **in the test suite** (`tests/fakes.py`) that parses a simple text format, e.g.:
```
FAKEBANK STATEMENT
ACCOUNT 1111
PERIOD 2026-01-01 2026-01-31
OPENING -100.00
CLOSING -150.25
ROW 2026-01-05 purchases ACME COFFEE -5.00
...
```
Tests call the service with a monkeypatched `extract_pages` returning this text, so no PDF files are needed. Provide a fixture that registers the fake parser and restores the registry afterwards, so tests do not leak parsers into each other.

- `test_helpers.py`: `infer_year` handles Dec/Jan wrap (period Dec 24 2025 to Jan 23 2026: "Dec 23" → 2025-12-23, "Jan 5" → 2026-01-05); out-of-range raises; `parse_amount` for each sign style.
- `test_registry.py`: no match raises; two matches raise; exactly one returns it.
- `test_reconcile.py`: balanced statement ok; off by 1 cent fails with difference 1; section total mismatch fails.
- `test_dedup.py`: identical same-day lines get different fingerprints; same statement twice gives identical fingerprints; different `card_last4` gives different fingerprints.
- `test_import_service.py` (migrated temp DB):
  - auto-match by last4; zero matches gives the `fin accounts add` hint; `--account` with mismatched last4 fails.
  - successful import writes batch, transactions, and a balance snapshot.
  - same bytes again → `already_imported`, nothing written.
  - unreconciled statement fails and writes nothing; with `allow_mismatch=True` imports with `reconciled = False`.
  - dry run writes nothing.
  - `import_folder` continues past a failing file.
- `test_pdf_text.py`: generate a tiny one-page PDF in the test with `pypdf` (blank page is fine) and confirm `extract_pages` returns one string; garbage bytes raise `StatementError`.

## Acceptance criteria

```powershell
ruff check . ; ruff format --check . ; pytest
fin import folder data/samples --dry-run     # every file reports "unrecognized statement format" (expected in this phase)
$env:FIN_REAL_SAMPLES=1; pytest -m real_samples; Remove-Item Env:FIN_REAL_SAMPLES   # all xfail, none error
```

Append your entry to `docs/progress.md`.
