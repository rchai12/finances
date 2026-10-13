# Phase 3d: the import commands

## Goal

Put the import service from Phase 3c behind four commands, so a person can import statements and see what was stored:

- `fin import statement PATH` imports one PDF.
- `fin import folder DIR` imports every PDF in a folder.
- `fin statements list` shows the imported statements.
- `fin transactions list` shows the stored transactions.

The commands are thin. Every rule about reading, matching, reconciling, and storing a statement already lives in `finances.ingest.service` and `finances.db.repositories`; a command calls those functions and prints what they return.

This phase and Phase 4 (the Capital One parser) do not depend on each other and can be built in either order. The tests here use the made-up bank format from `tests/conftest.py`.

## Read first

- `AGENTS.md`: "Running commands", "Privacy rules", "Architecture rules"
- `src/finances/cli/main.py`, `src/finances/cli/accounts.py`, `src/finances/cli/db.py`
- `src/finances/ingest/service.py`: `import_statement`, `import_folder`, `StatementImportResult`, `ImportStatus`
- `src/finances/db/repositories.py`: `list_statements`, `list_transactions`, `list_accounts`, `get_account_by_name`
- `src/finances/domain/money.py`: `format_cents`
- `tests/e2e/test_cli_accounts.py` and `tests/conftest.py`

## Starting state

- The previous phase is committed and `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `590` if Phase 4 has not been built and higher if it has.
- `src/finances/cli/` has `main.py`, `db.py`, and `accounts.py`. `accounts.py` checks that the database is up to date with the same six lines in each of its two commands.
- `finances.cli` and `finances.diagnostics` are at 100% line and branch coverage.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/cli/common.py` | new: `require_current_schema` |
| `src/finances/cli/importing.py` | new: the `import` command group |
| `src/finances/cli/listing.py` | new: the `statements` and `transactions` command groups |
| `src/finances/cli/main.py` | registers the three new groups |
| `src/finances/cli/accounts.py` | its two inline database checks are replaced by calls to `require_current_schema`; nothing else |
| `tests/e2e/test_cli_import.py`, `tests/e2e/test_cli_listing.py` | given, do not change |
| `docs/progress.md` | one new entry |

You may add private helpers (names starting with `_`) and module-level constants inside the three new modules. Do not create any other production module, and do not change any other production file or any existing test.

## Out of scope

- Any change under `src/finances/ingest/`, `src/finances/db/`, or `src/finances/domain/`. If a command seems to need a new repository or service function, stop and report it.
- Business rules in a command: no validating, matching, sorting, filtering, or de-duplicating in the CLI beyond passing options through.
- An option that imports a statement which does not reconcile, an option to delete or re-import, and any confirmation prompt.
- Colors, styles, a summary line, a progress bar, or paging.
- A date or time column for when a statement was imported.
- New dependencies.

## Dependencies

None new.

## Design

### `src/finances/cli/common.py`

```python
def require_current_schema() -> None
```

### `src/finances/cli/importing.py`

A Typer app named `app`, registered in `main.py` under the name `import`, with help text `Import statements.` and `no_args_is_help=True`. It has two commands:

| Command | Arguments and options |
|---|---|
| `statement` | `PATH`, a required argument: an existing file, not a folder. `--account NAME`, optional. `--dry-run`, a flag. |
| `folder` | `DIR`, a required argument: an existing folder, not a file. `--dry-run`, a flag. |

Typer checks that the path exists and is of the right kind (`exists=True`, `file_okay`, `dir_okay`), and exits with code 2 when it is not.

### `src/finances/cli/listing.py`

Two Typer apps, `statements_app` and `transactions_app`, registered in `main.py` under the names `statements` and `transactions`, with help texts `Show imported statements.` and `Show transactions.`, both with `no_args_is_help=True`. Each has one command, named `list`:

| Command | Options |
|---|---|
| `statements list` | `--account NAME`, optional |
| `transactions list` | `--account NAME`, optional. `--from DATE` and `--to DATE`, optional, in the form `YYYY-MM-DD` and no other. `--limit N`, an integer of at least 1, default `50`. |

