# Phase 2h: `get_engine` and `session_scope`

## Goal

Write the two functions every database operation will go through: `get_engine` opens the SQLite database, and `session_scope` wraps a unit of work in a transaction. The tests are given, and they run against a real temporary database. **You write both function bodies.** The work is to do the 18 steps in order.

This phase has about the same number of steps as the last one, but the code has more decisions in it: three kinds of database URL, a setting applied to every connection, and commit or rollback depending on what happened.

## Read first

- `AGENTS.md`, sections "Running commands", "Privacy rules", and "Architecture rules"
- `src/finances/config.py` (the `get_settings` function and `effective_database_url`)

## Starting state

- Phase 2g is done and committed. `git status --short` prints nothing.
- `.venv/bin/python -m pytest` ends with `170 passed`.
- SQLAlchemy 2 is installed. `src/finances/db/` contains `__init__.py` and `orm.py`.
- The folder `tests/integration/` does not exist yet.
- These commands are written for macOS. On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python`.

## Files

| Path | Action |
|---|---|
| `src/finances/db/engine.py` | create from the block in step 3; you write both function bodies |
| `tests/integration/test_engine.py` | create from the block in step 1 |
| `docs/progress.md` | add one entry at the end |

Do not create or modify any other file.

## What to build

### Part 1: `get_engine`

```python
def get_engine(url: str | None = None) -> Engine
```

- **R1.** When `url` is `None`, use `get_settings().effective_database_url`.
- **R2.** Only SQLite is supported. For any other backend, raise `ValueError("only SQLite databases are supported")` before doing anything else: no engine and no folder is created. The message is exactly that constant text. It never contains the URL, because a URL can hold a password.
- **R3.** For a SQLite database stored in a file, create the folder that will hold the file if it is missing, including any missing parent folders. An existing folder is not an error.
- **R4.** For an in-memory SQLite database, create nothing on disk.
- **R5.** Every connection the engine opens has foreign keys switched on. SQLite switches them off for each new connection, so this must be done with a listener for the engine's `connect` event, not once on a single connection.

### Part 2: `session_scope`

```python
@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]
```

- **R6.** It yields a `Session` bound to `engine`.
- **R7.** When the `with` block ends normally, commit.
- **R8.** When the `with` block raises, roll back and let the same exception continue. In both cases the session is closed at the end.

### SQLAlchemy facts you will need

These are how the library works, not a recipe. How you put them together is up to you.

- `make_url(url)` parses a URL without connecting. On the result, `.get_backend_name()` is `"sqlite"` for every SQLite URL, and `.database` is the path of the database file.
- For an in-memory database, `.database` is `None`, `""`, or `":memory:"`.
- `create_engine(url)` returns the engine.
- A `connect` listener looks like this. `cursor.execute` takes plain SQL text; the SQL to switch foreign keys on is `PRAGMA foreign_keys=ON`.

  ```python
  @event.listens_for(engine, "connect")
  def _on_connect(dbapi_connection, connection_record):
      cursor = dbapi_connection.cursor()
      ...
      cursor.close()
  ```

- `Session(engine)` makes a session. It has `commit()`, `rollback()`, and `close()`.
- A function decorated with `@contextmanager` runs up to its `yield`, hands the yielded value to the `with` block, and continues after the `yield` when the block ends. An exception raised in the block appears at the `yield`.

## Rules

- Do not change the test file. If a test fails, `engine.py` is wrong.
- Do not change the given parts of `engine.py`: the module docstring, the two `def` lines, the `@contextmanager` line, and the two docstrings.
- Do not log or print anything, and do not pass `echo=True` to `create_engine`: both would write financial data to the console.
- Do not create tables here. Do not call `create_all`.
- Do not change `orm.py` or anything under `src/finances/domain/`.
- Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.

## How to work

- Each step is **one action**: **Write** (use the block given), **Code** (write code yourself), or **Run** (one command).
- Do all 18 steps, in order. Do not skip a Run step, and do not merge steps.
- After each Run step, compare the output with "Expect". If it differs, use the table under "If a Run step prints something else".
- Type every command exactly as written, starting with `.venv/bin/python`. Do not shorten it to `python`, `python3`, `pip`, `ruff`, or `pytest`.
- Do not activate the virtual environment and do not create one. `.venv/` already exists.

## Steps

### Step 1: Write

Create `tests/integration/test_engine.py` with exactly this content. Create the folder `tests/integration/` first; it does not exist yet.

```python
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finances.config import Settings
from finances.db.engine import get_engine, session_scope

MEMORY_URLS = ["sqlite://", "sqlite:///:memory:"]
OTHER_URLS = ["postgresql://user:secret@host/db", "mysql://user:secret@host/folder/db"]
CREATE_CHILD = (
    "CREATE TABLE child ("
    "id INTEGER PRIMARY KEY, "
    "parent_id INTEGER NOT NULL REFERENCES parent (id))"
)


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def count_parents(engine: Engine) -> int:
    with engine.connect() as connection:
        return connection.execute(text("SELECT COUNT(*) FROM parent")).scalar_one()


