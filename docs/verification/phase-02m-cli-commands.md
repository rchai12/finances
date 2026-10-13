# Verify Phase 2m: the database and account commands

Spec: `docs/phases/phase-02m-cli-commands.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote four bodies: `_database_schema` in `diagnostics.py`, `upgrade` in `cli/db.py`, and `add` and `list_command` in `cli/accounts.py`, and possibly private helpers (names starting with `_`). Everything else was given: `cli/main.py` in full, the rest of the three source files, and the three test files. Judge the four bodies by behavior and by the rules.

This phase is two phases joined into one (32 steps, four Code steps, eight files), to find out whether the coder can work at that size. Whatever the verdict, end your report with the "Steps skipped or out of order" line and one more line saying which of the four parts, if any, needed a repair. The architect sizes the next phases from those two lines.

## 1. Gates

Run each command on its own line, exactly as written. Do not activate the virtual environment: name its interpreter in every command. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m ruff format --check .` | `35 files already formatted` |
| `.venv/bin/python -m pytest` | exit code 0, exactly `315 passed`, 0 skipped, 0 xfailed, no warnings summary, and `Required test coverage of 85.0% reached` |
| the coverage command below this table | `Required test coverage of 100% reached` |
| `.venv/bin/fin --help` | lists the commands `doctor`, `db`, and `accounts` |

`.venv/bin/python -m pytest tests/e2e tests/unit/test_diagnostics.py -o addopts="" --import-mode=importlib --cov=finances.cli --cov=finances.diagnostics --cov-branch --cov-report=term-missing --cov-fail-under=100`

## 2. Scope audit

- `git status --short` prints exactly these eight lines. Report every other path.

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

- `git diff HEAD -- src/finances/db src/finances/domain src/finances/config.py src/finances/log.py tests/integration tests/conftest.py pyproject.toml` is empty.
- `git status --short --ignored` shows no `.db` or `.sqlite` file in the repository. A `data/` folder must not have been created by this phase.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| given | test files untouched | compare the three test files with the blocks in steps 5, 6, and 7 of the spec | identical apart from trailing whitespace; each file ends with a newline |
| given | `main.py` untouched | compare with the block in step 3 | identical apart from trailing whitespace |
| given | given parts kept | compare `db.py`, `accounts.py`, and `diagnostics.py` with the blocks in steps 1, 2, and 4 | everything except the four bodies (and added private helpers and import lines) is unchanged, including every option name and help text |
| R1, R2 | schema check | probe script | the four `doctor before` and `doctor after` lines end in `ok` |
| R3, R4 | schema check errors | probe script | the two `doctor check on` lines end in `ok` |
| R5, R6 | `fin db upgrade` | probe script | the three `db upgrade` lines and `the password is never shown` end in `ok` |
| R7, R10 | database not migrated | probe script | `accounts list before upgrade` and `accounts add before upgrade` end in `ok` |
| R8 | add | probe script | the lines `add prints`, `add writes nothing`, `second add`, `third add`, and `only the three good accounts were stored` end in `ok` |
| R9 | add errors | probe script | `duplicate`, `bad last4`, `empty name`, `empty institution`, and the two `usage error` lines end in `ok` |
| R11 | no accounts | probe script | the two `when empty` lines end in `ok` |
| R12 | table | probe script | every line starting `list:` or `list --all:` ends in `ok` |
| rules | thin commands | run the search below this table | no output |
| scope | nothing extra | probe script | the two `no extra public functions` lines and `nothing unexpected was created` end in `ok` |

`git grep -n --untracked -E "logging|select\(|AccountRow|validate_last4|\.strip\(|session\.add|commit\(" -- src/finances/cli/db.py src/finances/cli/accounts.py`

## 4. Independent probes

The given tests run each command against a fresh database. This script runs one continuous session the way a person would use the program: `doctor` before anything exists, the commands refused until the database is migrated, three accounts added with awkward names, four kinds of bad input, one account closed, both listings, and an unsupported database URL that contains a password. None of its names or digits are in the given tests.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. It works inside its own temporary folder and sets `FIN_DATA_DIR` for itself. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import os
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from finances.cli import accounts as accounts_module
from finances.cli import db as db_module
from finances.cli.main import app
from finances.config import Settings, get_settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow
from finances.diagnostics import run_checks

NOT_MIGRATED = "Error: database is not up to date (run: fin db upgrade)\n"
BULLETS = "••"
failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def run(*args):
    return CliRunner(env={"COLUMNS": "200"}).invoke(app, list(args))


def failed_cleanly(result, message):
    return (
        result.exit_code == 1
        and isinstance(result.exception, SystemExit)
        and result.stderr == f"Error: {message}\n"
        and result.stdout == ""
    )


def add(name, kind="checking", *more):
    return run("accounts", "add", "--name", name, "--institution", "Probe Bank", "--type", kind, *more)


