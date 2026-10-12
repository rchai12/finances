# Verify Phase 2j: running migrations from code

Spec: `docs/phases/phase-02j-run-migrations.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote the bodies of `head_revision`, `upgrade_to_head`, and `current_revision`, and possibly private helpers (names starting with `_`). `tests/conftest.py`, the test file, and the rest of `migrate.py` were given. Judge the code by behavior and by the rules.

One thing that is correct and must not be reported: passing `None` straight through instead of looking up the settings. `get_engine(None)` already uses the configured database, so R5 is met either way.

This phase has three Code steps, one more than before. In your report, say which steps, if any, were skipped or done out of order.

## 1. Gates

Run each command on its own line, exactly as written. Do not activate the virtual environment: name its interpreter in every command. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m ruff format --check .` | `30 files already formatted` |
| `.venv/bin/python -m pytest` | exit code 0, exactly `228 passed`, 0 skipped, 0 xfailed, `Required test coverage of 85.0% reached`, and the row for `src/finances/db/migrate.py` at `100%` |

## 2. Scope audit

- `git status --short` prints exactly ` M docs/progress.md`, ` M tests/conftest.py`, `?? src/finances/db/migrate.py`, `?? tests/integration/test_migrate.py`. Report every other path.
- `git diff HEAD -- src tests/unit tests/e2e tests/integration/test_engine.py tests/integration/test_migrations.py pyproject.toml` is empty.
- There is no `alembic.ini` anywhere in the repository, and `git status --short --ignored` shows no `.db` or `.sqlite` file and no `data/` folder.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| given | fixtures untouched | compare `tests/conftest.py` with the block in step 2 of the spec | identical apart from trailing whitespace |
| given | test file untouched | compare `tests/integration/test_migrate.py` with the block in step 4 | identical apart from trailing whitespace; the file ends with a newline |
| given | given parts kept | compare `migrate.py` with the block in step 1 | the module docstring, the `MIGRATIONS` line, the three `def` lines, and the three docstrings are unchanged. Import lines may differ |
| R1 | head revision | probe script | `head revision` and `head revision follows MIGRATIONS` end in `ok` |
| R2, R3 | upgrade | probe script | `upgrade returns head`, `tables after upgrade`, `second upgrade returns head`, and `second upgrade keeps the data` end in `ok` |
| R4 | current revision | probe script | the three `current revision` lines and `asking created no tables` end in `ok` |
| R5 | default URL | probe script | the four `default:` lines end in `ok` |
| R6 | percent sign | probe script | the probe database lives in a folder named `50% off`; every line that uses it ends in `ok` |
| R7 | other backends | probe script; search below | the two `rejects another backend` lines end in `ok`; the search prints nothing |
| R8 | engines disposed | read `migrate.py` | every `get_engine(...)` call in the file is followed by `dispose()` on every path, including when an error is raised (a `try` / `finally` or equivalent) |
| R8 | nothing written | search below | no output |
| scope | nothing extra | probe script | `the working folder is still empty`, `nothing unexpected was created`, and `no extra public functions` end in `ok` |

`git grep -n --untracked -E "print\(|logging|except" -- src/finances/db/migrate.py`

## 4. Independent probes

The given tests use plain folder names and one fixed set of two fake migrations. This script uses a folder with a space and a percent sign, a working directory that is not the repository, a fake migrations folder with three revisions, the default URL taken from the environment, and a database that already holds a row when it is upgraded again.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. It works inside its own temporary folder. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import os
import tempfile
from pathlib import Path

from sqlalchemy import inspect

from finances.config import get_settings
from finances.db import migrate
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import current_revision, head_revision, upgrade_to_head
from finances.db.orm import AccountRow

MESSAGE = "only SQLite databases are supported"
REVISION = "revision = {rev!r}\ndown_revision = {down!r}\n\n\ndef upgrade():\n    pass\n\n\ndef downgrade():\n    pass\n"
failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def tables(url):
    engine = get_engine(url)
    names = sorted(inspect(engine).get_table_names())
    engine.dispose()
    return names


