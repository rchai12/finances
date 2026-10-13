# Phase 2m: the database and account commands

## Goal

Give the user the commands that finish Phase 2: `fin db upgrade`, `fin accounts add`, `fin accounts list`, and a new line in `fin doctor` that says whether the database is up to date. The tests are given. **You write four function bodies.** The work is to do the 32 steps in order.

This is two phases joined into one, so it is the longest so far: four Code steps in three source files. The method is the same as before. Work through it one step at a time and do not look ahead.

## Read first

- `AGENTS.md`, sections "Running commands", "Privacy rules", and "Architecture rules"
- `src/finances/cli/main.py` (how `doctor` prints a table and exits with code 1)
- `src/finances/db/migrate.py`, `src/finances/db/repositories.py`, `src/finances/db/engine.py` (the functions the commands call)

## Starting state

- Phase 2l is done and committed. `git status --short` prints nothing.
- `.venv/bin/python -m pytest` ends with `282 passed`.
- These commands are written for macOS. On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python`.

## Files

| Path | Action |
|---|---|
| `src/finances/cli/db.py` | create from the block in step 1; you write the body of `upgrade` |
| `src/finances/cli/accounts.py` | create from the block in step 2; you write the bodies of `add` and `list_command` |
| `src/finances/cli/main.py` | replace whole content with the block in step 3 (given in full) |
| `src/finances/diagnostics.py` | replace whole content with the block in step 4; you write the body of `_database_schema` |
| `tests/unit/test_diagnostics.py` | replace whole content with the block in step 5 |
| `tests/e2e/test_cli.py` | replace whole content with the block in step 6 |
| `tests/e2e/test_cli_accounts.py` | create from the block in step 7 |
| `docs/progress.md` | add one entry at the end |

Do not create or modify any other file.

## What to build

Every requirement below is checked by at least one given test. If the tests pass and the coverage step passes, you are done: do not add checks that no requirement asks for.

### Part 1: `_database_schema` in `diagnostics.py`

```python
def _database_schema(settings: Settings) -> Check
```

A `Check` is a tuple `(name, ok, detail)`. The name is always `"Database schema"`. The function compares `current_revision(settings.effective_database_url)` with `head_revision()`.

- **R1.** When the two are equal, it returns `("Database schema", True, "0001 OK")`, with the revision in place of `0001`.
- **R2.** When they differ, it returns `("Database schema", False, "0001 -> 0002 FAIL (run: fin db upgrade)")`, with the current revision first and the newest second. When the database has no revision, the word `none` stands in for the current one: `"none -> 0001 FAIL (run: fin db upgrade)"`.
- **R3.** When `current_revision` raises `ValueError` (the database is not SQLite), it returns `("Database schema", False, "unsupported database FAIL")`.
- **R4.** When `current_revision` raises `OSError` or `SQLAlchemyError` (the folder cannot be created, or the file is not a database), it returns `("Database schema", False, "cannot open database FAIL")`. `fin doctor` must report a broken setup, not crash on it.

### Part 2: `upgrade` in `cli/db.py` (the command `fin db upgrade`)

- **R5.** It calls `upgrade_to_head()` and prints `Database is at revision 0001`, with the revision that call returned.
- **R6.** When `upgrade_to_head()` raises `ValueError`, it prints `Error: ` followed by the error's message to standard error and exits with code 1.

### Part 3: `add` in `cli/accounts.py` (the command `fin accounts add`)

- **R7.** First it checks the database: when `current_revision()` is not equal to `head_revision()`, it prints `Error: database is not up to date (run: fin db upgrade)` to standard error and exits with code 1.
- **R8.** Otherwise it calls `create_account` inside a `session_scope` and prints `Added account "Test Checking" (id 1)`, with the name and id of the account that was returned.
- **R9.** When `create_account` raises `AccountExistsError` or `ValueError`, it prints `Error: ` followed by the error's message to standard error and exits with code 1. Nothing is printed to standard output.

### Part 4: `list_command` in `cli/accounts.py` (the command `fin accounts list`)

- **R10.** It makes the same database check as R7, with the same message and exit code.
- **R11.** It gets the accounts from `list_accounts`, passing `include_inactive=show_all`. When there are none, it prints `No accounts.` and nothing else.
- **R12.** Otherwise it prints a table with the columns `Name`, `Institution`, `Type`, `Last 4`, `Active`, one row per account in the order `list_accounts` returned them. `Type` is the text value such as `credit_card`. `Last 4` is two bullet characters followed by the digits, such as `••0042`, or empty when the account has none. `Active` is `yes` or `no`.

### Facts you will need

These are how the libraries work, not a recipe.

- `typer.echo("text")` prints to standard output. `typer.echo("text", err=True)` prints to standard error.
- `raise typer.Exit(code=1)` ends the command with exit code 1 and no traceback. Inside an `except` block write `raise typer.Exit(code=1) from None`.
- `str(error)` is an exception's message.
- `get_engine()` with no argument opens the configured database. `with session_scope(engine) as session:` gives a session and commits at the end. Values you need after the `with` block (an `Account`, a list of them) can be kept in a variable: they are plain data.
- A table is built as in `doctor`: `table = Table()`, `table.add_column("Heading")`, `table.add_row("a", "b", ...)` with one text value per column, then `console.print(table)`. `accounts.py` already has its own `console`.
- The bullet character is `"\u2022"`.
- `account.type.value` is the text of an `AccountType`.

You may add a private helper function (a name starting with `_`) when two commands need the same lines.

## Rules

- Do not change the test files. If a test fails, the source file is wrong.
- Do not change the given parts of the source files: the imports of `main.py`, the `app` and `console` lines, the `def` lines with their parameters, and the docstrings.
- The commands contain no business rules. They call the functions from earlier phases and print the result. Do not validate names, digits, or types in the command: `create_account` already does.
- Do not print or log an account's digits anywhere except the `Last 4` column.
- Do not change anything under `src/finances/db/` or `src/finances/domain/`.
- Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.

## How to work

- Each step is **one action**: **Write** (use the block given), **Code** (write code yourself), or **Run** (one command).
- Do all 32 steps, in order. Do not skip a Run step, and do not merge steps.
- After each Run step, compare the output with "Expect". If it differs, use the table under "If a Run step prints something else".
- Type every command exactly as written, starting with `.venv/bin/python`. Do not shorten it to `python`, `python3`, `pip`, `ruff`, or `pytest`. Step 31 is the one command that starts with `.venv/bin/fin`.
- Do not activate the virtual environment and do not create one. `.venv/` already exists.

## Steps

### Step 1: Write

Create `src/finances/cli/db.py` with exactly this content:

```python
"""The `fin db` commands."""