Typer rejects a date in another form and a limit below 1, with exit code 2.

### Tables

Tables are Rich tables with default settings, printed with a module-level `Console()`, as `accounts list` does. Every cell is text.

## Requirements

### Part 1: the shared database check

- **R1.** `require_current_schema` compares `current_revision()` with `head_revision()`. When they differ it prints `Error: database is not up to date (run: fin db upgrade)` to standard error and exits with code 1. When they are equal it does nothing.
- **R2.** All four new commands call it before anything else, and so do `accounts add` and `accounts list`, whose behavior does not change. No command module compares revisions itself.

### Part 2: `fin import statement`

- **R3.** It reads the file's bytes and calls `import_statement` inside `session_scope(get_engine())`, passing the path as `filename`, the bytes as `content`, the `--account` value as `account_name`, and the `--dry-run` flag.
- **R4.** For status `IMPORTED` it prints these eight lines to standard output and exits with code 0. The values come from the result.

  ```
  File: january.pdf
  Parser: fake_bank
  Account: Test Card
  Period: 2026-01-01 to 2026-01-31
  Lines: 4
  Inserted: 4
  Duplicates: 0
  Status: imported
  ```

- **R5.** For status `DRY_RUN` it prints the same eight lines, with the last one `Status: dry run, nothing written`.
- **R6.** For status `ALREADY_IMPORTED` it prints two lines, `File: january.pdf` and `Status: already imported`, and exits with code 0.
- **R7.** For status `FAILED` it prints `Error: ` followed by the result's message to standard error, prints nothing to standard output, and exits with code 1.
- **R8.** `File:` shows the result's `filename`, which is the file's own name without its folders.

### Part 3: `fin import folder`

- **R9.** It calls `import_folder(get_engine(), DIR, dry_run=...)`. When that returns no results, it prints `No PDF files.` and exits with code 0.
- **R10.** Otherwise it prints one table with these columns, and one row per result in the order returned:

  | Column | Cell |
  |---|---|
  | `File` | `filename` |
  | `Parser` | `parser_name`, or empty when it is `None` |
  | `Account` | `account_name`, or empty when it is `None` |
  | `Period` | `2026-01-01 to 2026-01-31`, or empty when the result has no period |
  | `Lines` | `lines_parsed` |
  | `Inserted` | `inserted` |
  | `Duplicates` | `duplicates` |
  | `Status` | `imported`, `dry run, nothing written`, `already imported`, or `failed` |

- **R11.** After the table, for each failed result in order, it prints one line to standard error: `Error: `, the file name, `: `, and the result's message. The message is not put in the table, where a long one would be wrapped.
- **R12.** It exits with code 1 when at least one result failed, and with code 0 otherwise.

### Part 4: `fin statements list`

- **R13.** With `--account`, the name is looked up with `get_account_by_name`. An unknown name prints `Error: account not found` to standard error and exits with code 1. This rule is the same for `transactions list`.
- **R14.** It gets the statements from `list_statements`, for that account or for all. When there are none it prints `No statements.` and exits with code 0.
- **R15.** Otherwise it prints one table with these columns, and one row per statement in the order returned:

  | Column | Cell |
  |---|---|
  | `Account` | the name of the statement's account, whether or not that account is still active |
  | `File` | `source_filename` |
  | `Parser` | `parser_name` |
  | `Period` | `2026-01-01 to 2026-01-31` |
  | `Opening` | `format_cents(opening_balance_cents)` |
  | `Closing` | `format_cents(closing_balance_cents)` |
  | `Lines` | `lines_parsed` |
  | `New` | `rows_inserted` |

### Part 5: `fin transactions list`

- **R16.** It gets the transactions from `list_transactions`, passing the account (R13), the `--from` and `--to` dates as `start` and `end`, and `--limit`. When there are none it prints `No transactions.` and exits with code 0.
- **R17.** Otherwise it prints one table with these columns, and one row per transaction in the order returned:

  | Column | Cell |
  |---|---|
  | `Date` | `posted_date` as `2026-01-05` |
  | `Account` | the name of the transaction's account, whether or not that account is still active |
  | `Description` | `description` |
  | `Amount` | `format_cents(amount_cents)` |
  | `Card` | two bullet characters (`"\u2022"`) followed by `card_last4`, or empty when it is `None` |
  | `Section` | `section`, or empty when it is `None` |