start = Path.cwd()
try:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder).resolve()
        os.chdir(root)
        os.environ["FIN_DATA_DIR"] = str(root / "probe data")
        os.environ.pop("FIN_DATABASE_URL", None)
        get_settings.cache_clear()

        result = run("doctor")
        check("doctor before upgrade: exit 1", result.exit_code == 1)
        check("doctor before upgrade: hint", "none -> 0001 FAIL (run: fin db upgrade)" in result.stdout)
        check("accounts list before upgrade", result.exit_code == 1 and run("accounts", "list").stderr == NOT_MIGRATED)
        check("accounts add before upgrade", add("Early").stderr == NOT_MIGRATED)

        result = run("db", "upgrade")
        check("db upgrade", result.exit_code == 0 and result.stdout == "Database is at revision 0001\n")
        check("db upgrade writes nothing to standard error", result.stderr == "")
        result = run("doctor")
        check("doctor after upgrade", result.exit_code == 0 and "0001 OK" in result.stdout)
        check("list when empty", run("accounts", "list").stdout == "No accounts.\n")
        check("list --all when empty", run("accounts", "list", "--all").stdout == "No accounts.\n")

        result = add("  zebra Savings ", "savings", "--last4", "9001", "--currency", "EUR")
        check("add prints the stored name and id", result.stdout == 'Added account "zebra Savings" (id 1)\n')
        check("add writes nothing to standard error", result.stderr == "")
        check("second add", add("Mango Card", "credit_card").stdout == 'Added account "Mango Card" (id 2)\n')
        check("third add", add("apple Checking").stdout == 'Added account "apple Checking" (id 3)\n')

        check("duplicate, other case", failed_cleanly(add("MANGO card"), "an account with this name already exists"))
        check("bad last4", failed_cleanly(add("New", "other", "--last4", "90011"), "last4 must be exactly 4 digits"))
        check("empty name", failed_cleanly(add(" \t "), "account name must not be empty"))
        result = run("accounts", "add", "--name", "New", "--institution", " ", "--type", "other")
        check("empty institution", failed_cleanly(result, "institution must not be empty"))
        check("unknown type is a usage error", add("New", "Savings").exit_code == 2)
        check("a missing option is a usage error", run("accounts", "add", "--name", "New").exit_code == 2)

        engine = get_engine()
        with session_scope(engine) as session:
            rows = session.query(AccountRow).order_by(AccountRow.id).all()
            stored = [(r.name, r.type, r.currency, r.last4) for r in rows]
            session.query(AccountRow).filter_by(name="Mango Card").one().is_active = False
        engine.dispose()
        expected = [("zebra Savings", "savings", "EUR", "9001"), ("Mango Card", "credit_card", "USD", None), ("apple Checking", "checking", "USD", None)]
        check("only the three good accounts were stored", stored == expected)

        output = run("accounts", "list").stdout
        lines = [line for line in output.splitlines() if "Probe Bank" in line]
        check("list: two active rows, sorted without regard to case", ["apple" in lines[0], "zebra" in lines[1], len(lines)] == [True, True, 2])
        check("list: headings", all(h in output for h in ["Name", "Institution", "Type", "Last 4", "Active"]))
        check("list: masked digits", BULLETS + "9001" in lines[1] and BULLETS not in lines[0])
        check("list: type text and yes", "savings" in lines[1] and "yes" in lines[1].split("Probe Bank")[1])
        check("list: no None or True text", "None" not in output and "True" not in output)

        output = run("accounts", "list", "--all").stdout
        lines = [line for line in output.splitlines() if "Probe Bank" in line]
        order = [next(i for i, line in enumerate(lines) if word in line) for word in ("apple", "Mango", "zebra")]
        check("list --all: three rows in order", len(lines) == 3 and order == [0, 1, 2])
        check("list --all: inactive shows no", "no" in lines[1].split("Probe Bank")[1] and "yes" not in lines[1].split("Probe Bank")[1])

        (root / "broken").mkdir()
        (root / "broken" / "finances.db").write_text("not a database " * 100)
        broken = run_checks(Settings(data_dir=root / "broken"))[4]
        check("doctor check on a file that is not a database", broken == ("Database schema", False, "cannot open database FAIL"))
        other = run_checks(Settings(data_dir=root, database_url="mysql://user:hunter2@host/db"))[4]
        check("doctor check on an unsupported database", other == ("Database schema", False, "unsupported database FAIL"))

        os.environ["FIN_DATABASE_URL"] = "mysql://user:hunter2@host/db"
        get_settings.cache_clear()
        result = run("db", "upgrade")
        check("db upgrade on an unsupported database", failed_cleanly(result, "only SQLite databases are supported"))
        check("the password is never shown", "hunter2" not in result.output and "hunter2" not in run("doctor").output)
        names = sorted(path.name for path in root.iterdir())
        check(f"nothing unexpected was created {names}", names == ["broken", "probe data"])
except Exception as exc:  # noqa: BLE001
    check(f"probe ran to the end (stopped by {type(exc).__name__}: {exc})", False)
finally:
    os.chdir(start)
    os.environ.pop("FIN_DATA_DIR", None)
    os.environ.pop("FIN_DATABASE_URL", None)
    get_settings.cache_clear()

for module, expected in [(db_module, ["upgrade"]), (accounts_module, ["add", "list_command"])]:
    public = sorted(
        name
        for name, value in vars(module).items()
        if callable(value) and getattr(value, "__module__", "") == module.__name__ and not name.startswith("_")
    )
    check(f"{module.__name__}: no extra public functions {public}", public == expected)
print("FAILURES", failures)
```

## 5. Progress log

`docs/progress.md` ends with the entry given in step 24 of the spec, with a real date in place of `YYYY-MM-DD`. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then two lines:

`Steps skipped or out of order: <none, or the step numbers>`

`Parts that needed a repair: <none, or Part 1 / Part 2 / Part 3 / Part 4>`

## If the verdict is FAIL

Send each repair in one of these forms, and no other:

- "Run step N of the spec again."
- "Replace the whole content of `<given file>` with the block in step N." (`main.py` or a test file only)
- For a command or the check: "R<n> is not met: `<command or call>` gave `<got>`; it must give `<want>`. Change only the body of `<function>`, then run steps 20 to 32 again." At most three.
- For code no test reaches: "Delete lines N to M of `<file>`: no requirement asks for them. Then run steps 20 to 32 again."
- For a rule: "Line N of `<file>` has `<thing>`, which the Rules section forbids. Remove it and call the earlier phase's function, then run steps 20 to 32 again."