def foreign_keys(connection) -> int:
    return connection.execute(text("PRAGMA foreign_keys")).scalar_one()


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = get_engine(sqlite_url(tmp_path / "test.db"))
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
        connection.execute(text(CREATE_CHILD))
    yield engine
    engine.dispose()


def test_get_engine_returns_an_engine(engine: Engine) -> None:
    assert isinstance(engine, Engine)


def test_get_engine_uses_the_configured_database_by_default(tmp_settings: Settings) -> None:
    engine = get_engine()
    url = engine.url.render_as_string(hide_password=False)
    engine.dispose()
    assert url == tmp_settings.effective_database_url
    assert tmp_settings.data_dir.is_dir()


def test_get_engine_creates_missing_parent_folders(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "app.db"
    get_engine(sqlite_url(target)).dispose()
    assert target.parent.is_dir()


def test_get_engine_accepts_an_existing_folder(tmp_path: Path) -> None:
    get_engine(sqlite_url(tmp_path / "app.db")).dispose()
    get_engine(sqlite_url(tmp_path / "app.db")).dispose()


def test_get_engine_creates_folders_for_a_relative_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    get_engine("sqlite:///nested/dir/app.db").dispose()
    assert (tmp_path / "nested" / "dir").is_dir()


@pytest.mark.parametrize("url", MEMORY_URLS)
def test_get_engine_in_memory_creates_nothing_on_disk(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    engine = get_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
    engine.dispose()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("url", OTHER_URLS)
def test_get_engine_rejects_other_backends(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError) as excinfo:
        get_engine(url)
    assert str(excinfo.value) == "only SQLite databases are supported"
    assert list(tmp_path.iterdir()) == []


def test_foreign_keys_are_on(engine: Engine) -> None:
    with engine.connect() as connection:
        assert foreign_keys(connection) == 1


def test_foreign_keys_are_on_for_every_connection(engine: Engine) -> None:
    with engine.connect() as first, engine.connect() as second:
        assert foreign_keys(first) == 1
        assert foreign_keys(second) == 1


@pytest.mark.parametrize("url", MEMORY_URLS)
def test_foreign_keys_are_on_in_memory(url: str) -> None:
    engine = get_engine(url)
    with engine.connect() as connection:
        assert foreign_keys(connection) == 1
    engine.dispose()


def test_a_broken_foreign_key_is_rejected(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("INSERT INTO child (id, parent_id) VALUES (1, 99)"))


def test_session_scope_yields_a_session_bound_to_the_engine(engine: Engine) -> None:
    with session_scope(engine) as session:
        assert isinstance(session, Session)
        assert session.get_bind() is engine


def test_session_scope_commits_on_success(engine: Engine) -> None:
    with session_scope(engine) as session:
        session.execute(text("INSERT INTO parent (id) VALUES (1)"))
    assert count_parents(engine) == 1


def test_session_scope_rolls_back_on_error(engine: Engine) -> None:
    with pytest.raises(RuntimeError), session_scope(engine) as session:
        session.execute(text("INSERT INTO parent (id) VALUES (1)"))
        raise RuntimeError("boom")
    assert count_parents(engine) == 0


def test_session_scope_reraises_the_same_exception(engine: Engine) -> None:
    error = RuntimeError("boom")
    with pytest.raises(RuntimeError) as excinfo, session_scope(engine):
        raise error
    assert excinfo.value is error


def test_session_scope_keeps_earlier_work_after_a_later_error(engine: Engine) -> None:
    with session_scope(engine) as session:
        session.execute(text("INSERT INTO parent (id) VALUES (1)"))
    with pytest.raises(RuntimeError), session_scope(engine) as session:
        session.execute(text("INSERT INTO parent (id) VALUES (2)"))
        raise RuntimeError("boom")
    assert count_parents(engine) == 1


@pytest.mark.parametrize("fail", [False, True])
def test_session_scope_closes_the_session(
    engine: Engine, monkeypatch: pytest.MonkeyPatch, fail: bool
) -> None:
    closed = []
    real_close = Session.close

    def spy(self: Session) -> None:
        closed.append(self)
        real_close(self)

    monkeypatch.setattr(Session, "close", spy)
    if fail:
        with pytest.raises(RuntimeError), session_scope(engine) as session:
            raise RuntimeError("boom")
    else:
        with session_scope(engine) as session:
            pass
    assert session in closed
```

### Step 2: Run

`.venv/bin/python -m ruff format tests/integration/test_engine.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 3: Write

Create `src/finances/db/engine.py` with exactly this content:

```python
"""Database engine and session scope. SQLite is the only supported backend."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from finances.config import get_settings


def get_engine(url: str | None = None) -> Engine:
    """Return an engine for url, or for the configured database when url is None."""
    raise NotImplementedError


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Yield a session; commit when the block succeeds, roll back when it raises."""
    raise NotImplementedError
```

### Step 4: Run

`.venv/bin/python -m pytest tests/integration/test_engine.py --no-cov`

Expect: the last line contains `10 failed, 11 errors`. The tests fail because the functions are not written yet.

### Step 5: Code

In `src/finances/db/engine.py`, replace the first `raise NotImplementedError` with your implementation of `get_engine`. Keep the `def` line and the docstring as they are. Follow Part 1 (R1 to R5).

### Step 6: Run

`.venv/bin/python -m ruff format src/finances/db/engine.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 7: Run

`.venv/bin/python -m pytest tests/integration/test_engine.py --no-cov -k "not session_scope"`

Expect: the last line contains `14 passed, 7 deselected`

### Step 8: Code

In `src/finances/db/engine.py`, replace the remaining `raise NotImplementedError` with your implementation of `session_scope`. Keep the `@contextmanager` line, the `def` line, and the docstring as they are. Follow Part 2 (R6 to R8).

### Step 9: Run

`.venv/bin/python -m ruff format src/finances/db/engine.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 10: Run

`.venv/bin/python -m ruff check --fix src/finances/db/engine.py`

Expect: the last line is `All checks passed!`. A line saying an error was fixed is fine: it removes an import you did not use.

### Step 11: Run

`.venv/bin/python -m pytest tests/integration/test_engine.py --no-cov`

Expect: the last line contains `21 passed`

### Step 12: Write

Add this entry at the end of `docs/progress.md`, after one blank line. Replace `YYYY-MM-DD` with today's date. If you did anything these steps did not ask for, describe it on the "Deviations" line in place of `None`.

```markdown
## Phase 2h: get_engine and session_scope (YYYY-MM-DD)
- Built: `get_engine` and `session_scope` in `src/finances/db/engine.py`; `tests/integration/test_engine.py`. 191 tests pass. `engine.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None
```

### Step 13: Run

`.venv/bin/python -m ruff format .`

Expect: `25 files left unchanged`. If it says a file was reformatted, that is fine: go on to step 14.

### Step 14: Run

`.venv/bin/python -m ruff format --check .`

Expect: `25 files already formatted`

### Step 15: Run

`.venv/bin/python -m ruff check .`

Expect: `All checks passed!`

### Step 16: Run

`.venv/bin/python -m pytest`

Expect: the last line contains `191 passed`, the output contains `Required test coverage of 85.0% reached`, and the row for `src/finances/db/engine.py` ends with `100%`.

### Step 17: Run

`git grep -n --untracked -E "print\(|logging|echo|create_all" -- src/finances/db/engine.py`

Expect: no output.

### Step 18: Run

`git status --short`

Expect exactly these three lines and nothing else:

```
 M docs/progress.md
?? src/finances/db/engine.py
?? tests/integration/
```

## If a Run step prints something else

| Step | Do this, then run the step again |
|---|---|
| any | If the output says `command not found`, `No such file`, or `No module named ruff` (or `pytest`), the command was not typed as written. Type it again starting with `.venv/bin/python`. If `.venv/bin/python` itself is missing, stop and report that; do not create a virtual environment |
| 4 | If it reports an import error or a syntax error, redo step 3 |
| 7 | Read the first failing test: its name says which requirement is not met (`creates ... folders` is R3, `in_memory` is R4, `rejects_other_backends` is R2, `foreign_keys` is R5, `configured_database` is R1). Change only the body of `get_engine`, then redo step 6 |
| 10 | The error names a line: fix that line, then redo step 9 |
| 11 | Read the first failing test: `commits` is R7; `rolls_back`, `reraises`, and `keeps_earlier_work` are R8; `closes` is the last sentence of R8. Change only the body of `session_scope`, then redo steps 9 and 10. If a `get_engine` or `foreign_keys` test fails, you changed `get_engine`: put it back |
| 14 | Run step 13 again |
| 15 | Run `.venv/bin/python -m ruff check --fix .`. If an error remains, it names a file and a line: fix that line |
| 16, `engine.py` below `100%` | The "Missing" column lists lines of `engine.py` that no test reaches. Remove that code, then redo steps 9 to 11 |
| 17 | Each line printed breaks a rule. Rewrite that line without it, then redo steps 9 to 11 |
| 18 | A path that is not in the list is a file you must not have changed, or a database file a test left behind. For a file you changed, open it and undo your edit by hand. Report any database file. Do not use a git command |

## Final report

When step 18 matches, reply with the numbers 1 to 18, and after each Run step the last line of output you saw. Do not write "done" for a step you did not run.