import typer

from finances.db.migrate import upgrade_to_head

app = typer.Typer(help="Manage the database schema.", no_args_is_help=True)


@app.command()
def upgrade() -> None:
    """Apply every pending migration."""
    raise NotImplementedError
```

### Step 2: Write

Create `src/finances/cli/accounts.py` with exactly this content:

```python
"""The `fin accounts` commands."""

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from finances.db.engine import get_engine, session_scope
from finances.db.migrate import current_revision, head_revision
from finances.db.repositories import AccountExistsError, create_account, list_accounts
from finances.domain.models import AccountType

app = typer.Typer(help="Manage accounts.", no_args_is_help=True)
console = Console()


@app.command()
def add(
    name: Annotated[str, typer.Option("--name", help="Your label for the account.")],
    institution: Annotated[str, typer.Option("--institution", help="The bank or card issuer.")],
    account_type: Annotated[AccountType, typer.Option("--type", help="The kind of account.")],
    currency: Annotated[str, typer.Option("--currency", help="Three-letter currency.")] = "USD",
    last4: Annotated[
        str | None, typer.Option("--last4", help="Last four digits of the account number.")
    ] = None,
) -> None:
    """Add an account."""
    raise NotImplementedError


@app.command("list")
def list_command(
    show_all: Annotated[bool, typer.Option("--all", help="Include inactive accounts.")] = False,
) -> None:
    """List the accounts."""
    raise NotImplementedError
