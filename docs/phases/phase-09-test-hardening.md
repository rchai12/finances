# Phase 9: Test hardening for the import pipeline

## Goal

The import pipeline (Phases 2 to 8) is where a silent bug corrupts every later number. This phase adds test types that the per-phase tests do not cover: property-based invariants, parser fuzzing, golden snapshots, migration consistency, and end-to-end workflows. **No product features.** Fix bugs the new tests uncover (each with a failing-first test) and record them in `docs/progress.md`.

## Read first

- `AGENTS.md`, `docs/testing.md`
- `docs/progress.md` (what was actually built in Phases 2 to 8, including known gaps)
- `src/finances/ingest/`, `src/finances/domain/money.py`, `migrations/`

## Dependencies

Add dev: `hypothesis>=6.100`

## Deliverables

### 1. Property-based tests (`tests/unit/test_properties_*.py`)

Use Hypothesis strategies built from domain types (dates in 2000 to 2099, cents in ±10,000,000,000, descriptions from a small synthetic alphabet). Register a profile in `tests/conftest.py`: `max_examples=200` by default, `derandomize=True` when env `CI` is set.

| Module | Properties |
|---|---|
| `money` | `parse_money(format_cents(c)) == c` for all `c`; accounting `(x)` equals `-x`; trailing minus equals leading minus; never returns for 3+ decimals |
| `helpers.infer_year` | result is within `[start - 60d, end + 7d]`; month and day preserved; for periods spanning a year boundary, December dates get the earlier year |
| `reconcile` | a statement built as `closing = opening + sum(lines)` always reconciles; changing any one line amount by a nonzero delta always fails with `difference == delta` |
| `csv_balance` | a row list generated with consistent running balances passes for any row order; perturbing one day's balance always fails |
| `dedup` | fingerprints deterministic; permuting rows permutes fingerprints identically; n identical rows give n distinct fingerprints; the same rows in two "files" give identical sets |
| `matching` | output is one-to-one; every pair has equal amounts and date gap ≤ `MATCH_MAX_DAYS`; shuffling either input gives identical output; the number of pairs equals the maximum possible when all candidates are mutually exclusive by amount |
| `merge.plan_merge` | every provisional id appears in at most one of upgrades / drops; every statement line appears in exactly one of upgrades / inserts; nothing outside the window is touched |

### 2. Parser fuzzing (`tests/unit/test_parser_fuzz.py`)

For every registered statement parser and every CSV profile:
- Feed Hypothesis-generated text: random lines, valid fixture lines with characters deleted or duplicated, shuffled lines, truncated pages, empty pages.
- **Property**: the parser either returns a `ParsedStatement` or raises `StatementError` / `ProfileError`. Any other exception type (`IndexError`, `ValueError`, `AttributeError`, ...) is a bug.
- Separately: a parsed result from mutated input either reconciles or is reported as unreconciled. It must never reconcile with a line count different from the original fixture's when only a single row was removed (that would mean reconciliation is being fooled).

### 3. Golden snapshot tests (`tests/golden/`)

- For each synthetic statement fixture (all banks) and CSV fixture: parse it and serialize the result to canonical JSON (sorted keys, dates ISO, cents as integers, lines in parse order).
- Compare to `tests/golden/<parser>/<fixture>.expected.json`.
- `pytest --update-golden` (custom option in `conftest.py`) rewrites the expected files. The diff is then reviewed by a human in the commit. Never auto-update in normal runs.
- Purpose: any change in parser behavior shows up as a visible diff.

### 4. Migration tests (`tests/integration/test_migrations_full.py`)

- `upgrade head` → `downgrade base` → `upgrade head` succeeds on an empty DB. Implement any missing `downgrade()` functions.
- **Model/migration drift check**: after `upgrade head`, run Alembic's autogenerate comparison (`alembic.autogenerate.compare_metadata`) against `orm.Base.metadata`. It must report no differences. This catches a model changed without a migration.
- Data survives an upgrade: create a DB at the revision before the latest, insert a row, upgrade to head, read it back.

### 5. End-to-end workflow tests (`tests/e2e/`)

Through Typer's `CliRunner`, with `FIN_DATA_DIR` pointed at `tmp_path` and `extract_pages` monkeypatched to return synthetic fixture text for `.pdf` paths (map by filename in the test).

- **Household month**: create accounts for every institution; import a folder containing one synthetic statement per bank plus both CSV kinds; assert per-account transaction counts, balances (`fin statements list`), and that re-running `fin import folder` reports everything `already_imported`.
- **Rolling month** (the January / 30-day CSV / February scenario from Phase 8), driven entirely through CLI commands, asserting the CLI output counts (`covered by statement`, `upgraded`, `provisional dropped`).
- **Failure paths**: unknown format, unreconciled statement, CSV with a bad daily balance, missing account. Each exits with code 1, writes nothing, and its output contains **no** description text from the fixture (check that a known synthetic merchant name is absent from the output).

### 6. Log hygiene test (`tests/integration/test_log_hygiene.py`)

Run a full import at the default log level with `caplog` capturing everything. Assert that no synthetic merchant name, no amount string from the fixture, and no account last4 appear in any record at INFO or above (AGENTS.md rule 4).

## Acceptance criteria

```powershell
ruff check . ; ruff format --check . ; pytest
$env:FIN_REAL_SAMPLES=1; pytest -m real_samples; Remove-Item Env:FIN_REAL_SAMPLES
```
- All new tests pass; the full suite stays under 60 seconds on a laptop.
- Bugs found are fixed and listed in `docs/progress.md` (one line each: what the test caught, what was wrong).

Append your entry to `docs/progress.md`.
