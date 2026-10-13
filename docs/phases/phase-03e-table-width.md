# Phase 3e: table width

## Goal

Fix how the commands print tables. Phase 3d fixed the two table consoles at 200 columns (`Console(width=200, height=25)`) so that its tests would pass in a terminal that ignores `COLUMNS`. The result is that `fin statements list` and `fin transactions list` print 200 columns wide in every real terminal, and still wrap a row that needs more than 200. `fin accounts list` and `fin doctor` have the opposite fault: in a dumb terminal, or when their output goes to a file or another program, they wrap at 80 columns.

After this phase one function, `print_table`, prints every table, with one rule:

- in a terminal, the table is fitted to the terminal, as Rich does by default;
- anywhere else (a pipe, a file, a test, a dumb terminal), every row is printed on one line, however long.

The second case is what a program that reads the output needs, and the overarching agent will be one of them.

## Read first

- `AGENTS.md`: "Running commands", "Architecture rules"
- `src/finances/cli/common.py`, `accounts.py`, `importing.py`, `listing.py`, `main.py`
- `tests/e2e/test_cli_listing.py`: how the tests read a table, one list of cells per row

## Starting state

- The previous phase is committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. This phase does not depend on Phase 5 and can be built before or after it.
- Five tables are printed: by `accounts list`, `doctor`, `import folder`, `statements list`, and `transactions list`. Each module that prints one has a module-level `console`.
- `finances.cli` is at 100% line and branch coverage.
- The existing end-to-end tests create their runner with `CliRunner(env={"COLUMNS": "200"})`. That stays. After this phase it has no effect, and it does no harm.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/cli/common.py` | one function added: `print_table` |
| `src/finances/cli/accounts.py`, `importing.py`, `listing.py`, `main.py` | the module-level `console` is removed; each table is printed with `print_table` |
| `tests/unit/test_print_table.py`, `tests/e2e/test_cli_table_width.py` | given, do not change |
| `docs/progress.md` | one new entry |

You may add private names (starting with `_`) to `common.py`. Do not change any other production file or any existing test.

## Out of scope

- Any change to what a table contains: its columns, headings, cell text, order of rows, or the lines printed with `typer.echo`.
- A `--width` option, a `--plain` or `--json` output, or a setting for the width.
- Colour, styles, or a different box shape.
- Making the tests pass when `FORCE_COLOR` is set. That variable makes Rich treat every stream as a colour terminal; it is not set in this project.
- New dependencies.

## Dependencies

None new.

## Design

```python
# src/finances/cli/common.py
def print_table(table: Table, console: Console | None = None) -> None:
    """Print a table: fitted to the terminal when there is one, each row on one line otherwise."""
