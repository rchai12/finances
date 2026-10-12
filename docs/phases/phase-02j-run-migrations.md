# Phase 2j: running migrations from code

## Goal

Write the three functions the app uses to manage its database schema: `head_revision` says what the newest migration is, `upgrade_to_head` applies the migrations, and `current_revision` says which one a database is at. The tests are given. **You write all three function bodies.** The work is to do the 23 steps in order.

This phase also adds two shared test fixtures that give later phases a ready, migrated database.

## Read first

- `AGENTS.md`, sections "Running commands" and "Architecture rules"
- `src/finances/db/engine.py` (`get_engine`)
- `tests/integration/test_migrations.py` (its `make_config` helper shows an Alembic configuration built in code)

## Starting state

- Phase 2i is done and committed. `git status --short` prints nothing.
- `.venv/bin/python -m pytest` ends with `208 passed`.
- `src/finances/db/migrations/` contains `env.py` and `versions/0001_accounts.py`.
- These commands are written for macOS. On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python`.

## Files

| Path | Action |
|---|---|
| `src/finances/db/migrate.py` | create from the block in step 1; you write the three function bodies |
| `tests/conftest.py` | replace whole content with the block in step 2 |
| `tests/integration/test_migrate.py` | create from the block in step 4 |
| `docs/progress.md` | add one entry at the end |

Do not create or modify any other file.

## What to build

```python
def head_revision() -> str
def upgrade_to_head(url: str | None = None) -> str
def current_revision(url: str | None = None) -> str | None
```

### Part 1: `head_revision`

- **R1.** It returns the identifier of the newest migration in the folder named by `MIGRATIONS`. Today that is `"0001"`, but the function must find it by reading the folder each time it is called, never by returning a fixed value: a test points `MIGRATIONS` at a folder with two migrations and expects `"0002"`. It does not open or create a database, and it gives the same answer from any working directory.

### Part 2: `upgrade_to_head`

- **R2.** It applies every migration that the database at `url` has not had yet, then returns the revision the database is now at. After a successful call that equals `head_revision()`.
- **R3.** Calling it again on an up-to-date database changes nothing and returns the same value.

### Part 3: `current_revision`

- **R4.** It returns the revision recorded in the database at `url`, or `None` when the database has no recorded revision (for example a database that was never migrated). It creates no tables.

### All parts

- **R5.** When `url` is `None`, `upgrade_to_head` and `current_revision` use `get_settings().effective_database_url`.
- **R6.** A URL that contains a percent sign must work. A folder can be named `100%`.
- **R7.** A URL that is not SQLite raises `ValueError("only SQLite databases are supported")`. `get_engine` already raises it; do not catch it and do not replace its message.
- **R8.** Every engine that `migrate.py` creates is disposed before the function returns. Nothing is printed or logged.

### Alembic facts you will need

These are how the library works, not a recipe.

- `Config()` makes an empty configuration. `config.set_main_option("script_location", <folder as text>)` tells it where the migrations are, and `config.set_main_option("sqlalchemy.url", <url>)` tells `env.py` which database to use.
- `set_main_option` treats `%` as a special character and fails on a single one. Write each `%` in the value twice (`%%`) and Alembic hands the original text to `env.py`.
- `command.upgrade(config, "head")` applies the migrations. It returns nothing.
- `ScriptDirectory.from_config(config).get_current_head()` returns the newest migration's identifier. It needs only `script_location`.
- `MigrationContext.configure(connection).get_current_revision()` returns the revision recorded in a database, or `None`. `connection` comes from `with engine.connect() as connection:`.
- `get_engine(url)` returns an engine, and `engine.dispose()` releases it.

You may add a private helper function (a name starting with `_`) if several functions need the same lines.

## Rules

- Do not change the test files. If a test fails, `migrate.py` is wrong.
- Do not change the given parts of `migrate.py`: the docstrings, the `MIGRATIONS` line, and the three `def` lines.
- Do not create an `alembic.ini` file.
- Do not change `env.py`, the migration file, `engine.py`, or `orm.py`.
- Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.

## How to work

- Each step is **one action**: **Write** (use the block given), **Code** (write code yourself), or **Run** (one command).
- Do all 23 steps, in order. Do not skip a Run step, and do not merge steps.
- After each Run step, compare the output with "Expect". If it differs, use the table under "If a Run step prints something else".
- Type every command exactly as written, starting with `.venv/bin/python`. Do not shorten it to `python`, `python3`, `pip`, `ruff`, `pytest`, or `alembic`.
- Do not activate the virtual environment and do not create one. `.venv/` already exists.

## Steps

### Step 1: Write

Create `src/finances/db/migrate.py` with exactly this content. It comes first because the fixtures in step 2 import it.

```python
"""Run database migrations from code. There is no alembic.ini, so this works from any folder."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from finances.config import get_settings
from finances.db.engine import get_engine

MIGRATIONS = Path(__file__).parent / "migrations"


def head_revision() -> str:
    """Return the identifier of the newest migration."""
    raise NotImplementedError


def upgrade_to_head(url: str | None = None) -> str:
    """Apply every pending migration and return the revision the database is now at."""
    raise NotImplementedError


def current_revision(url: str | None = None) -> str | None:
    """Return the revision recorded in the database, or None if it has none."""
    raise NotImplementedError
```

### Step 2: Write

Replace the whole content of `tests/conftest.py` with exactly this. The `tmp_settings` fixture is unchanged; `db_url` and `db_engine` are new.

```python
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine

from finances.config import Settings, get_settings
from finances.db.engine import get_engine
from finances.db.migrate import upgrade_to_head

_ENV_KEYS = ("FIN_ENVIRONMENT", "FIN_DATA_DIR", "FIN_DATABASE_URL", "FIN_LOG_LEVEL")


@pytest.fixture
def tmp_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Settings]:
    """Settings whose data dir is under tmp_path, with no .env file in reach."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FIN_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    """URL of a SQLite database file under tmp_path. The file does not exist yet."""
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def db_engine(db_url: str) -> Iterator[Engine]:
    """Engine for a temporary database that has been migrated to the newest revision."""
    upgrade_to_head(db_url)
    engine = get_engine(db_url)
    yield engine
    engine.dispose()
```

### Step 3: Run

`.venv/bin/python -m ruff format tests/conftest.py src/finances/db/migrate.py`

Expect: the output ends with `reformatted` or `left unchanged`. Both are fine.

### Step 4: Write

Create `tests/integration/test_migrate.py` with exactly this content:

```python
from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect, text

import finances.db.migrate
from finances.config import Settings
from finances.db.engine import get_engine
from finances.db.migrate import current_revision, head_revision, upgrade_to_head

OTHER_URL = "postgresql://user:secret@host/db"
MESSAGE = "only SQLite databases are supported"
REVISION = """revision = "{revision}"
down_revision = {down}


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
"""


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def table_names(url: str) -> list[str]:
    engine = get_engine(url)
    names = sorted(inspect(engine).get_table_names())
    engine.dispose()
    return names


def test_head_revision_is_0001() -> None:
    assert head_revision() == "0001"


def test_head_revision_is_the_same_from_another_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert head_revision() == "0001"
    assert list(tmp_path.iterdir()) == []


def test_head_revision_reads_the_migrations_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    versions = tmp_path / "migrations" / "versions"
    versions.mkdir(parents=True)
    (versions / "0001_first.py").write_text(REVISION.format(revision="0001", down="None"))
    (versions / "0002_second.py").write_text(REVISION.format(revision="0002", down='"0001"'))
    monkeypatch.setattr(finances.db.migrate, "MIGRATIONS", tmp_path / "migrations")
    assert head_revision() == "0002"


def test_upgrade_to_head_returns_the_new_revision(db_url: str) -> None:
    assert upgrade_to_head(db_url) == "0001"


def test_upgrade_to_head_creates_the_tables(db_url: str) -> None:
    upgrade_to_head(db_url)
    assert table_names(db_url) == ["accounts", "alembic_version"]


def test_upgrade_to_head_twice_changes_nothing(db_url: str) -> None:
    upgrade_to_head(db_url)
    assert upgrade_to_head(db_url) == "0001"
    assert table_names(db_url) == ["accounts", "alembic_version"]


def test_upgrade_to_head_works_from_another_folder(
    db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert upgrade_to_head(db_url) == "0001"
    assert list(elsewhere.iterdir()) == []


def test_upgrade_to_head_creates_missing_folders(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "app.db"
    assert upgrade_to_head(sqlite_url(target)) == "0001"
    assert target.is_file()


def test_upgrade_to_head_accepts_a_percent_sign(tmp_path: Path) -> None:
    target = tmp_path / "100%" / "app.db"
    assert upgrade_to_head(sqlite_url(target)) == "0001"
    assert target.is_file()
    assert [path.name for path in tmp_path.iterdir()] == ["100%"]


def test_upgrade_to_head_uses_the_configured_database_by_default(
    tmp_settings: Settings,
) -> None:
    assert upgrade_to_head() == "0001"
    assert (tmp_settings.data_dir / "finances.db").is_file()
    assert table_names(tmp_settings.effective_database_url) == ["accounts", "alembic_version"]


def test_upgrade_to_head_rejects_other_backends() -> None:
    with pytest.raises(ValueError) as excinfo:
        upgrade_to_head(OTHER_URL)
    assert str(excinfo.value) == MESSAGE


def test_current_revision_is_none_for_a_new_database(db_url: str) -> None:
    assert current_revision(db_url) is None
    assert table_names(db_url) == []


def test_current_revision_after_an_upgrade(db_url: str) -> None:
    upgrade_to_head(db_url)
    assert current_revision(db_url) == "0001"


def test_current_revision_is_none_when_the_record_is_empty(db_url: str) -> None:
    upgrade_to_head(db_url)
    engine = get_engine(db_url)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM alembic_version"))
    engine.dispose()
    assert current_revision(db_url) is None


def test_current_revision_accepts_a_percent_sign(tmp_path: Path) -> None:
    url = sqlite_url(tmp_path / "100%" / "app.db")
    assert current_revision(url) is None
    upgrade_to_head(url)
    assert current_revision(url) == "0001"


def test_current_revision_uses_the_configured_database_by_default(
    tmp_settings: Settings,
) -> None:
    assert current_revision() is None
    upgrade_to_head()
    assert current_revision() == "0001"


def test_current_revision_rejects_other_backends() -> None:
    with pytest.raises(ValueError) as excinfo:
        current_revision(OTHER_URL)
    assert str(excinfo.value) == MESSAGE


def test_db_engine_fixture_is_migrated(db_engine: Engine, db_url: str) -> None:
    assert sorted(inspect(db_engine).get_table_names()) == ["accounts", "alembic_version"]
    assert current_revision(db_url) == head_revision()


def test_db_engine_fixture_has_foreign_keys_on(db_engine: Engine) -> None:
    with db_engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_db_url_fixture_points_into_tmp_path(db_url: str, tmp_path: Path) -> None:
    assert db_url == sqlite_url(tmp_path / "test.db")
    assert list(tmp_path.iterdir()) == []
```

### Step 5: Run

`.venv/bin/python -m ruff format tests/integration/test_migrate.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 6: Run

`.venv/bin/python -m pytest tests/integration/test_migrate.py --no-cov`

Expect: the last line contains `17 failed, 1 passed, 2 errors`. The tests fail because the functions are not written yet.

### Step 7: Code

In `src/finances/db/migrate.py`, replace the first `raise NotImplementedError` with your implementation of `head_revision`. Keep the `def` line and the docstring as they are. Follow R1.

### Step 8: Run

`.venv/bin/python -m ruff format src/finances/db/migrate.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 9: Run

`.venv/bin/python -m pytest tests/integration/test_migrate.py --no-cov -k "test_head_revision"`

Expect: the last line contains `3 passed, 17 deselected`

### Step 10: Code

In `src/finances/db/migrate.py`, replace the next `raise NotImplementedError` with your implementation of `upgrade_to_head`. Keep the `def` line and the docstring as they are. Follow R2, R3, and R5 to R8.

### Step 11: Run

`.venv/bin/python -m ruff format src/finances/db/migrate.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 12: Run

`.venv/bin/python -m pytest tests/integration/test_migrate.py --no-cov -k "test_head_revision or test_upgrade_to_head"`

Expect: the last line contains `11 passed, 9 deselected`

### Step 13: Code

In `src/finances/db/migrate.py`, replace the last `raise NotImplementedError` with your implementation of `current_revision`. Keep the `def` line and the docstring as they are. Follow R4 to R8.

### Step 14: Run

`.venv/bin/python -m ruff format src/finances/db/migrate.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 15: Run

`.venv/bin/python -m ruff check --fix src/finances/db/migrate.py`

Expect: the last line is `All checks passed!`. A line saying an error was fixed is fine: it removes an import you did not use.

### Step 16: Run

`.venv/bin/python -m pytest tests/integration/test_migrate.py --no-cov`

Expect: the last line contains `20 passed`

### Step 17: Write

Add this entry at the end of `docs/progress.md`, after one blank line. Replace `YYYY-MM-DD` with today's date. If you did anything these steps did not ask for, describe it on the "Deviations" line in place of `None`.

```markdown
## Phase 2j: running migrations from code (YYYY-MM-DD)
- Built: `head_revision`, `upgrade_to_head`, and `current_revision` in `src/finances/db/migrate.py`; `db_url` and `db_engine` fixtures in `tests/conftest.py`; `tests/integration/test_migrate.py`. 228 tests pass. `migrate.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None
```

### Step 18: Run

`.venv/bin/python -m ruff format .`

Expect: `30 files left unchanged`. If it says a file was reformatted, that is fine: go on to step 19.

### Step 19: Run

`.venv/bin/python -m ruff format --check .`

Expect: `30 files already formatted`

### Step 20: Run

`.venv/bin/python -m ruff check .`

Expect: `All checks passed!`

### Step 21: Run

`.venv/bin/python -m pytest`

Expect: the last line contains `228 passed`, the output contains `Required test coverage of 85.0% reached`, and the row for `src/finances/db/migrate.py` ends with `100%`.

### Step 22: Run

`git grep -n --untracked -E "print\(|logging|except" -- src/finances/db/migrate.py`

Expect: no output.

### Step 23: Run

`git status --short`

Expect exactly these four lines and nothing else:

```
 M docs/progress.md
 M tests/conftest.py
?? src/finances/db/migrate.py
?? tests/integration/test_migrate.py
```

## If a Run step prints something else

| Step | Do this, then run the step again |
|---|---|
| any | If the output says `command not found`, `No such file`, or `No module named ruff` (or `pytest`), the command was not typed as written. Type it again starting with `.venv/bin/python`. If `.venv/bin/python` itself is missing, stop and report that; do not create a virtual environment |
| 6 | If it reports an import error or a syntax error, redo step 1 or step 2, whichever file the message names |
| 9 | Read the first failing test. `reads_the_migrations_folder` fails when the function returns a fixed value, or does not use `MIGRATIONS` at the time it is called. Change only the body of `head_revision` (or your private helper), then redo step 8 |
| 12 | Read the first failing test: its name says what is wrong (`another_folder` is R1 or the script location, `percent_sign` is R6, `configured_database` is R5, `other_backends` is R7). Change only the body of `upgrade_to_head` (or your private helper), then redo step 11 |
| 15 | The error names a line: fix that line, then redo step 14 |
| 16 | Read the first failing test. If its name starts with `test_current_revision` or `test_db_`, change only the body of `current_revision`, then redo steps 14 and 15. Otherwise you changed an earlier function: put it back |
| 19 | Run step 18 again |
| 20 | Run `.venv/bin/python -m ruff check --fix .`. If an error remains, it names a file and a line: fix that line |
| 21, another test file fails | The fixtures in `tests/conftest.py` were changed. Redo step 2, then step 3 |
| 21, `migrate.py` below `100%` | The "Missing" column lists lines of `migrate.py` that no test reaches. Remove that code, then redo steps 14 to 16 |
| 22 | Each line printed breaks R7, R8, or a rule. Rewrite that line without it, then redo steps 14 to 16 |
| 23 | A path that is not in the list is a file you must not have changed, or a database file a test left behind. For a file you changed, open it and undo your edit by hand. Report any database file. Do not use a git command |

## Final report

When step 23 matches, reply with the numbers 1 to 23, and after each Run step the last line of output you saw. Do not write "done" for a step you did not run.
