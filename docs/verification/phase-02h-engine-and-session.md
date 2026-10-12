# Verify Phase 2h: `get_engine` and `session_scope`

Spec: `docs/phases/phase-02h-engine-and-session.md`

Do not modify any file in the repository. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder wrote the bodies of `get_engine` and `session_scope`. The test file, the imports, the `def` lines, the `@contextmanager` line, and the docstrings were given. The spec lists library facts but no recipe, so implementations will differ: judge by behavior and by the rules. A private helper (a name starting with `_`) is allowed, at module level or nested.

This phase tests harder logic at the size that worked for 2g. In your report, say which steps, if any, were skipped or done out of order.

## 1. Gates

Run each command on its own line, exactly as written. Do not activate the virtual environment: name its interpreter in every command. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m ruff format --check .` | `25 files already formatted` |
| `.venv/bin/python -m pytest` | exit code 0, exactly `191 passed`, 0 skipped, 0 xfailed, no warnings summary, `Required test coverage of 85.0% reached`, and the row for `src/finances/db/engine.py` at `100%` |

## 2. Scope audit

- `git status --short` prints exactly ` M docs/progress.md`, `?? src/finances/db/engine.py`, `?? tests/integration/`. Report every other path.
- `tests/integration/` holds exactly `test_engine.py` (ignore `__pycache__`).
- `git diff HEAD -- src tests/unit tests/e2e tests/conftest.py pyproject.toml` is empty.
- No database file was left behind: `git status --short --ignored` shows no `.db` or `.sqlite` file and no `data/`, `a/`, or `nested/` folder in the repository.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| given | test file untouched | compare `tests/integration/test_engine.py` with the block in step 1 of the spec | identical apart from trailing whitespace; the file ends with a newline |
| given | given parts kept | compare `engine.py` with the block in step 3 | the module docstring, both `def` lines, the `@contextmanager` line, and both docstrings are unchanged. Import lines may differ |
| R1 | default URL | probe script | the two `default URL` lines end in `ok` |
| R2 | other backends | probe script; read `get_engine` | every `rejects` line and `rejected URLs create nothing` end in `ok`; the backend check comes before `create_engine` and before any folder is created; the `ValueError` carries a constant string |
| R3 | folders | probe script | `folders created` ends in `ok` |
| R4 | in-memory | probe script | both `in-memory` lines end in `ok` |
| R5 | foreign keys per connection | probe script; read `get_engine` | the three `foreign keys` lines end in `ok`; the setting is applied in a `connect` event listener |
| R6, R7 | commit | probe script | `ORM row committed` and `data persists for a new engine` end in `ok` |
| R8 | rollback, re-raise, close | probe script | `same exception object comes out`, `ORM row rolled back`, `a failing commit raises`, `database usable after a failed commit`, and `session closed` end in `ok` |
| rules | nothing written to the console | run the search below this table | no output |
| scope | nothing extra | probe script | `no extra public functions` ends in `ok` |

`git grep -n --untracked -E "print\(|logging|echo|create_all" -- src/finances/db/engine.py`

## 4. Independent probes

The given tests use a throwaway two-table database built with plain SQL. This script goes further: the real `accounts` table through the ORM, a driver-qualified SQLite URL, three connections at once, a commit that fails, the default URL taken from the environment, and backends the tests do not name.

Save the script in a temporary directory **outside the repository**, run it with `.venv/bin/python <path>` from the repository root, and delete it afterwards. It works inside its own temporary folder and leaves nothing behind. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import os
import tempfile
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from finances.config import get_settings
from finances.db import engine as engine_module
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, Base

MESSAGE = "only SQLite databases are supported"
failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def foreign_keys(connection):
    return connection.execute(text("PRAGMA foreign_keys")).scalar_one()


start = Path.cwd()
try:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder).resolve()
        os.chdir(root)

        deep = root / "one" / "two" / "three" / "probe.db"
        engine = get_engine(f"sqlite+pysqlite:///{deep.as_posix()}")
        check("driver-qualified sqlite URL accepted, folders created", deep.parent.is_dir())
        with engine.connect() as a, engine.connect() as b, engine.connect() as c:
            check("foreign keys on three open connections", [foreign_keys(x) for x in (a, b, c)] == [1, 1, 1])
        engine.dispose()
        with engine.connect() as again:
            check("foreign keys on after the pool is rebuilt", foreign_keys(again) == 1)

        Base.metadata.create_all(engine)
        with session_scope(engine) as session:
            session.add(AccountRow(name="Probe One", institution="Probe Bank", type="checking"))
        with session_scope(engine) as session:
            check("ORM row committed", session.query(AccountRow).count() == 1)

        error = KeyError("probe")
        try:
            with session_scope(engine) as session:
                session.add(AccountRow(name="Probe Two", institution="Probe Bank", type="savings"))
                session.flush()
                raise error
        except KeyError as caught:
            check("same exception object comes out", caught is error)
        else:
            check("same exception object comes out", False)
        with session_scope(engine) as session:
            check("ORM row rolled back", session.query(AccountRow).count() == 1)

        try:
            with session_scope(engine) as session:
                session.add(AccountRow(name="Probe One", institution="Other", type="other"))
            check("a failing commit raises", False)
        except Exception as exc:  # noqa: BLE001
            check("a failing commit raises", type(exc).__name__ == "IntegrityError")
        with session_scope(engine) as session:
            check("database usable after a failed commit", session.query(AccountRow).count() == 1)

        closed = []
        real_close = Session.close
        Session.close = lambda self: (closed.append(self), real_close(self))[1]
        with session_scope(engine) as kept:
            pass
        Session.close = real_close
        check("session closed", kept in closed)
        engine.dispose()

        second = get_engine(f"sqlite:///{deep.as_posix()}")
        with session_scope(second) as session:
            check("data persists for a new engine", session.query(AccountRow).count() == 1)
        second.dispose()

        before = sorted(path.name for path in root.iterdir())
        for url in ["oracle://user:hunter2@host/x/y", "postgresql+psycopg://user:hunter2@host/deep/er/db", "mssql://host/z"]:
            try:
                get_engine(url)
                check(f"rejects {url.split(':')[0]}", False)
            except ValueError as exc:
                check(f"rejects {url.split(':')[0]}", str(exc) == MESSAGE)
            except Exception as exc:  # noqa: BLE001
                check(f"rejects {url.split(':')[0]} (raised {type(exc).__name__})", False)
        check("rejected URLs create nothing", sorted(path.name for path in root.iterdir()) == before)

        memory = get_engine("sqlite:///:memory:")
        with memory.connect() as connection:
            check("in-memory foreign keys", foreign_keys(connection) == 1)
        memory.dispose()
        check("in-memory creates nothing", sorted(path.name for path in root.iterdir()) == before)

        for key, value in [("FIN_DATABASE_URL", f"sqlite:///{(root / 'env' / 'from_env.db').as_posix()}")]:
            os.environ[key] = value
        get_settings.cache_clear()
        from_env = get_engine()
        check("default URL follows FIN_DATABASE_URL", from_env.url.database == (root / "env" / "from_env.db").as_posix())
        check("default URL folder created", (root / "env").is_dir())
        from_env.dispose()
        os.environ["FIN_DATABASE_URL"] = "postgresql://user:hunter2@host/db"
        get_settings.cache_clear()
        try:
            get_engine()
            check("configured non-SQLite URL rejected", False)
        except ValueError as exc:
            check("configured non-SQLite URL rejected", str(exc) == MESSAGE)
        del os.environ["FIN_DATABASE_URL"]
        get_settings.cache_clear()
        pass
except Exception as exc:  # noqa: BLE001
    check(f"probe ran to the end (stopped by {type(exc).__name__})", False)
finally:
    os.chdir(start)
    os.environ.pop("FIN_DATABASE_URL", None)
    get_settings.cache_clear()

names = sorted(
    name
    for name, value in vars(engine_module).items()
    if callable(value) and getattr(value, "__module__", "") == engine_module.__name__ and not name.startswith("_")
)
check(f"no extra public functions {names}", names == ["get_engine", "session_scope"])
print("FAILURES", failures)
```

## 5. Progress log

`docs/progress.md` ends with the entry given in step 12 of the spec, with a real date in place of `YYYY-MM-DD`. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then one line: `Steps skipped or out of order: <none, or the step numbers>`.

## If the verdict is FAIL

Send each repair in one of these forms, and no other:

- "Run step N of the spec again."
- "Replace the whole content of `tests/integration/test_engine.py` with the block in step 1."
- For a function: "R<n> is not met: `<what the probe or test did>` gave `<got>`; it must give `<want>`. Change only the body of `<get_engine or session_scope>`, then run steps 9 to 18 again." At most three.
- For a rule: "Line N of `engine.py` has `<thing>`, which the Rules section forbids. Rewrite that line, then run steps 9 to 18 again."