### All commands

- **R18.** `main.py` registers the three groups, so `fin --help` lists `import`, `statements`, and `transactions` beside `db` and `accounts`.
- **R19.** Nothing but the texts above is printed. A failure never shows a traceback: the command exits through `typer.Exit`.

## Given tests

Create these two files exactly as shown and do not change them. They define the exact output of every command. If one of their tests fails, the command is wrong.

`tests/e2e/test_cli_import.py`:

```python
from pathlib import Path

import pytest
from sqlalchemy import func, select
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import StatementRow, TransactionRow

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
HEADINGS = ["File", "Parser", "Account", "Period", "Lines", "Inserted", "Duplicates", "Status"]
IMPORTED = (
    "File: january.pdf\n"
    "Parser: fake_bank\n"
    "Account: Test Card\n"
    "Period: 2026-01-01 to 2026-01-31\n"
    "Lines: 4\n"
    "Inserted: 4\n"
    "Duplicates: 0\n"
)
HINT = (
    'no account ends in 1111; add one with: fin accounts add --name "NAME" '
    '--institution "Fake Bank" --type credit_card --last4 1111'
)


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    """The cells of one row of a Rich table."""
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    """Every row of a Rich table, heading first."""
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def stored(settings: Settings) -> tuple[int, int]:
    engine = get_engine(settings.effective_database_url)
    with session_scope(engine) as session:
        found = (
            session.scalar(select(func.count()).select_from(StatementRow)),
            session.scalar(select(func.count()).select_from(TransactionRow)),
        )
    engine.dispose()
    return found


def failed_cleanly(result, message: str) -> bool:
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


@pytest.fixture
def migrated(tmp_settings: Settings, fake_bank) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    return tmp_settings


@pytest.fixture
def with_card(migrated: Settings) -> Settings:
    args = ["--name", "Test Card", "--institution", "Fake Bank", "--type", "credit_card"]
    assert run("accounts", "add", *args, "--last4", "1111").exit_code == 0
    return migrated


@pytest.fixture
def january(tmp_path: Path, fake_statement_pdf) -> Path:
    path = tmp_path / "inbox" / "january.pdf"
    path.parent.mkdir()
    path.write_bytes(fake_statement_pdf())
    return path


def test_import_statement_stores_it_and_reports(with_card: Settings, january: Path) -> None:
    result = run("import", "statement", january)
    assert result.exit_code == 0
    assert result.stdout == IMPORTED + "Status: imported\n"
    assert result.stderr == ""
    assert stored(with_card) == (1, 4)


def test_import_statement_twice_says_already_imported(with_card: Settings, january: Path) -> None:
    run("import", "statement", january)
    result = run("import", "statement", january)
    assert result.exit_code == 0
    assert result.stdout == "File: january.pdf\nStatus: already imported\n"
    assert stored(with_card) == (1, 4)


def test_import_statement_dry_run_stores_nothing(with_card: Settings, january: Path) -> None:
    result = run("import", "statement", january, "--dry-run")
    assert result.exit_code == 0
    assert result.stdout == IMPORTED + "Status: dry run, nothing written\n"
    assert stored(with_card) == (0, 0)


def test_import_statement_counts_duplicates(
    with_card: Settings, january: Path, tmp_path: Path, fake_statement_pdf
) -> None:
    run("import", "statement", january)
    rows = (
        "2026-01-05|2026-01-04|purchases|-4.50|2222|-|ACME COFFEE #12",
        "2026-02-03|-|purchases|-10.00|-|-|FOOBAR BOOKS",
    )
    later = tmp_path / "february.pdf"
    later.write_bytes(
        fake_statement_pdf(start="2026-02-01", end="2026-02-28", closing="-114.50", rows=rows)
    )
    result = run("import", "statement", later)
    assert result.stdout == (
        "File: february.pdf\n"
        "Parser: fake_bank\n"
        "Account: Test Card\n"
        "Period: 2026-02-01 to 2026-02-28\n"
        "Lines: 2\n"
        "Inserted: 1\n"
        "Duplicates: 1\n"
        "Status: imported\n"
    )
    assert stored(with_card) == (2, 5)


def test_import_statement_into_a_named_account(migrated: Settings, january: Path) -> None:
    for name in ("First Card", "Second Card"):
        args = ["--name", name, "--institution", "Fake Bank", "--type", "credit_card"]
        run("accounts", "add", *args, "--last4", "1111")
    refused = run("import", "statement", january)
    message = "more than one account ends in these digits; name the account"
    assert failed_cleanly(refused, message)
    result = run("import", "statement", january, "--account", "second card")
    assert result.exit_code == 0
    assert "Account: Second Card\n" in result.stdout


@pytest.mark.parametrize(
    ("changes", "options", "message"),
    [
        ({"last4": "9999"}, [], HINT.replace("1111", "9999")),
        ({}, ["--account", "Nobody"], "account not found"),
        ({"closing": "-85.00"}, [], "statement does not reconcile: off by -1 cents"),
        (
            {"totals": ("purchases -1.00", "fees 0.00")},
            [],
            "statement does not reconcile: off by 0 cents; section totals differ: purchases",
        ),
    ],
)
def test_import_statement_reports_a_failure(
    with_card: Settings, tmp_path: Path, fake_statement_pdf, changes, options, message
) -> None:
    path = tmp_path / "bad.pdf"
    path.write_bytes(fake_statement_pdf(**changes))
    result = run("import", "statement", path, *options)
    assert failed_cleanly(result, message)
    assert stored(with_card) == (0, 0)


@pytest.mark.parametrize(
    ("content", "message"),
    [(b"not a pdf", "could not read PDF"), (None, "unrecognized statement format")],
)
def test_import_statement_reports_an_unusable_file(
    with_card: Settings, tmp_path: Path, make_pdf, content, message
) -> None:
    path = tmp_path / "odd.pdf"
    path.write_bytes(content or make_pdf([["SOME OTHER DOCUMENT"]]))
    assert failed_cleanly(run("import", "statement", path), message)


def test_import_statement_needs_an_existing_file(with_card: Settings, tmp_path: Path) -> None:
    assert run("import", "statement", tmp_path / "missing.pdf").exit_code == 2
    assert run("import", "statement", tmp_path).exit_code == 2
    assert run("import", "statement").exit_code == 2


def test_import_commands_need_a_migrated_database(
    tmp_settings: Settings, january: Path, fake_bank
) -> None:
    for args in (["statement", january], ["folder", january.parent]):
        result = run("import", *args)
        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        assert result.stderr == NOT_MIGRATED
        assert result.stdout == ""


def test_import_folder_shows_one_row_per_pdf(
    with_card: Settings, january: Path, fake_statement_pdf, make_pdf
) -> None:
    inbox = january.parent
    (inbox / "broken.pdf").write_bytes(b"not a pdf")
    (inbox / "copy of january.PDF").write_bytes(fake_statement_pdf(opening="-100.00 "))
    (inbox / "notes.txt").write_text("not a statement")
    result = run("import", "folder", inbox)
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert table_rows(result.stdout) == [
        HEADINGS,
        ["broken.pdf", "", "", "", "0", "0", "0", "failed"],
        [
            "copy of january.PDF",
            "fake_bank",
            "Test Card",
            "2026-01-01 to 2026-01-31",
            "4",
            "4",
            "0",
            "imported",
        ],
        [
            "january.pdf",
            "fake_bank",
            "Test Card",
            "2026-01-01 to 2026-01-31",
            "4",
            "0",
            "4",
            "imported",
        ],
    ]
    assert result.stderr == "Error: broken.pdf: could not read PDF\n"
    assert stored(with_card) == (2, 4)


def test_import_folder_succeeds_when_nothing_fails(with_card: Settings, january: Path) -> None:
    first = run("import", "folder", january.parent)
    assert first.exit_code == 0
    assert first.stderr == ""
    second = run("import", "folder", january.parent)
    assert second.exit_code == 0
    assert table_rows(second.stdout)[1] == [
        "january.pdf",
        "",
        "",
        "",
        "0",
        "0",
        "0",
        "already imported",
    ]


def test_import_folder_dry_run_stores_nothing(with_card: Settings, january: Path) -> None:
    result = run("import", "folder", january.parent, "--dry-run")
    assert result.exit_code == 0
    assert table_rows(result.stdout)[1][-1] == "dry run, nothing written"
    assert stored(with_card) == (0, 0)


def test_import_folder_reports_every_failure(
    with_card: Settings, tmp_path: Path, fake_statement_pdf
) -> None:
    inbox = tmp_path / "bad"
    inbox.mkdir()
    (inbox / "a.pdf").write_bytes(fake_statement_pdf(last4="9999"))
    (inbox / "b.pdf").write_bytes(fake_statement_pdf(closing="-80.00"))
    result = run("import", "folder", inbox)
    assert result.exit_code == 1
    assert result.stderr == (
        f"Error: a.pdf: {HINT.replace('1111', '9999')}\n"
        "Error: b.pdf: statement does not reconcile: off by 499 cents\n"
    )
    assert [row[-1] for row in table_rows(result.stdout)[1:]] == ["failed", "failed"]
    assert table_rows(result.stdout)[2][:4] == [
        "b.pdf",
        "fake_bank",
        "Test Card",
        "2026-01-01 to 2026-01-31",
    ]


def test_import_folder_with_no_pdfs(with_card: Settings, tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    (tmp_path / "empty" / "notes.txt").write_text("nothing")
    result = run("import", "folder", tmp_path / "empty")
    assert result.exit_code == 0
    assert result.stdout == "No PDF files.\n"


def test_import_folder_needs_an_existing_folder(with_card: Settings, january: Path) -> None:
    assert run("import", "folder", january.parent / "missing").exit_code == 2
    assert run("import", "folder", january).exit_code == 2
```

