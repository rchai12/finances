# Verify Phase 3e: table width

Spec: `docs/phases/phase-03e-table-width.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder added one function, `print_table`, to `src/finances/cli/common.py`, and changed four modules to use it. Two test files were given. The coder wrote no tests in this phase.

Judge the function by what it prints, never by how it is written. These are all correct and must not be reported:

- any way of finding a table's natural width, including printing on a very wide console;
- creating a second `Console` inside `print_table` to print at that width;
- private names in `common.py`.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`, and the two variables of the fourth command are set in the shell first.)

**N** is the passed count before the phase. The coder's entry in `docs/progress.md` states it.

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 24 passed, 0 failed, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| `TERM=dumb COLUMNS=40 .venv/bin/python -m pytest` | the same passed count, 0 failed |
| `.venv/bin/python -m pytest tests/unit/test_print_table.py tests/e2e/test_cli_table_width.py --no-cov` | exactly `24 passed` |
| the coverage command below | `Required test coverage of 100% reached`, with every module of `finances.cli` at 100% |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.cli --cov-branch --cov-report=term-missing --cov-fail-under=100`

Record the total passed count in your report.

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M src/finances/cli/accounts.py
 M src/finances/cli/common.py
 M src/finances/cli/importing.py
 M src/finances/cli/listing.py
 M src/finances/cli/main.py
?? tests/e2e/test_cli_table_width.py
?? tests/unit/test_print_table.py
```

- The two given test files are identical to the blocks in the spec, apart from trailing whitespace.
- In `git diff HEAD -- src/finances/cli/accounts.py src/finances/cli/importing.py src/finances/cli/listing.py src/finances/cli/main.py`, every changed line is one of: an import of `Console` removed, an import of `print_table` added or merged into an existing import, a module-level `console = Console(...)` removed, `console.print(table)` replaced by `print_table(table)`, or a blank line. Report any other change, in particular to a heading, a cell, or a `typer.echo` line.
- `git diff HEAD -- src/finances/cli/common.py` only adds. `require_current_schema` is unchanged.
- `git diff HEAD --stat -- tests/e2e/test_cli.py tests/e2e/test_cli_accounts.py tests/e2e/test_cli_import.py tests/e2e/test_cli_listing.py tests/conftest.py src/finances/db src/finances/domain src/finances/ingest pyproject.toml` is empty.

## 3. Requirement checklist

Probe lines are named by how they start. "Every line starting `x`" passes when each such line ends in `ok`.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | console made during the call | probe script; read `print_table` | every line starting `modules:`; `Console()` is called inside the function body |
| R2 | terminal | probe script | every line starting `terminal` |
| R3 | plain | probe script | every line starting `plain`, `dumb terminal console`, and `given console that is no terminal` |
| R4 | one printer | search below; probe script | no output; the lines starting `modules:` |
| R5 | commands unchanged | gates 3 and 4; scope audit; probe script | every line starting `cli` |

`git grep -n --untracked -e "Console(" -- src/finances/cli ':!src/finances/cli/common.py'`

## 4. Independent probes

The script prints a table with a sixty-word cell under seven environments without a terminal, on consoles that behave as terminals of four widths, and on a dumb terminal. It then runs `accounts list` and `doctor` through the command line with an account name of 144 characters. None of its text is in the given tests.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. It creates its database in a temporary directory that it removes, and reads nothing under `data/`. Every line must end in `ok`; the last line must be `FAILURES 0`. A line that says a section `ran to the end (stopped by ...)` and ends in `FAIL` means the code raised where it should not have; report it with the exception named on that line.

Run it a second time as `TERM=dumb COLUMNS=30 .venv/bin/python <path>`. The result must be the same.