def rejects(function):
    try:
        function("mysql://user:hunter2@host/folder/db")
        return False
    except ValueError as exc:
        return str(exc) == MESSAGE
    except Exception:  # noqa: BLE001
        return False


start = Path.cwd()
real_migrations = migrate.MIGRATIONS
try:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder).resolve()
        work = root / "work dir"
        work.mkdir()
        os.chdir(work)

        check("head revision", head_revision() == "0001")
        fake = root / "fake" / "versions"
        fake.mkdir(parents=True)
        for rev, down in [("aaa", None), ("bbb", "aaa"), ("ccc", "bbb")]:
            (fake / f"{rev}.py").write_text(REVISION.format(rev=rev, down=down))
        migrate.MIGRATIONS = root / "fake"
        check("head revision follows MIGRATIONS", head_revision() == "ccc")
        migrate.MIGRATIONS = real_migrations

        target = root / "50% off" / "deep" / "probe.db"
        url = f"sqlite:///{target.as_posix()}"
        check("current revision of a database that does not exist", current_revision(url) is None)
        check("asking created no tables", tables(url) == [])
        check("upgrade returns head", upgrade_to_head(url) == head_revision() == "0001")
        check("tables after upgrade", tables(url) == ["accounts", "alembic_version"])
        check("current revision after upgrade", current_revision(url) == "0001")

        engine = get_engine(url)
        with session_scope(engine) as session:
            session.add(AccountRow(name="Probe", institution="Probe Bank", type="other"))
        engine.dispose()
        check("second upgrade returns head", upgrade_to_head(url) == "0001")
        engine = get_engine(url)
        with session_scope(engine) as session:
            kept = session.query(AccountRow).count()
        engine.dispose()
        check("second upgrade keeps the data", kept == 1)

        os.environ["FIN_DATABASE_URL"] = f"sqlite:///{(root / 'from env' / 'env.db').as_posix()}"
        get_settings.cache_clear()
        check("default: current is None first", current_revision() is None)
        check("default: upgrade", upgrade_to_head() == "0001")
        check("default: current after upgrade", current_revision() == "0001")
        check("default: the configured file was used", (root / "from env" / "env.db").is_file())

        check("upgrade_to_head rejects another backend", rejects(upgrade_to_head))
        check("current_revision rejects another backend", rejects(current_revision))
        check("the working folder is still empty", list(work.iterdir()) == [])
        names = sorted(path.name for path in root.iterdir())
        check(f"nothing unexpected was created {names}", names == ["50% off", "fake", "from env", "work dir"])
except Exception as exc:  # noqa: BLE001
    check(f"probe ran to the end (stopped by {type(exc).__name__}: {exc})", False)
finally:
    migrate.MIGRATIONS = real_migrations
    os.chdir(start)
    os.environ.pop("FIN_DATABASE_URL", None)
    get_settings.cache_clear()

public = sorted(
    name
    for name, value in vars(migrate).items()
    if callable(value) and getattr(value, "__module__", "") == migrate.__name__ and not name.startswith("_")
)
check(f"no extra public functions {public}", public == ["current_revision", "head_revision", "upgrade_to_head"])
print("FAILURES", failures)
```

## 5. Progress log

`docs/progress.md` ends with the entry given in step 17 of the spec, with a real date in place of `YYYY-MM-DD`. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then one line: `Steps skipped or out of order: <none, or the step numbers>`.

## If the verdict is FAIL

Send each repair in one of these forms, and no other:

- "Run step N of the spec again."
- "Replace the whole content of `<given file>` with the block in step N." (`tests/conftest.py` or the test file only)
- For a function: "R<n> is not met: `<call>` gave `<got>`; it must give `<want>`. Change only the body of `<function>` (or your private helper), then run steps 14 to 23 again." At most three.
- For a rule: "Line N of `migrate.py` has `<thing>`, which R<n> forbids. Rewrite that line, then run steps 14 to 23 again."