`tests/e2e/test_cli_listing.py`:

```python
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, TransactionRow

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
STATEMENT_HEADINGS = ["Account", "File", "Parser", "Period", "Opening", "Closing", "Lines", "New"]
TRANSACTION_HEADINGS = ["Date", "Account", "Description", "Amount", "Card", "Section"]
BULLETS = "••"
CARD_STATEMENT = [
    "Test Card",
    "january.pdf",
    "fake_bank",
    "2026-01-01 to 2026-01-31",
    "-$100.00",
    "-$84.99",
    "4",
    "4",
]
CHECKING_STATEMENT = [
    "Test Checking",
    "checking.pdf",
    "fake_bank",
    "2026-02-01 to 2026-02-28",
    "$1,000.00",
    "$900.00",
    "1",
    "1",
]
RENT = ["2026-02-10", "Test Checking", "ACME RENT", "-$100.00", "", "withdrawals"]
PAYMENT = ["2026-01-20", "Test Card", "PAYMENT THANK YOU", "$50.00", "", "payments_credits"]
GROCERY = ["2026-01-06", "Test Card", "FOOBAR GROCERY", "-$25.99", BULLETS + "2222", "purchases"]
COFFEE = ["2026-01-05", "Test Card", "ACME COFFEE #12", "-$4.50", BULLETS + "2222", "purchases"]


def run(*args: object):
    return runner.invoke(app, [str(arg) for arg in args])


def cells(line: str) -> list[str]:
    """The cells of one row of a Rich table."""
    return [cell.strip() for cell in line.replace("┃", "│").split("│")[1:-1]]


def table_rows(output: str) -> list[list[str]]:
    """Every row of a Rich table, heading first."""
    return [cells(line) for line in output.splitlines() if line.startswith(("│", "┃"))]


def failed_cleanly(result, message: str) -> bool:
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


@pytest.fixture
def migrated(tmp_settings: Settings, fake_bank) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    card = ["--name", "Test Card", "--institution", "Fake Bank", "--type", "credit_card"]
    checking = ["--name", "Test Checking", "--institution", "Fake Bank", "--type", "checking"]
    assert run("accounts", "add", *card, "--last4", "1111").exit_code == 0
    assert run("accounts", "add", *checking, "--last4", "2222").exit_code == 0
    return tmp_settings


@pytest.fixture
def imported(migrated: Settings, tmp_path: Path, fake_statement_pdf) -> Settings:
    january = tmp_path / "january.pdf"
    january.write_bytes(fake_statement_pdf())
    checking = tmp_path / "checking.pdf"
    checking.write_bytes(
        fake_statement_pdf(
            last4="2222",
            account_type="checking",
            start="2026-02-01",
            end="2026-02-28",
            opening="1000.00",
            closing="900.00",
            rows=("2026-02-10|-|withdrawals|-100.00|-|-|ACME RENT",),
        )
    )
    assert run("import", "statement", january).exit_code == 0
    assert run("import", "statement", checking).exit_code == 0
    return migrated


def test_statements_list_newest_period_first(imported: Settings) -> None:
    result = run("statements", "list")
    assert result.exit_code == 0
    assert result.stderr == ""
    assert table_rows(result.stdout) == [STATEMENT_HEADINGS, CHECKING_STATEMENT, CARD_STATEMENT]


def test_statements_list_for_one_account(imported: Settings) -> None:
    result = run("statements", "list", "--account", " test card ")
    assert table_rows(result.stdout) == [STATEMENT_HEADINGS, CARD_STATEMENT]


def test_statements_list_when_there_are_none(migrated: Settings) -> None:
    result = run("statements", "list")
    assert result.exit_code == 0
    assert result.stdout == "No statements.\n"
    assert run("statements", "list", "--account", "Test Card").stdout == "No statements.\n"


def test_transactions_list_newest_first(imported: Settings) -> None:
    result = run("transactions", "list")
    assert result.exit_code == 0
    assert result.stderr == ""
    assert table_rows(result.stdout) == [
        TRANSACTION_HEADINGS,
        RENT,
        PAYMENT,
        GROCERY,
        COFFEE,
        COFFEE,
    ]


def test_transactions_list_for_one_account(imported: Settings) -> None:
    result = run("transactions", "list", "--account", "TEST CHECKING")
    assert table_rows(result.stdout) == [TRANSACTION_HEADINGS, RENT]


def test_transactions_list_between_two_dates(imported: Settings) -> None:
    result = run("transactions", "list", "--from", "2026-01-06", "--to", "2026-01-20")
    assert table_rows(result.stdout) == [TRANSACTION_HEADINGS, PAYMENT, GROCERY]


def test_transactions_list_from_or_to_alone(imported: Settings) -> None:
    after = run("transactions", "list", "--from", "2026-01-20")
    assert table_rows(after.stdout) == [TRANSACTION_HEADINGS, RENT, PAYMENT]
    before = run("transactions", "list", "--to", "2026-01-05")
    assert table_rows(before.stdout) == [TRANSACTION_HEADINGS, COFFEE, COFFEE]


def test_transactions_list_limit(imported: Settings) -> None:
    result = run("transactions", "list", "--limit", "2")
    assert table_rows(result.stdout) == [TRANSACTION_HEADINGS, RENT, PAYMENT]


def test_transactions_list_shows_fifty_by_default(
    migrated: Settings, tmp_path: Path, fake_statement_pdf
) -> None:
    rows = tuple(f"2026-01-{1 + n % 28:02d}|-|purchases|-1.00|-|-|ACME ITEM {n}" for n in range(60))
    path = tmp_path / "many.pdf"
    path.write_bytes(fake_statement_pdf(closing="-160.00", rows=rows))
    assert run("import", "statement", path).exit_code == 0
    assert len(table_rows(run("transactions", "list").stdout)) == 51
    assert len(table_rows(run("transactions", "list", "--limit", "60").stdout)) == 61


def test_transactions_list_when_there_are_none(imported: Settings) -> None:
    result = run("transactions", "list", "--from", "2027-01-01")
    assert result.exit_code == 0
    assert result.stdout == "No transactions.\n"


def test_lists_still_name_an_account_that_was_closed(imported: Settings) -> None:
    engine = get_engine(imported.effective_database_url)
    with session_scope(engine) as session:
        session.scalars(
            select(AccountRow).where(AccountRow.name == "Test Card")
        ).one().is_active = False
    engine.dispose()
    assert table_rows(run("statements", "list").stdout)[2] == CARD_STATEMENT
    assert table_rows(run("transactions", "list").stdout)[2] == PAYMENT


def test_transactions_list_leaves_a_missing_card_and_section_empty(imported: Settings) -> None:
    engine = get_engine(imported.effective_database_url)
    with session_scope(engine) as session:
        session.add(
            TransactionRow(
                account_id=2,
                posted_date=date(2026, 3, 1),
                amount_cents=123456,
                description="ACME PAYROLL",
                source="aggregator",
                fingerprint="f" * 64,
            )
        )
    engine.dispose()
    rows = table_rows(run("transactions", "list", "--limit", "1").stdout)
    assert rows[1] == ["2026-03-01", "Test Checking", "ACME PAYROLL", "$1,234.56", "", ""]


@pytest.mark.parametrize("command", ["statements", "transactions"])
def test_an_unknown_account_is_an_error(imported: Settings, command: str) -> None:
    assert failed_cleanly(run(command, "list", "--account", "Nobody"), "account not found")


@pytest.mark.parametrize(
    "options",
    [
        ["--limit", "0"],
        ["--limit", "-3"],
        ["--limit", "ten"],
        ["--from", "01/06/2026"],
        ["--to", "soon"],
    ],
)
def test_transactions_list_rejects_bad_options(imported: Settings, options: list[str]) -> None:
    assert run("transactions", "list", *options).exit_code == 2


@pytest.mark.parametrize("command", ["statements", "transactions"])
def test_list_commands_need_a_migrated_database(tmp_settings: Settings, command: str) -> None:
    result = run(command, "list")
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.stderr == NOT_MIGRATED
    assert result.stdout == ""


def test_the_program_lists_the_new_command_groups() -> None:
    output = run("--help").stdout
    for name in ("import", "statements", "transactions"):
        assert name in output
```