```python
import contextlib
import importlib
import io
import os
import tempfile

from rich.console import Console
from rich.table import Table

failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def section(name, function):
    try:
        function()
    except Exception as exc:  # noqa: BLE001
        check(f"{name}: ran to the end (stopped by {type(exc).__name__}: {exc})", False)


def cells(output):
    lines = [line for line in output.splitlines() if line.startswith("│")]
    return [[cell.strip() for cell in line.split("│")[1:-1]] for line in lines]


WORDS = " ".join(f"probe{n:03d}" for n in range(60))


def make():
    table = Table()
    for heading in ("Key", "Text", "Sum"):
        table.add_column(heading)
    table.add_row("k1", WORDS, "-$1.00")
    table.add_row("k2", "", "$2,345.67")
    table.add_row("k3", "zz", "")
    return table


WANT = [["k1", WORDS, "-$1.00"], ["k2", "", "$2,345.67"], ["k3", "zz", ""]]
NATURAL = len(WORDS) + 2 + 5 + 11 + 4


def to_stdout(env):
    from finances.cli.common import print_table

    saved = {key: os.environ.get(key) for key in ("COLUMNS", "LINES", "TERM", "FORCE_COLOR", "NO_COLOR")}
    for key in saved:
        os.environ.pop(key, None)
    os.environ.update(env)
    stream = io.StringIO()
    try:
        with contextlib.redirect_stdout(stream):
            print_table(make())
    finally:
        for key, value in saved.items():
            os.environ.pop(key, None)
            if value is not None:
                os.environ[key] = value
    return stream.getvalue()


def helper_checks():
    from finances.cli.common import print_table

    for env in ({}, {"COLUMNS": "10"}, {"COLUMNS": "100"}, {"COLUMNS": "9999"}, {"TERM": "dumb"}, {"TERM": "dumb", "COLUMNS": "33"}, {"TERM": "xterm", "LINES": "3"}):
        output = to_stdout(env)
        check(f"plain {env}: every row on one line", cells(output) == WANT)
        check(f"plain {env}: natural width", {len(line) for line in output.splitlines()} == {NATURAL})
        check(f"plain {env}: seven lines, no escape codes", len(output.splitlines()) == 7 and "\x1b" not in output)
    for width in (48, 61, 150):
        stream = io.StringIO()
        console = Console(file=stream, force_terminal=True, width=width, color_system=None, _environ={"TERM": "xterm"})
        print_table(make(), console)
        lines = stream.getvalue().splitlines()
        check(f"terminal {width}: every line is as wide as the terminal", {len(line) for line in lines} == {width})
        text = " ".join(row[1] for row in cells(stream.getvalue())).split()
        check(f"terminal {width}: the long cell is wrapped, nothing lost", len(lines) > 7 and text == [*WORDS.split(), "zz"])
    stream = io.StringIO()
    print_table(make(), Console(file=stream, force_terminal=True, width=4000, color_system=None, _environ={"TERM": "xterm"}))
    check("terminal 4000: the table is not stretched", {len(line) for line in stream.getvalue().splitlines()} == {NATURAL})
    stream = io.StringIO()
    print_table(make(), Console(file=stream, force_terminal=True, width=30, color_system=None, _environ={"TERM": "dumb"}))
    check("dumb terminal console: every row on one line", cells(stream.getvalue()) == WANT)
    small = Table()
    small.add_column("Id")
    small.add_row("7")
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        print_table(small)
    check("plain: a small table is exactly as wide as its content", stream.getvalue().splitlines() == ["┏━━━━┓", "┃ Id ┃", "┡━━━━┩", "│ 7  │", "└────┘"])
    stream, other = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(other):
        print_table(make(), Console(file=stream, width=30))
    check("given console that is no terminal: every row on one line, written to its file", cells(stream.getvalue()) == WANT and other.getvalue() == "")


def module_checks():
    for name in ("accounts", "common", "db", "importing", "listing", "main"):
        module = importlib.import_module(f"finances.cli.{name}")
        kept = [key for key, value in vars(module).items() if isinstance(value, Console)]
        check(f"modules: finances.cli.{name} keeps no console {kept}", not kept)
    common = importlib.import_module("finances.cli.common")
    public = sorted(key for key, value in vars(common).items() if getattr(value, "__module__", "") == common.__name__ and not key.startswith("_"))
    check(f"modules: public functions of common {public}", public == ["print_table", "require_current_schema"])


def cli_checks():
    from typer.testing import CliRunner

    from finances.cli.main import app
    from finances.config import get_settings

    name = "Probe Account " + "Q" * 130
    with tempfile.TemporaryDirectory() as folder:
        saved = os.environ.get("FIN_DATA_DIR")
        os.environ["FIN_DATA_DIR"] = folder
        get_settings.cache_clear()
        try:
            runner = CliRunner(env={"COLUMNS": "24", "TERM": "dumb"})
            check("cli: db upgrade", runner.invoke(app, ["db", "upgrade"]).exit_code == 0)
            added = runner.invoke(app, ["accounts", "add", "--name", name, "--institution", "Probe Bank", "--type", "checking"])
            check("cli: accounts add", added.exit_code == 0)
            for env in ({"COLUMNS": "24", "TERM": "dumb"}, {"COLUMNS": "24"}, {"COLUMNS": "500"}, {}):
                listed = CliRunner(env=env).invoke(app, ["accounts", "list"])
                check(f"cli {env}: accounts list keeps the row on one line", cells(listed.output) == [[name, "Probe Bank", "checking", "", "yes"]])
                doctor = CliRunner(env=env).invoke(app, ["doctor"])
                lines = [line for line in doctor.output.splitlines() if line.startswith(("│", "┃"))]
                check(f"cli {env}: doctor rows are one line each", len(lines) > 2 and len({len(line) for line in lines}) == 1 and all(len(row) == len(cells(doctor.output)[0]) for row in cells(doctor.output)))
        finally:
            os.environ.pop("FIN_DATA_DIR", None)
            if saved is not None:
                os.environ["FIN_DATA_DIR"] = saved
            get_settings.cache_clear()
            with contextlib.suppress(Exception):
                importlib.import_module("finances.db.engine").get_engine().dispose()


section("helper", helper_checks)
section("modules", module_checks)
section("cli", cli_checks)
print("FAILURES", failures)
```

## 5. The coder's tests

There are none to review. Confirm that the coder added no test file beyond the two given ones and edited no existing test (section 2).

## 6. Project rules that apply to this phase

- **Thin CLI.** `print_table` contains no logic about accounts, statements, or money.
- **Privacy.** `git grep -n --untracked -e "logging" -- src/finances/cli/common.py` prints nothing, and the only thing `print_table` prints is the table it was given.
- **Layering.** `common.py` imports nothing from `finances.ingest` or `finances.domain`.

## 7. Out of scope

Each of these must be absent. Report any that is present.

- A width option, an environment variable, or a setting that controls the width.
- A plain-text or JSON output mode.
- Any change to table contents, colours, or box shape.
- Edits to existing tests, including removing `env={"COLUMNS": "200"}` from them.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 3e: table width (YYYY-MM-DD)` with a real date. "Built" gives N and the passed count. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then three lines:

`Total passed: <the count from section 1>`

`Parts that needed a repair: <none, or which requirement>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the probe line, or the file and line), and what is required. Do not prescribe the code.
