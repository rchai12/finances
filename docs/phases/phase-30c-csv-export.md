# Phase 30c: CSV export from the terminal

## Goal

A person can write CSV files a spreadsheet opens, with the owner's choices (2026-10-24): transactions, the year, and spending; files in a settings folder (or one named) and never overwritten without `--force`; amounts as plain signed decimal dollars; a split transaction as one row per part. After this phase:

- `fin export transactions` writes every transaction in a date range (this year by default), oldest first, one row per split part, with its tags and note;
- `fin export year` writes 30a's year (by group, by category, and the tax-relevant categories) as one file with a Section column;
- `fin export spending` writes the spending report for a month or range, grouped as `fin spending` groups it;
- every amount is written exactly from integer cents (`-12.34`), never through `float`, and nothing leaves the machine.

Export from the web is 30d.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/domain/money.py` (critical), `src/finances/config.py` (`backup_dir` and `effective_backup_dir`, the pattern for the new setting)
- `src/finances/analysis/search.py` (`search_transactions`, parts), `src/finances/analysis/yearend.py`, `src/finances/analysis/spending.py` (`spending_report`), `src/finances/db/repositories/tags.py` (`tags_for`, `note_of`), `src/finances/db/repositories/accounts.py` (`account_names`)
- `src/finances/views/format.py` (`mask_last4`), `src/finances/cli/reports.py` (`spending_command`'s month and range options, `year_command`), `src/finances/cli/main.py`

## Starting state

N is `3802` when Phase 30b is the last phase built. The newest migration is `0021`; this phase adds none. `tests/conftest.py` clears each `FIN_` setting it lists for every test, so the new `FIN_EXPORT_DIR` joins that list (the given diff), or a value in the owner's shell would reach the tests.

## Scope

| Path | What changes |
|---|---|
| `src/finances/domain/money.py` | `decimal_text` (R1) |
| `src/finances/config.py` | `export_dir`, `effective_export_dir` (R2) |
| `src/finances/analysis/export.py` (new) | `ExportLine`, `transactions_for_export` (R3) |
| `src/finances/views/export.py` (new) | `transactions_csv`, `year_csv`, `spending_csv` (R4) |
| `src/finances/export/__init__.py`, `src/finances/export/files.py` (new) | `write_csv` (R5) |
| `src/finances/cli/export.py` (new), `src/finances/cli/main.py` | `fin export` and its three commands (R6 to R8) |
| `tests/conftest.py` | the given diff (R9) |
| `tests/unit/test_money_decimal.py`, `tests/e2e/test_cli_export.py` | new: given |
| `tests/unit/test_export_views.py`, `tests/integration/test_export_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Export from the web (30d); any other report (months, balances, budgets, recurring, upcoming, forecast, insights, shared); filters on the transactions export.
- Other formats (Excel, JSON), a choice of columns, or a header in another language.
- Sending a file anywhere; the export writes to a local folder only.

## Dependencies

None new. No migration. The standard library's `csv` module.

## Design

```python
# src/finances/domain/money.py (critical)
def decimal_text(cents: int) -> str: ...  # -1234 -> "-12.34"; 0 -> "0.00"; no $ and no commas

# src/finances/config.py
export_dir: Path | None = None
@property
def effective_export_dir(self) -> Path: ...  # export_dir, else data_dir / "exports"

# src/finances/analysis/export.py
@dataclass(frozen=True)
class ExportLine:
    found: FoundTransaction   # the transaction and its flow (a part's, for a split)
    account: str
    tags: list[str]
    note: str | None

def transactions_for_export(session: Session, start: date, end: date) -> list[ExportLine]: ...

# src/finances/views/export.py
def transactions_csv(lines: list[ExportLine]) -> str: ...
def year_csv(report: YearReport) -> str: ...
def spending_csv(report: SpendingReport) -> str: ...

# src/finances/export/files.py
EXISTS = "the file is already there; add --force to replace it"
def write_csv(folder: Path, name: str, text: str, *, force: bool) -> Path: ...
```

The three CSVs (written by `csv.writer` with its default dialect, so every line ends `\r\n`; a header row first):