## Tests to write

None are required. The given tests reach every requirement, and with a straightforward implementation they reach every line. If the coverage command in "Acceptance" reports a missing line, either that line is a private helper branch that needs a test in a new file `tests/e2e/test_cli_import_more.py`, or it is code no requirement asks for and should be removed.

## Rules for this phase

- **Thin commands.** A command calls service and repository functions and prints. `git grep` in "Acceptance" checks that the CLI does not query tables, reconcile, or fingerprint anything itself.
- **Standard output and standard error.** Results go to standard output with `typer.echo` or the console. Every `Error:` line goes to standard error with `typer.echo(..., err=True)`.
- **Exit codes.** `0` for success, including "already imported" and "nothing to show". `1` for a failure the command reports. `2` is Typer's own, for bad arguments.
- **Privacy.** `transactions list` and `statements list` print descriptions, amounts, and balances to the terminal because the user asked for them. Nothing is logged, and no command writes them anywhere else.
- **Money is shown with `format_cents`** and never computed in the CLI.
- **No shipped behavior changes.** The earlier commands print exactly what they printed before, and every existing test passes unchanged.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, at least N + 41 passed, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/e2e/test_cli_import.py tests/e2e/test_cli_listing.py --no-cov` | exactly `41 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| the search below | no output |
| `.venv/bin/fin --help` | lists `doctor`, `db`, `accounts`, `import`, `statements`, and `transactions` |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest tests/e2e tests/unit/test_diagnostics.py -o addopts="" --import-mode=importlib --cov=finances.cli --cov=finances.diagnostics --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -E "current_revision|head_revision|select\(|Row\b|reconcile|fingerprint|extract_pages|detect_parser|logging" -- src/finances/cli/accounts.py src/finances/cli/importing.py src/finances/cli/listing.py`

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 3d: the import commands (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. Under "Deviations", list your design choices (private helpers, constants) and anything you did that the spec did not ask for, or `None`.

In your final message, give the output line of each acceptance command.