```

The `console` argument exists so that a test can pass a console that behaves as a terminal. The commands call `print_table(table)`.

How the natural width of a table is found, and whether a second `Console` is created to print at that width, is your choice.

## Requirements

- **R1.** When `console` is `None`, `print_table` creates a `Console()` during the call, so that it sees the output stream and the environment of that moment. No `Console` is created when a module is imported.
- **R2.** The console is a **terminal** when its `is_terminal` is true and its `is_dumb_terminal` is false. In a terminal, the table is printed with that console and Rich's own fitting: a table that is wider than the terminal is as wide as the terminal, with long cells wrapped onto further lines, and a narrower table is not stretched.
- **R3.** Otherwise the table is printed **plain**:
  - every row of the table is one line of output;
  - the output is exactly as wide as the content needs, neither wrapped nor padded. A table with the one heading `A` and the one cell `xyz` is five lines of seven characters;
  - `COLUMNS`, `LINES`, and `TERM` change nothing;
  - the output contains no escape codes;
  - it is written to the console's own stream (`console.file`), which for the default console is standard output.
- **R4.** The five tables are printed with `print_table(table)`. No module in `finances.cli` has a module-level `Console`, and `Console(` is written only in `common.py`.
- **R5.** Nothing else about any command changes. Every existing test passes without being edited.

## Given tests

Create these two files exactly as shown and do not change them. If one of their tests fails, the production code is wrong. Together with the existing tests they reach every line and branch of `finances.cli`, so this phase has no tests for you to write.

`tests/unit/test_print_table.py`

```python
import importlib
import io

import pytest
from rich.console import Console
from rich.table import Table

from finances.cli.common import print_table

LONG = " ".join(["ACME WIDGET"] * 30)
CLI_MODULES = ["accounts", "common", "db", "importing", "listing", "main"]


def wide_table() -> Table:
    table = Table()
    table.add_column("Name")
    table.add_column("Note")
    table.add_row("first", LONG)
    table.add_row("second", "short")
    return table


def rows(output: str) -> list[list[str]]:
    lines = [line for line in output.splitlines() if line.startswith("│")]
    return [[cell.strip() for cell in line.split("│")[1:-1]] for line in lines]


def terminal(width: int, term: str = "xterm-256color") -> tuple[Console, io.StringIO]:
    stream = io.StringIO()
    console = Console(
        file=stream, force_terminal=True, width=width, color_system=None, _environ={"TERM": term}
    )
    return console, stream


def test_without_a_terminal_every_row_is_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    print_table(wide_table())
    output = capsys.readouterr().out
    assert rows(output) == [["first", LONG], ["second", "short"]]
    assert len(output.splitlines()) == 6
    assert len({len(line) for line in output.splitlines()}) == 1


@pytest.mark.parametrize("columns", ["20", "80", "200", "5000"])
def test_without_a_terminal_columns_is_not_used(
    columns: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COLUMNS", columns)
    print_table(wide_table())
    output = capsys.readouterr().out
    assert rows(output) == [["first", LONG], ["second", "short"]]
    assert len(output.splitlines()[0]) == len(LONG) + 13


def test_without_a_terminal_the_table_is_as_wide_as_its_content(
    capsys: pytest.CaptureFixture[str],
) -> None:
    table = Table()
    table.add_column("A")
    table.add_row("xyz")
    print_table(table)
    assert capsys.readouterr().out.splitlines() == [
        "┏━━━━━┓",
        "┃ A   ┃",
        "┡━━━━━┩",
        "│ xyz │",
        "└─────┘",
    ]


def test_without_a_terminal_there_are_no_escape_codes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TERM", "xterm-256color")
    print_table(wide_table())
    assert "\x1b" not in capsys.readouterr().out


def test_a_dumb_terminal_gets_every_row_on_one_line() -> None:
    console, stream = terminal(40, term="dumb")
    print_table(wide_table(), console)
    assert rows(stream.getvalue()) == [["first", LONG], ["second", "short"]]


def test_a_console_that_is_not_a_terminal_gets_every_row_on_one_line() -> None:
    stream = io.StringIO()
    print_table(wide_table(), Console(file=stream, width=40))
    assert rows(stream.getvalue()) == [["first", LONG], ["second", "short"]]


@pytest.mark.parametrize("width", [40, 72, 120])
def test_in_a_terminal_the_table_fits_the_terminal(width: int) -> None:
    console, stream = terminal(width)
    print_table(wide_table(), console)
    lines = stream.getvalue().splitlines()
    assert {len(line) for line in lines} == {width}
    assert len(lines) > 6
    words = " ".join(cells[1] for cells in rows(stream.getvalue())).split()
    assert words == [*LONG.split(), "short"]


def test_in_a_wide_terminal_the_table_is_not_stretched() -> None:
    console, stream = terminal(5000)
    print_table(wide_table(), console)
    assert len(stream.getvalue().splitlines()[0]) == len(LONG) + 13


def test_the_output_goes_to_the_given_console(capsys: pytest.CaptureFixture[str]) -> None:
    console, stream = terminal(40)
    print_table(wide_table(), console)
    stream_two = io.StringIO()
    print_table(wide_table(), Console(file=stream_two))
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "")
    assert stream.getvalue() != ""
    assert stream_two.getvalue() != ""


@pytest.mark.parametrize("name", CLI_MODULES)
def test_no_cli_module_keeps_a_console(name: str) -> None:
    module = importlib.import_module(f"finances.cli.{name}")
    assert not [key for key, value in vars(module).items() if isinstance(value, Console)]
```

`tests/e2e/test_cli_table_width.py`

```python
from pathlib import Path

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import create_account
from finances.ingest.service import import_statement

NAME = "Test Card With A Long Name " + "X" * 90
FILE = "statement-" + "y" * 120 + ".pdf"
ENVIRONMENTS = [
    {"COLUMNS": "20"},
    {"COLUMNS": "80"},
    {"COLUMNS": "20", "TERM": "dumb"},
    {"COLUMNS": "30", "LINES": "10", "TERM": "xterm-256color"},
]


def rows(output: str) -> list[list[str]]:
    lines = [line for line in output.splitlines() if line.startswith("│")]
    return [[cell.strip() for cell in line.split("│")[1:-1]] for line in lines]


@pytest.fixture
def inbox(tmp_settings, fake_bank, fake_statement_pdf) -> Path:
    """A database with one long-named account and one imported statement, and a folder."""
    upgrade_to_head()
    content = fake_statement_pdf()
    with session_scope(get_engine()) as session:
        create_account(session, NAME, "Fake Bank", "credit_card", last4="1111")
        result = import_statement(session, filename=FILE, content=content)
    assert result.message == "imported"
    folder = tmp_settings.data_dir / "inbox"
    folder.mkdir(parents=True)
    (folder / FILE).write_bytes(content)
    return folder


@pytest.mark.parametrize("env", ENVIRONMENTS)
def test_every_table_keeps_each_row_on_one_line(env: dict[str, str], inbox: Path) -> None:
    runner = CliRunner(env=env)

    result = runner.invoke(app, ["accounts", "list"])
    assert result.exit_code == 0
    assert rows(result.output) == [[NAME, "Fake Bank", "credit_card", "••1111", "yes"]]

    result = runner.invoke(app, ["statements", "list"])
    assert result.exit_code == 0
    assert [cells[:3] for cells in rows(result.output)] == [[NAME, FILE, "fake_bank"]]

    result = runner.invoke(app, ["transactions", "list"])
    assert result.exit_code == 0
    found = rows(result.output)
    assert len(found) == 4
    assert [(len(cells), cells[1]) for cells in found] == [(6, NAME)] * 4

    result = runner.invoke(app, ["import", "folder", str(inbox)])
    assert result.exit_code == 0
    found = rows(result.output)
    assert len(found) == 1
    assert found[0][0].endswith(FILE)
    assert found[0][-1] == "already imported"

    result = runner.invoke(app, ["doctor"])
    lines = [line for line in result.output.splitlines() if line.startswith(("│", "┃"))]
    assert len(lines) > 2
    assert len({len(line) for line in lines}) == 1
```

## Rules for this phase

- **The CLI stays thin.** `print_table` decides how wide to print and nothing else. It does not build, sort, or shorten tables.
- **Privacy.** Nothing is logged. The function prints only the table it was given.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, at least N + 24 passed, and `Required test coverage of 85.0% reached` |
| `TERM=dumb COLUMNS=40 .venv/bin/python -m pytest` | the same passed count, 0 failed |
| `.venv/bin/python -m pytest tests/unit/test_print_table.py tests/e2e/test_cli_table_width.py --no-cov` | exactly `24 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| the search below | no output |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.cli --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -e "Console(" -- src/finances/cli ':!src/finances/cli/common.py'`

The fourth command is the situation Phase 3d ran into: a dumb terminal with a narrow width. It is written for macOS; on Windows, set the two variables in the shell first.

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 3e: table width (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. Under "Deviations", say how the natural width is found, list any private names, and anything you did that the spec did not ask for, or `None`.

In your final message, give the output line of each acceptance command.