```

### Step 3: Write

Replace the whole content of `src/finances/cli/main.py` with exactly this. It registers the two new command groups and stops Alembic from writing progress lines to the screen. You write no code in this file.

```python
import logging
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from finances import __version__
from finances.cli.accounts import app as accounts_app
from finances.cli.db import app as db_app
from finances.config import get_settings
from finances.diagnostics import run_checks
from finances.log import setup_logging

app = typer.Typer(add_completion=False)
app.add_typer(db_app, name="db")
app.add_typer(accounts_app, name="accounts")
console = Console()


@app.callback(invoke_without_command=True)
def main(
    version: Annotated[
        bool,
        typer.Option("--version", help="Show the version and exit."),
    ] = False,
) -> None:
    setup_logging(get_settings().log_level)
    logging.getLogger("alembic").setLevel(logging.WARNING)
    if version:
        typer.echo(f"finances {__version__}")
        raise typer.Exit()


@app.command()
def doctor() -> None:
    checks = run_checks(get_settings())
    table = Table()
    table.add_column("Check")
    table.add_column("Result")
    for name, _ok, detail in checks:
        table.add_row(name, detail)
    console.print(table)
    if any(not ok for _name, ok, _detail in checks):
        raise typer.Exit(code=1)
```

### Step 4: Write

Replace the whole content of `src/finances/diagnostics.py` with exactly this. Everything except the last function is finished.

```python
import sys

from sqlalchemy.exc import SQLAlchemyError

from finances.config import Settings, mask_url
from finances.db.migrate import current_revision, head_revision

Check = tuple[str, bool, str]


def run_checks(settings: Settings) -> list[Check]:
    return [
        _python_version(),
        _environment(settings),
        _data_dir(settings),
        _database_url(settings),
        _database_schema(settings),
    ]


def _python_version() -> Check:
    version = sys.version_info
    detail = f"{version.major}.{version.minor}.{version.micro}"
    ok = version >= (3, 11)
    if not ok:
        detail = f"{detail} FAIL"
    return ("Python version", ok, detail)


def _environment(settings: Settings) -> Check:
    return ("Environment", True, settings.environment)


def _data_dir(settings: Settings) -> Check:
    path = settings.data_dir.resolve()
    probe = path / ".fin_write_probe"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError:
        return ("Data dir", False, f"{path} FAIL")
    return ("Data dir", True, f"{path} OK")


def _database_url(settings: Settings) -> Check:
    return ("Database URL", True, mask_url(settings.effective_database_url))


def _database_schema(settings: Settings) -> Check:
    """Say whether the database is at the newest migration."""
    raise NotImplementedError
```

### Step 5: Write

Replace the whole content of `tests/unit/test_diagnostics.py` with exactly this:

```python
import collections
import types
from pathlib import Path

import pytest
from sqlalchemy import text

import finances.diagnostics
from finances.config import Settings
from finances.db.engine import get_engine
from finances.db.migrate import upgrade_to_head
from finances.diagnostics import run_checks

Version = collections.namedtuple("Version", "major minor micro")


def test_python_version_ok(tmp_settings: Settings) -> None:
    checks = run_checks(tmp_settings)
    assert checks[0][0] == "Python version"
    assert checks[0][1] is True
    assert "FAIL" not in checks[0][2]


def test_python_version_too_old(monkeypatch: pytest.MonkeyPatch, tmp_settings: Settings) -> None:
    fake_sys = types.SimpleNamespace(version_info=Version(3, 10, 0))
    monkeypatch.setattr(finances.diagnostics, "sys", fake_sys)
    checks = run_checks(tmp_settings)
    assert checks[0] == ("Python version", False, "3.10.0 FAIL")