| File | Name | Columns | Rows |
|---|---|---|---|
| transactions | `transactions-<from>-to-<to>.csv` | `ID`, `Posted`, `Date`, `Account`, `Description`, `Merchant`, `Category`, `Group`, `Kind`, `Amount`, `Card`, `Person`, `Part`, `Tags`, `Note` | one per flow, by posted date, then id, then part |
| year | `year-<year>.csv` | `Section`, `Label`, `Spent`, `Refunds`, `Net`, `Count` | `group` lines, then `category`, then `tax`, each in 30a's order |
| spending | `spending-by-<by>-<from>-to-<to>.csv` | the grouping capitalized, `Spent`, `Refunds`, `Net`, `Count` | the report's lines in order |

`fin export` is a new Typer app, `export_app` (help `Write CSV files a spreadsheet can open.`, `no_args_is_help=True`), registered in `cli/main.py` as `export`. Each command takes `--folder PATH` (default `effective_export_dir`) and `--force`, calls `require_current_schema()` first, prints `Wrote N rows to <path>.` (N not counting the header; the path as `write_csv` returns it), and refuses through `fail(message)`:

| Command | Options |
|---|---|
| `fin export transactions` | `--from YYYY-MM-DD`, `--to YYYY-MM-DD` (both default to this year's first and last day, from `clock.today()`) |
| `fin export year` | `--year INT` (this year by default), with no `min` or `max` on the option, so `year_report`'s message reaches the person |
| `fin export spending` | `--month`, `--from`, `--to`, `--by` exactly as `fin spending` takes them |

## Requirements

### The rule and the setting

- **R1.** `decimal_text` writes the sign (`-` for money out), the dollars without separators, a point, and two digits of cents, by integer arithmetic; it is covered 100% by `tests/unit/test_money_decimal.py`, and `domain/money.py` stays critical.
- **R2.** `Settings.export_dir` (`FIN_EXPORT_DIR`) and `effective_export_dir` as designed.

### Gathering and writing

- **R3.** `transactions_for_export` refuses a start after the end (`the start date is after the end date`) and gives one `ExportLine` per flow of `search_transactions` over the range (so a split transaction gives one per part), with every transaction in the range found whatever its count, in the order of the table above. Tags and notes are loaded so that no query passes more than 500 ids at once.
- **R4.** The three CSV functions as designed, every amount through `decimal_text`: a transaction's `Amount` is its flow's amount; `Spent` is a line's purchases, `Refunds` its refunds, `Net` its spent cents (positive for money out, negative for money back); `Category` and `Group` are blank for an uncategorized flow and `Person` for an unassigned one, as the pages show them; `Card` is `mask_last4`; `Part` is the part's position or blank; `Tags` are joined by `; `; `Note` is the note or blank.
- **R5.** `write_csv` makes the folder (and its parents) when missing, refuses an existing file unless `force` (`EXISTS`), writes the text as UTF-8 with no newline translation (`newline=""`), and returns the file's path (`folder / name`).

### The commands

- **R6.** `fin export transactions` as designed.
- **R7.** `fin export year` as designed.
- **R8.** `fin export spending` as designed; its range and grouping are refused exactly as `fin spending` refuses them.
- **R9.** Apply the given diff to `tests/conftest.py`. No other earlier test changes.

## Given diff to earlier tests

```text
diff --git a/tests/conftest.py b/tests/conftest.py
index 9fbbdde..6fd1360 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -37,6 +37,7 @@ _ENV_KEYS = (
     "FIN_LOG_LEVEL",
     "FIN_BACKUP_DIR",
     "FIN_BACKUP_KEEP",
+    "FIN_EXPORT_DIR",
 )
 
 _TERMINAL_KEYS = ("FORCE_COLOR", "NO_COLOR", "TTY_COMPATIBLE", "TTY_INTERACTIVE")
```

## Given tests

17 tests in two files. Do not change them.

`tests/unit/test_money_decimal.py`

```python
import pytest

from finances.domain.money import decimal_text


@pytest.mark.parametrize(
    ("cents", "text"),
    [
        (0, "0.00"),
        (5, "0.05"),
        (-5, "-0.05"),
        (99, "0.99"),
        (-100, "-1.00"),
        (-1234, "-12.34"),
        (123456, "1234.56"),
        (100000000, "1000000.00"),
        (900719925474099301, "9007199254740993.01"),
    ],
)
def test_cents_as_plain_decimal_dollars(cents: int, text: str) -> None:
    assert decimal_text(cents) == text
```

`tests/e2e/test_cli_export.py`

```python
from datetime import date
from pathlib import Path

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_tags,
    create_account,
    set_category_by_hand,
    set_note,
    set_split,
)
from tests.support import failed_cleanly, run

TRANSACTIONS = (
    "ID,Posted,Date,Account,Description,Merchant,Category,Group,Kind,Amount,Card,Person,Part,"
    "Tags,Note\r\n"
    "1,2026-05-01,2026-05-01,Test Card,ACME COFFEE,ACME COFFEE,Coffee & Dessert,Food,spending,"
    "-12.34,,,,work,client lunch\r\n"
    "2,2026-05-03,2026-05-03,Test Card,FOOBAR GROCERY,FOOBAR GROCERY,Groceries,Food,spending,"
    "-12.00,,,1,,\r\n"
    "2,2026-05-03,2026-05-03,Test Card,FOOBAR GROCERY,FOOBAR GROCERY,Home & Garden,Home,"
    "spending,-8.00,,,2,,\r\n"
    "3,2026-05-05,2026-05-05,Test Card,ACME COFFEE,ACME COFFEE,Coffee & Dessert,Food,spending,"
    "5.00,,,,,\r\n"
)
YEAR = (
    "Section,Label,Spent,Refunds,Net,Count\r\n"
    "group,Food,24.34,5.00,19.34,3\r\n"
    "group,Home,8.00,0.00,8.00,1\r\n"
    "category,Groceries,12.00,0.00,12.00,1\r\n"
    "category,Home & Garden,8.00,0.00,8.00,1\r\n"
    "category,Coffee & Dessert,12.34,5.00,7.34,2\r\n"
    "tax,Gifts & Donations,0.00,0.00,0.00,0\r\n"
    "tax,Medical,0.00,0.00,0.00,0\r\n"
    "tax,Taxes,0.00,0.00,0.00,0\r\n"
)
SPENDING = (
    "Category,Spent,Refunds,Net,Count\r\n"
    "Groceries,12.00,0.00,12.00,1\r\n"
    "Home & Garden,8.00,0.00,8.00,1\r\n"
    "Coffee & Dessert,12.34,5.00,7.34,2\r\n"
)


@pytest.fixture
def card(tmp_settings: Settings) -> Settings:
    """May 2026 on a card: ACME COFFEE -$12.34 (1) tagged work with a note; FOOBAR GROCERY
    -$20.00 (2) split into Groceries -$12.00 and Home & Garden -$8.00; a refund of $5.00 at
    ACME COFFEE (3); and -$9.99 on 2025-12-31 (4), the year before."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [
            (date(2026, 5, 1), -1234, "ACME COFFEE"),
            (date(2026, 5, 3), -2000, "FOOBAR GROCERY"),
            (date(2026, 5, 5), 500, "ACME COFFEE"),
            (date(2025, 12, 31), -999, "ACME COFFEE"),
        ]
        for number, (day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for number in (1, 3, 4):
            set_category_by_hand(session, number, "Coffee & Dessert")
        set_split(session, 2, [(-1200, "Groceries"), (-800, "Home & Garden")])
        add_tags(session, [1], "work")
        set_note(session, 1, "client lunch")
    engine.dispose()
    return tmp_settings


def folder(settings: Settings) -> Path:
    return settings.data_dir / "exports"


def test_transactions(card: Settings) -> None:
    result = run("export", "transactions", "--from", "2026-01-01", "--to", "2026-12-31")
    written = folder(card) / "transactions-2026-01-01-to-2026-12-31.csv"
    assert (result.exit_code, result.stdout) == (0, f"Wrote 4 rows to {written}.\n")
    assert written.read_bytes().decode("utf-8") == TRANSACTIONS


def test_the_year(card: Settings) -> None:
    result = run("export", "year", "--year", "2026")
    written = folder(card) / "year-2026.csv"
    assert (result.exit_code, result.stdout) == (0, f"Wrote 8 rows to {written}.\n")
    assert written.read_bytes().decode("utf-8") == YEAR


def test_spending_for_a_month(card: Settings) -> None:
    result = run("export", "spending", "--month", "2026-05")
    written = folder(card) / "spending-by-category-2026-05-01-to-2026-05-31.csv"
    assert (result.exit_code, result.stdout) == (0, f"Wrote 3 rows to {written}.\n")
    assert written.read_bytes().decode("utf-8") == SPENDING


def test_another_folder_and_replacing(card: Settings, tmp_path: Path) -> None:
    elsewhere = tmp_path / "taxes"
    first = run("export", "year", "--year", "2026", "--folder", str(elsewhere))
    assert first.stdout == f"Wrote 8 rows to {elsewhere / 'year-2026.csv'}.\n"
    again = run("export", "year", "--year", "2026", "--folder", str(elsewhere))
    assert failed_cleanly(again, "the file is already there; add --force to replace it")
    (elsewhere / "year-2026.csv").write_text("old", encoding="utf-8")
    forced = run("export", "year", "--year", "2026", "--folder", str(elsewhere), "--force")
    assert forced.exit_code == 0
    assert (elsewhere / "year-2026.csv").read_bytes().decode("utf-8") == YEAR


def test_the_export_folder_setting(card: Settings, tmp_path: Path, monkeypatch) -> None:
    from finances.config import get_settings

    monkeypatch.setenv("FIN_EXPORT_DIR", str(tmp_path / "out"))
    get_settings.cache_clear()
    result = run("export", "year", "--year", "2026")
    assert result.stdout == f"Wrote 8 rows to {tmp_path / 'out' / 'year-2026.csv'}.\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ("transactions", "--from", "2026-12-31", "--to", "2026-01-01"),
            "the start date is after the end date",
        ),
        (("year", "--year", "0"), "year must be from 1 to 9999"),
        (
            ("spending", "--month", "2026-05", "--by", "colour"),
            "by must be one of: category, group, merchant, person, account, bank, card",
        ),
    ],
)
def test_refused(card: Settings, args: tuple[str, ...], message: str) -> None:
    assert failed_cleanly(run("export", *args), message)
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/unit/test_export_views.py`:

- `transactions_csv` of hand-made lines: a description holding a comma and a quote is quoted as `csv` quotes it; an uncategorized flow and an unassigned person give blanks; a card gives `mask_last4`'s text; two tags give `a; b`;
- `year_csv` and `spending_csv` of hand-made reports, with a line whose net is money back (`-5.00`).

`tests/integration/test_export_more.py`:

- `transactions_for_export` over a range with 1201 transactions returns 1201 lines (no search limit), and with 600 tagged ones gives every tag (the 500-id rule);
- a pending transaction is written with the kind `pending`;
- `write_csv` makes a missing folder two levels deep;
- `fin export transactions` with no dates writes this year's file, with `clock.today()` replaced;
- `fin export spending` with no options writes this month's file by category;
- a database that is not migrated gives the CLI's not-migrated message for `fin export year`.

## Rules for this phase

- Money is integer cents until `decimal_text` writes it; no `float` anywhere in the export.
- No network: the files go to a local folder, and nothing is sent.
- The CSVs hold descriptions, amounts, and notes by design; no log line or error message echoes them.
- `views/export.py` only formats what `analysis` returns; `cli/export.py` parses options, calls one function to gather, one to format, and `write_csv`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files above, 17 tests; at least N + 17 passed in all;
- `git diff --stat HEAD -- tests` lists only `tests/conftest.py`;
- `git grep -n "float(\|urllib\|socket\|http" -- src/finances/export src/finances/views/export.py src/finances/analysis/export.py src/finances/domain/money.py` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.domain.money --cov=finances.analysis.export --cov=finances.views.export --cov=finances.export --cov=finances.cli.export --cov-branch --cov-report=term-missing --cov-fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 30c: CSV export from the terminal (YYYY-MM-DD)`.