def test_data_dir_ok(tmp_settings: Settings) -> None:
    checks = run_checks(tmp_settings)
    assert checks[2][0] == "Data dir"
    assert checks[2][1] is True
    assert checks[2][2].endswith(" OK")
    assert tmp_settings.data_dir.is_dir()
    assert not (tmp_settings.data_dir / ".fin_write_probe").exists()


def test_data_dir_unwritable(tmp_settings: Settings, tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    checks = run_checks(Settings(data_dir=blocker / "data"))
    assert checks[2][1] is False
    assert checks[2][2].endswith(" FAIL")
    assert checks[4] == ("Database schema", False, "cannot open database FAIL")


def test_database_url_is_masked(tmp_settings: Settings, tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, database_url="postgresql://user:secret@host/db")
    checks = run_checks(settings)
    assert checks[3][0] == "Database URL"
    assert "secret" not in checks[3][2]
    assert "***" in checks[3][2]


def test_there_are_five_checks_in_order(tmp_settings: Settings) -> None:
    names = [name for name, _ok, _detail in run_checks(tmp_settings)]
    assert names == [
        "Python version",
        "Environment",
        "Data dir",
        "Database URL",
        "Database schema",
    ]


def test_database_schema_fails_before_the_first_upgrade(tmp_settings: Settings) -> None:
    checks = run_checks(tmp_settings)
    assert checks[4] == ("Database schema", False, "none -> 0001 FAIL (run: fin db upgrade)")


def test_database_schema_is_ok_after_an_upgrade(tmp_settings: Settings) -> None:
    upgrade_to_head(tmp_settings.effective_database_url)
    checks = run_checks(tmp_settings)
    assert checks[4] == ("Database schema", True, "0001 OK")


def test_database_schema_shows_an_old_revision(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    upgrade_to_head(tmp_settings.effective_database_url)
    monkeypatch.setattr(finances.diagnostics, "head_revision", lambda: "0002")
    checks = run_checks(tmp_settings)
    assert checks[4] == ("Database schema", False, "0001 -> 0002 FAIL (run: fin db upgrade)")


def test_database_schema_uses_the_settings_it_is_given(
    tmp_settings: Settings, tmp_path: Path
) -> None:
    other = Settings(data_dir=tmp_path / "other")
    upgrade_to_head(other.effective_database_url)
    assert run_checks(other)[4] == ("Database schema", True, "0001 OK")
    assert run_checks(tmp_settings)[4][1] is False


def test_database_schema_reports_an_unsupported_database(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, database_url="postgresql://user:secret@host/db")
    checks = run_checks(settings)
    assert checks[4] == ("Database schema", False, "unsupported database FAIL")


def test_database_schema_reports_a_file_that_is_not_a_database(tmp_settings: Settings) -> None:
    tmp_settings.data_dir.mkdir(parents=True)
    (tmp_settings.data_dir / "finances.db").write_text("this is not a database " * 50)
    checks = run_checks(tmp_settings)
    assert checks[4] == ("Database schema", False, "cannot open database FAIL")


def test_database_schema_check_changes_no_tables(tmp_settings: Settings) -> None:
    run_checks(tmp_settings)
    engine = get_engine(tmp_settings.effective_database_url)
    with engine.connect() as connection:
        tables = connection.execute(text("SELECT name FROM sqlite_master")).all()
    engine.dispose()
    assert tables == []
```

### Step 6: Write

Replace the whole content of `tests/e2e/test_cli.py` with exactly this:

```python
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings, get_settings

runner = CliRunner(env={"COLUMNS": "200"})


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_doctor_creates_data_dir(tmp_settings: Settings) -> None:
    result = runner.invoke(app, ["doctor"])
    assert tmp_settings.data_dir.is_dir()
    assert "Data dir" in result.stdout


def test_doctor_exits_1_when_a_check_fails(monkeypatch, tmp_settings) -> None:
    monkeypatch.setattr(
        "finances.cli.main.run_checks",
        lambda settings: [("Probe", False, "bad FAIL")],
    )

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "Probe" in result.stdout


def test_doctor_fails_before_the_first_upgrade(tmp_settings: Settings) -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "Database schema" in result.stdout
    assert "none -> 0001 FAIL (run: fin db upgrade)" in result.stdout


def test_db_upgrade_reports_the_revision(tmp_settings: Settings) -> None:
    result = runner.invoke(app, ["db", "upgrade"])
    assert result.exit_code == 0
    assert "Database is at revision 0001" in result.stdout
    assert (tmp_settings.data_dir / "finances.db").is_file()


def test_db_upgrade_prints_the_revision_it_was_given(tmp_settings: Settings, monkeypatch) -> None:
    monkeypatch.setattr("finances.cli.db.upgrade_to_head", lambda: "0007")
    result = runner.invoke(app, ["db", "upgrade"])
    assert result.exit_code == 0
    assert result.stdout == "Database is at revision 0007\n"


def test_db_upgrade_twice_is_fine(tmp_settings: Settings) -> None:
    runner.invoke(app, ["db", "upgrade"])
    result = runner.invoke(app, ["db", "upgrade"])
    assert result.exit_code == 0
    assert "Database is at revision 0001" in result.stdout


def test_doctor_passes_after_an_upgrade(tmp_settings: Settings) -> None:
    runner.invoke(app, ["db", "upgrade"])
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "0001 OK" in result.stdout


def test_db_upgrade_reports_an_unsupported_database(tmp_settings: Settings, monkeypatch) -> None:
    monkeypatch.setenv("FIN_DATABASE_URL", "postgresql://user:secret@host/db")
    get_settings.cache_clear()
    result = runner.invoke(app, ["db", "upgrade"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.stderr == "Error: only SQLite databases are supported\n"
    assert "secret" not in result.output
```

### Step 7: Write

Create `tests/e2e/test_cli_accounts.py` with exactly this content:

```python
import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow

runner = CliRunner(env={"COLUMNS": "200"})
NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
ADD = ["accounts", "add", "--name", "Test Checking", "--institution", "Test Bank"]


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    result = runner.invoke(app, ["db", "upgrade"])
    assert result.exit_code == 0
    return tmp_settings


def stored(settings: Settings) -> list[tuple]:
    engine = get_engine(settings.effective_database_url)
    with session_scope(engine) as session:
        rows = session.scalars(select(AccountRow).order_by(AccountRow.id)).all()
        found = [(r.name, r.institution, r.type, r.currency, r.last4, r.is_active) for r in rows]
    engine.dispose()
    return found


def deactivate(settings: Settings, name: str) -> None:
    engine = get_engine(settings.effective_database_url)
    with session_scope(engine) as session:
        session.scalars(select(AccountRow).where(AccountRow.name == name)).one().is_active = False
    engine.dispose()


def add(name: str, account_type: str = "checking", last4: str | None = None) -> None:
    args = ["accounts", "add", "--name", name, "--institution", "Test Bank", "--type", account_type]
    if last4 is not None:
        args += ["--last4", last4]
    result = runner.invoke(app, args)
    assert result.exit_code == 0


def test_accounts_add_stores_the_account(migrated: Settings) -> None:
    result = runner.invoke(app, [*ADD, "--type", "checking"])
    assert result.exit_code == 0
    assert result.stdout == 'Added account "Test Checking" (id 1)\n'
    assert stored(migrated) == [("Test Checking", "Test Bank", "checking", "USD", None, True)]


def test_accounts_add_takes_currency_and_last4(migrated: Settings) -> None:
    args = [*ADD, "--type", "credit_card", "--currency", "CAD", "--last4", "0042"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    assert stored(migrated) == [("Test Checking", "Test Bank", "credit_card", "CAD", "0042", True)]


def test_accounts_add_numbers_accounts_in_order(migrated: Settings) -> None:
    add("First")
    result = runner.invoke(app, [*ADD, "--type", "savings"])
    assert result.stdout == 'Added account "Test Checking" (id 2)\n'


def test_accounts_add_shows_the_stored_name(migrated: Settings) -> None:
    args = [
        "accounts",
        "add",
        "--name",
        "  Spaced  ",
        "--institution",
        "Test Bank",
        "--type",
        "other",
    ]
    result = runner.invoke(app, args)
    assert result.stdout == 'Added account "Spaced" (id 1)\n'


def test_accounts_add_rejects_a_duplicate_name(migrated: Settings) -> None:
    add("Test Checking")
    result = runner.invoke(
        app, ["accounts", "add", "--name", "test checking", "--institution", "X", "--type", "other"]
    )
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.stderr == "Error: an account with this name already exists\n"
    assert result.stdout == ""
    assert len(stored(migrated)) == 1


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--last4", "12a4", "last4 must be exactly 4 digits"),
        ("--last4", "12345", "last4 must be exactly 4 digits"),
        ("--name", "   ", "account name must not be empty"),
        ("--institution", "", "institution must not be empty"),
    ],
)
def test_accounts_add_reports_bad_input(
    migrated: Settings, option: str, value: str, message: str
) -> None:
    result = runner.invoke(app, [*ADD, "--type", "checking", option, value])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.stderr == f"Error: {message}\n"
    assert result.stdout == ""
    assert stored(migrated) == []


def test_accounts_add_rejects_an_unknown_type(migrated: Settings) -> None:
    result = runner.invoke(app, [*ADD, "--type", "brokerage"])
    assert result.exit_code == 2
    assert stored(migrated) == []


def test_accounts_add_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = runner.invoke(app, [*ADD, "--type", "checking"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.stderr == NOT_MIGRATED
    assert result.stdout == ""


def test_accounts_list_says_when_there_are_none(migrated: Settings) -> None:
    result = runner.invoke(app, ["accounts", "list"])
    assert result.exit_code == 0
    assert result.stdout == "No accounts.\n"


def test_accounts_list_shows_a_table(migrated: Settings) -> None:
    add("Test Card", "credit_card", "0042")
    result = runner.invoke(app, ["accounts", "list"])
    assert result.exit_code == 0
    for heading in ["Name", "Institution", "Type", "Last 4", "Active"]:
        assert heading in result.stdout
    for cell in ["Test Card", "Test Bank", "credit_card", "••0042", "yes"]:
        assert cell in result.stdout
    assert "No accounts." not in result.stdout


def test_accounts_list_leaves_last4_empty_when_unknown(migrated: Settings) -> None:
    add("No Digits")
    result = runner.invoke(app, ["accounts", "list"])
    assert "No Digits" in result.stdout
    assert "•" not in result.stdout
    assert "None" not in result.stdout


def test_accounts_list_is_sorted_by_name(migrated: Settings) -> None:
    for name in ["cherry", "Banana", "apple"]:
        add(name)
    output = runner.invoke(app, ["accounts", "list"]).stdout
    assert output.index("apple") < output.index("Banana") < output.index("cherry")


def test_accounts_list_hides_inactive_accounts(migrated: Settings) -> None:
    add("Open Account")
    add("Closed Account")
    deactivate(migrated, "Closed Account")
    result = runner.invoke(app, ["accounts", "list"])
    assert "Open Account" in result.stdout
    assert "Closed Account" not in result.stdout


def test_accounts_list_all_shows_inactive_accounts(migrated: Settings) -> None:
    add("Open Account")
    add("Closed Account")
    deactivate(migrated, "Closed Account")
    result = runner.invoke(app, ["accounts", "list", "--all"])
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    closed = next(line for line in lines if "Closed Account" in line)
    opened = next(line for line in lines if "Open Account" in line)
    assert "no" in closed.split("Test Bank")[1]
    assert "yes" in opened.split("Test Bank")[1]


def test_accounts_list_says_none_when_all_are_inactive(migrated: Settings) -> None:
    add("Closed Account")
    deactivate(migrated, "Closed Account")
    assert runner.invoke(app, ["accounts", "list"]).stdout == "No accounts.\n"


def test_accounts_list_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = runner.invoke(app, ["accounts", "list"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.stderr == NOT_MIGRATED
    assert result.stdout == ""
```

### Step 8: Run

`.venv/bin/python -m ruff format src/finances/cli src/finances/diagnostics.py tests/e2e tests/unit/test_diagnostics.py`

Expect: the output ends with `reformatted` or `left unchanged`. Both are fine.

### Step 9: Run

`.venv/bin/python -m pytest tests/e2e tests/unit/test_diagnostics.py --no-cov`

Expect: the last line contains `22 failed, 2 passed, 17 errors`. The tests fail because the four bodies are not written yet.

### Step 10: Code

In `src/finances/diagnostics.py`, replace `raise NotImplementedError` with your implementation of `_database_schema`. Follow Part 1 (R1 to R4).

### Step 11: Run

`.venv/bin/python -m ruff format src/finances/diagnostics.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 12: Run

`.venv/bin/python -m pytest tests/unit/test_diagnostics.py --no-cov`

Expect: the last line contains `13 passed`

### Step 13: Code

In `src/finances/cli/db.py`, replace `raise NotImplementedError` with your implementation of `upgrade`. Follow Part 2 (R5 and R6).

### Step 14: Run

`.venv/bin/python -m ruff format src/finances/cli/db.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 15: Run

`.venv/bin/python -m pytest tests/e2e/test_cli.py --no-cov`

Expect: the last line contains `9 passed`

### Step 16: Code

In `src/finances/cli/accounts.py`, replace the first `raise NotImplementedError` with your implementation of `add`. Follow Part 3 (R7 to R9).

### Step 17: Run

`.venv/bin/python -m ruff format src/finances/cli/accounts.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 18: Run

`.venv/bin/python -m pytest tests/e2e/test_cli_accounts.py --no-cov -k "test_accounts_add"`

Expect: the last line contains `11 passed, 8 deselected`

### Step 19: Code

In `src/finances/cli/accounts.py`, replace the remaining `raise NotImplementedError` with your implementation of `list_command`. Follow Part 4 (R10 to R12).

### Step 20: Run

`.venv/bin/python -m ruff format src/finances/cli/accounts.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 21: Run

`.venv/bin/python -m ruff check --fix src/finances/cli src/finances/diagnostics.py`

Expect: the last line is `All checks passed!`. A line saying an error was fixed is fine: it removes an import you did not use.

### Step 22: Run

`.venv/bin/python -m pytest tests/e2e tests/unit/test_diagnostics.py --no-cov`

Expect: the last line contains `41 passed`

### Step 23: Run

`.venv/bin/python -m pytest tests/e2e tests/unit/test_diagnostics.py -o addopts="" --import-mode=importlib --cov=finances.cli --cov=finances.diagnostics --cov-branch --cov-report=term-missing --cov-fail-under=100`

Expect: the output contains `Required test coverage of 100% reached`.

This step checks that every line you wrote is used by a test. If it prints `FAIL Required test coverage of 100% not reached`, the "Missing" column lists line numbers that no test runs. Those lines are code that no requirement asks for: delete them. Do not go on until this step passes.

### Step 24: Write

Add this entry at the end of `docs/progress.md`, after one blank line. Replace `YYYY-MM-DD` with today's date. If you did anything these steps did not ask for, describe it on the "Deviations" line in place of `None`.

```markdown
## Phase 2m: the database and account commands (YYYY-MM-DD)
- Built: `fin db upgrade` in `src/finances/cli/db.py`; `fin accounts add` and `fin accounts list` in `src/finances/cli/accounts.py`; the "Database schema" check in `src/finances/diagnostics.py`; `tests/e2e/test_cli_accounts.py` and updated CLI and diagnostics tests. 315 tests pass. `finances.cli` and `diagnostics.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None
```

### Step 25: Run

`.venv/bin/python -m ruff format .`

Expect: `35 files left unchanged`. If it says a file was reformatted, that is fine: go on to step 26.

### Step 26: Run

`.venv/bin/python -m ruff format --check .`

Expect: `35 files already formatted`

### Step 27: Run

`.venv/bin/python -m ruff check .`

Expect: `All checks passed!`

### Step 28: Run

`.venv/bin/python -m pytest`

Expect: the last line contains `315 passed`, and the output contains `Required test coverage of 85.0% reached`.

### Step 29: Run

`.venv/bin/python -m pytest tests/e2e tests/unit/test_diagnostics.py -o addopts="" --import-mode=importlib --cov=finances.cli --cov=finances.diagnostics --cov-branch --cov-report=term-missing --cov-fail-under=100`

Expect: the output contains `Required test coverage of 100% reached`. This is step 23 again, in case a later step changed a file.

### Step 30: Run

`git grep -n --untracked -E "logging|select\(|AccountRow|validate_last4|\.strip\(|session\.add|commit\(" -- src/finances/cli/db.py src/finances/cli/accounts.py`

Expect: no output. A match means the command is doing work that belongs to an earlier phase's function.

### Step 31: Run

`.venv/bin/fin --help`

Expect: the output lists three commands: `doctor`, `db`, and `accounts`. This runs the real program, outside the tests.

### Step 32: Run

`git status --short`

Expect exactly these eight lines and nothing else:

```
 M docs/progress.md
 M src/finances/cli/main.py
 M src/finances/diagnostics.py
 M tests/e2e/test_cli.py
 M tests/unit/test_diagnostics.py
?? src/finances/cli/accounts.py
?? src/finances/cli/db.py
?? tests/e2e/test_cli_accounts.py
```

## If a Run step prints something else

| Step | Do this, then run the step again |
|---|---|
| any | If the output says `command not found`, `No such file`, or `No module named ruff` (or `pytest`), the command was not typed as written. Type it again starting with `.venv/bin/python`. If `.venv/bin/python` itself is missing, stop and report that; do not create a virtual environment |
| 9 | If it reports an import error or a syntax error, the message names a file: redo the Write step for that file (steps 1 to 7) |
| 12 | Read the first failing test: its name says which case is wrong (`is_ok_after_an_upgrade` is R1, `fails_before` and `old_revision` are R2, `unsupported` is R3, `data_dir_unwritable` and `not_a_database` are R4). Change only the body of `_database_schema`, then redo step 11 |
| 15 | Read the first failing test. Change only the body of `upgrade`, then redo step 14. If a `doctor` test fails, look at step 12 again |
| 18 | Read the first failing test: `needs_a_migrated_database` is R7, `stores`, `takes`, `numbers`, and `shows_the_stored_name` are R8, `duplicate` and `bad_input` are R9. The test shows the exact text expected. Change only the body of `add`, then redo step 17 |
| 21 | The error names a line: fix that line, then redo step 20 |
| 22 | Read the first failing test: `needs_a_migrated_database` is R10, `says_when_there_are_none` and `says_none_when_all_are_inactive` are R11, the others are R12. Change only the body of `list_command`, then redo steps 20 and 21. If an earlier test fails, you changed an earlier function: put it back |
| 23 or 29 | Delete the lines listed under "Missing", then redo steps 20 to 22 |
| 26 | Run step 25 again |
| 27 | Run `.venv/bin/python -m ruff check --fix .`. If an error remains, it names a file and a line: fix that line |
| 28 | A test in another file fails only if a file outside this phase was changed. Find it with step 32 and undo the edit by hand |
| 30 | Each line printed is work the command must not do. Remove it and call the earlier phase's function, then redo steps 20 to 23 |
| 31 | The error names a file and a line: fix that line, then redo steps 20 to 23 |
| 32 | A path that is not in the list is a file you must not have changed, or a database file a test left behind. For a file you changed, open it and undo your edit by hand. Report any database file. Do not use a git command |

## Final report

When step 32 matches, reply with the numbers 1 to 32, and after each Run step the last line of output you saw. Do not write "done" for a step you did not run.
