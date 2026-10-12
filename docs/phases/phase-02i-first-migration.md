# Phase 2i: the first migration

## Goal

Add Alembic to the project and write the first database migration: `upgrade` creates the `accounts` table, and `downgrade` removes it. The tests are given, and they compare the migrated database with the ORM class from Phase 2g. **You write both function bodies.** The work is to do the 24 steps in order.

## Read first

- `AGENTS.md`, sections "Running commands" and "Architecture rules"
- `src/finances/db/orm.py` (the `AccountRow` class: the migration must produce exactly this table)

## Starting state

- Phase 2h is done and committed. `git status --short` prints nothing.
- `.venv/bin/python -m pytest` ends with `191 passed`.
- `src/finances/db/` contains `__init__.py`, `orm.py`, and `engine.py`.
- The folder `src/finances/db/migrations/` does not exist yet, and Alembic is not installed.
- These commands are written for macOS. On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python`.

## Files

| Path | Action |
|---|---|
| `pyproject.toml` | replace whole content with the block in step 1 |
| `src/finances/db/migrations/env.py` | create from the block in step 5 (given in full) |
| `src/finances/db/migrations/versions/0001_accounts.py` | create from the block in step 9; you write both function bodies |
| `tests/integration/test_migrations.py` | create from the block in step 7 |
| `docs/progress.md` | add one entry at the end |

Do not create or modify any other file. There is no `alembic.ini`: the tests build the Alembic configuration in code.

## What to build

### Part 1: `upgrade`

- **R1.** It creates one table named `accounts` with these eight columns, in this order:

  | Column | Type | Null allowed |
  |---|---|---|
  | `id` | `sa.Integer()` | no |
  | `name` | `sa.String(100)` | no |
  | `institution` | `sa.String(100)` | no |
  | `type` | `sa.String(20)` | no |
  | `currency` | `sa.String(3)` | no |
  | `last4` | `sa.String(4)` | yes |
  | `is_active` | `sa.Boolean()` | no |
  | `created_at` | `sa.DateTime(timezone=True)` | no |

- **R2.** The primary key is `id`, and in the database the constraint is named `pk_accounts`.
- **R3.** `name` is unique, and in the database the constraint is named `uq_accounts_name`.
- **R4.** There is nothing else: no other constraint, no index, and no `server_default`. The default values (`"USD"`, `True`, the current time) are applied by the ORM class, not by the database.
- **R5.** The result must match `AccountRow` exactly. One of the tests asks Alembic to compare the migrated database with the ORM class and expects no difference.

### Part 2: `downgrade`

- **R6.** It removes the `accounts` table and nothing else.

### Both parts

- **R7.** The migration file imports only `sqlalchemy` and `alembic`. It must not import anything from `finances`: a migration is a frozen record of one change, and it must keep working when the ORM classes change later.
- **R8.** Do not change the four lines `revision`, `down_revision`, `branch_labels`, and `depends_on`.

### Alembic facts you will need

These are how the library works, not a recipe.

- `op.create_table("table_name", <column>, <column>, ..., <constraint>, <constraint>)` creates a table. Columns come first, in order, then constraints.
- A column is `sa.Column("column_name", <type>, nullable=False)`. Write `nullable=` on every column: without it a column allows null.
- A named primary key is `sa.PrimaryKeyConstraint("column_name", name="constraint_name")`.
- A named unique constraint is `sa.UniqueConstraint("column_name", name="constraint_name")`.
- `op.drop_table("table_name")` removes a table.

## Rules

- Do not change the test file or `env.py`. If a test fails, the migration is wrong.
- Do not change the given parts of the migration file: the docstring, the imports, the four revision lines, and the two `def` lines.
- Do not add other tables, columns, or migrations.
- Do not change `orm.py`, `engine.py`, or anything under `src/finances/domain/`.
- Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.

## How to work

- Each step is **one action**: **Write** (use the block given), **Code** (write code yourself), or **Run** (one command).
- Do all 24 steps, in order. Do not skip a Run step, and do not merge steps.
- After each Run step, compare the output with "Expect". If it differs, use the table under "If a Run step prints something else".
- Type every command exactly as written, starting with `.venv/bin/python`. Do not shorten it to `python`, `python3`, `pip`, `ruff`, `pytest`, or `alembic`.
- Do not activate the virtual environment and do not create one. `.venv/` already exists.

## Steps

### Step 1: Write

Replace the whole content of `pyproject.toml` with exactly this. The only change is the new line `"alembic>=1.13",`.

```toml
[project]
name = "finances"
version = "0.1.0"
description = "Local personal-finance tools for one household."
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "rich>=13",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "ruff>=0.5",
    "pytest-cov>=5",
]

[project.scripts]
fin = "finances.cli.main:app"

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100
target-version = "py311"
extend-exclude = ["docs"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib --cov=finances --cov-branch --cov-report=term-missing"

[tool.coverage.report]
fail_under = 85
show_missing = true
```

### Step 2: Run

`.venv/bin/python -c "from pathlib import Path; p = Path('pyproject.toml'); b = p.read_bytes(); p.write_bytes(b if b.endswith(b'\n') else b + b'\n')"`

Expect: no output. This makes sure the file ends with a newline.

### Step 3: Run

`.venv/bin/python -m pip install -e ".[dev]"`

Expect: the output contains `Successfully installed` and the word `alembic`. This step needs the network and can take a minute.

### Step 4: Run

`.venv/bin/python -c "import alembic; print(alembic.__version__.split('.')[0])"`

Expect: `1`

### Step 5: Write

Create `src/finances/db/migrations/env.py` with exactly this content. Create the folder `src/finances/db/migrations/` first; it does not exist yet.

```python
"""Alembic environment. The database URL comes from the Alembic Config, never from a file."""

from alembic import context

from finances.db.engine import get_engine
from finances.db.orm import Base

engine = get_engine(context.config.get_main_option("sqlalchemy.url"))
with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
```

### Step 6: Run

`.venv/bin/python -m ruff format src/finances/db/migrations/env.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 7: Write

Create `tests/integration/test_migrations.py` with exactly this content:

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import finances.db
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, Base, to_account
from finances.domain.models import AccountType

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
COLUMNS = [
    ("id", "INTEGER", False),
    ("name", "VARCHAR(100)", False),
    ("institution", "VARCHAR(100)", False),
    ("type", "VARCHAR(20)", False),
    ("currency", "VARCHAR(3)", False),
    ("last4", "VARCHAR(4)", True),
    ("is_active", "BOOLEAN", False),
    ("created_at", "DATETIME", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


def table_names(url: str) -> list[str]:
    engine = get_engine(url)
    names = sorted(inspect(engine).get_table_names())
    engine.dispose()
    return names


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def migrated(url: str) -> str:
    command.upgrade(make_config(url), "head")
    return url


def test_there_is_one_migration_named_0001(url: str) -> None:
    scripts = ScriptDirectory.from_config(make_config(url))
    assert scripts.get_heads() == ["0001"]
    assert scripts.get_base() == "0001"


def test_migration_file_is_self_contained() -> None:
    source = (MIGRATIONS / "versions" / "0001_accounts.py").read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source


def test_created_at_is_declared_with_a_time_zone() -> None:
    source = (MIGRATIONS / "versions" / "0001_accounts.py").read_text(encoding="utf-8")
    assert "DateTime(timezone=True)" in source


def test_upgrade_creates_the_accounts_table(migrated: str) -> None:
    assert table_names(migrated) == ["accounts", "alembic_version"]


def test_upgrade_records_the_revision(migrated: str) -> None:
    engine = get_engine(migrated)
    with engine.connect() as connection:
        versions = connection.execute(text("SELECT version_num FROM alembic_version")).all()
    engine.dispose()
    assert [row[0] for row in versions] == ["0001"]


def test_columns_types_and_nulls(migrated: str) -> None:
    engine = get_engine(migrated)
    columns = inspect(engine).get_columns("accounts")
    engine.dispose()
    found = [(column["name"], str(column["type"]), column["nullable"]) for column in columns]
    assert found == COLUMNS


def test_no_server_defaults(migrated: str) -> None:
    engine = get_engine(migrated)
    columns = inspect(engine).get_columns("accounts")
    engine.dispose()
    assert [column["default"] for column in columns] == [None] * 8


def test_primary_key_is_named(migrated: str) -> None:
    engine = get_engine(migrated)
    primary_key = inspect(engine).get_pk_constraint("accounts")
    engine.dispose()
    assert primary_key["name"] == "pk_accounts"
    assert primary_key["constrained_columns"] == ["id"]


def test_name_is_the_only_unique_constraint(migrated: str) -> None:
    engine = get_engine(migrated)
    uniques = inspect(engine).get_unique_constraints("accounts")
    engine.dispose()
    assert [(unique["name"], unique["column_names"]) for unique in uniques] == [
        ("uq_accounts_name", ["name"])
    ]


def test_no_indexes_and_no_foreign_keys(migrated: str) -> None:
    engine = get_engine(migrated)
    inspector = inspect(engine)
    indexes = inspector.get_indexes("accounts")
    foreign_keys = inspector.get_foreign_keys("accounts")
    engine.dispose()
    assert indexes == []
    assert foreign_keys == []


def test_migrated_database_matches_the_orm(migrated: str) -> None:
    engine = get_engine(migrated)
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert differences == []


def test_upgrade_twice_changes_nothing(migrated: str) -> None:
    command.upgrade(make_config(migrated), "head")
    assert table_names(migrated) == ["accounts", "alembic_version"]


def test_the_table_works_with_the_orm(migrated: str) -> None:
    engine = get_engine(migrated)
    with session_scope(engine) as session:
        session.add(AccountRow(name="Test Checking", institution="Test Bank", type="checking"))
    with session_scope(engine) as session:
        account = to_account(session.query(AccountRow).one())
    engine.dispose()
    assert account.id == 1
    assert account.type is AccountType.CHECKING
    assert account.currency == "USD"
    assert account.is_active is True


def test_the_table_rejects_a_duplicate_name(migrated: str) -> None:
    engine = get_engine(migrated)
    with session_scope(engine) as session:
        session.add(AccountRow(name="Test Checking", institution="Test Bank", type="checking"))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(AccountRow(name="Test Checking", institution="Other Bank", type="savings"))
    engine.dispose()


def test_upgrade_writes_only_the_database_file(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    command.upgrade(make_config(url), "head")
    assert [path.name for path in tmp_path.iterdir()] == ["test.db"]


def test_downgrade_removes_the_accounts_table(migrated: str) -> None:
    command.downgrade(make_config(migrated), "base")
    assert table_names(migrated) == ["alembic_version"]


def test_downgrade_then_upgrade_restores_the_table(migrated: str) -> None:
    config = make_config(migrated)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    assert table_names(migrated) == ["accounts", "alembic_version"]
```

### Step 8: Run

`.venv/bin/python -m ruff format tests/integration/test_migrations.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 9: Write

Create `src/finances/db/migrations/versions/0001_accounts.py` with exactly this content. Create the folder `src/finances/db/migrations/versions/` first.

```python
"""Create the accounts table."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    raise NotImplementedError


def downgrade() -> None:
    raise NotImplementedError
```

### Step 10: Run

`.venv/bin/python -m pytest tests/integration/test_migrations.py --no-cov`

Expect: the last line contains `2 failed, 2 passed, 13 errors`. The tests fail because the migration is not written yet.

### Step 11: Code

In `src/finances/db/migrations/versions/0001_accounts.py`, replace the first `raise NotImplementedError` with your implementation of `upgrade`. Follow Part 1 (R1 to R5).

### Step 12: Run

`.venv/bin/python -m ruff format src/finances/db/migrations/versions/0001_accounts.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 13: Run

`.venv/bin/python -m pytest tests/integration/test_migrations.py --no-cov -k "not downgrade"`

Expect: the last line contains `15 passed, 2 deselected`

### Step 14: Code

In `src/finances/db/migrations/versions/0001_accounts.py`, replace the remaining `raise NotImplementedError` with your implementation of `downgrade`. Follow Part 2 (R6).

### Step 15: Run

`.venv/bin/python -m ruff format src/finances/db/migrations/versions/0001_accounts.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 16: Run

`.venv/bin/python -m ruff check --fix src/finances/db/migrations`

Expect: the last line is `All checks passed!`.

### Step 17: Run

`.venv/bin/python -m pytest tests/integration/test_migrations.py --no-cov`

Expect: the last line contains `17 passed`

### Step 18: Write

Add this entry at the end of `docs/progress.md`, after one blank line. Replace `YYYY-MM-DD` with today's date. If you did anything these steps did not ask for, describe it on the "Deviations" line in place of `None`.

```markdown
## Phase 2i: the first migration (YYYY-MM-DD)
- Built: Alembic dependency; `src/finances/db/migrations/env.py`; migration `0001` creating the `accounts` table; `tests/integration/test_migrations.py`. 208 tests pass.
- Deviations from spec (and why): None
- Follow-ups / known issues: None
```

### Step 19: Run

`.venv/bin/python -m ruff format .`

Expect: `28 files left unchanged`. If it says a file was reformatted, that is fine: go on to step 20.

### Step 20: Run

`.venv/bin/python -m ruff format --check .`

Expect: `28 files already formatted`

### Step 21: Run

`.venv/bin/python -m ruff check .`

Expect: `All checks passed!`

### Step 22: Run

`.venv/bin/python -m pytest`

Expect: the last line contains `208 passed`, and the output contains `Required test coverage of 85.0% reached`.

### Step 23: Run

`git grep -n --untracked -E "finances|server_default|create_index|print\(" -- src/finances/db/migrations/versions`

Expect: no output.

### Step 24: Run

`git status --short`

Expect exactly these four lines and nothing else:

```
 M docs/progress.md
 M pyproject.toml
?? src/finances/db/migrations/
?? tests/integration/test_migrations.py
```

## If a Run step prints something else

| Step | Do this, then run the step again |
|---|---|
| any | If the output says `command not found`, `No such file`, or `No module named ruff` (or `pytest`, or `pip`), the command was not typed as written. Type it again starting with `.venv/bin/python`. If `.venv/bin/python` itself is missing, stop and report that; do not create a virtual environment |
| 3 | If it cannot reach the network, stop and report that. If it reports an error in `pyproject.toml`, redo steps 1 and 2 |
| 4 | Run step 3 again |
| 10 | If it reports an import error or a syntax error in `env.py` or the migration file, redo step 5 or step 9. If it reports `No module named 'alembic'`, redo step 3 |
| 13 | Read the first failing test: its name says what is wrong (`columns_types_and_nulls` and `time_zone` are R1, `primary_key` is R2, `unique` is R3, `server_defaults` and `indexes` are R4, `matches_the_orm` is R5 and its message lists each difference). Change only the body of `upgrade`, then redo step 12 |
| 16 | The error names a line: fix that line, then redo step 15 |
| 17 | Read the first failing test. If its name contains `downgrade`, change only the body of `downgrade`, then redo steps 15 and 16. Otherwise you changed `upgrade`: put it back |
| 20 | Run step 19 again |
| 21 | Run `.venv/bin/python -m ruff check --fix .`. If an error remains, it names a file and a line: fix that line |
| 23 | Each line printed breaks R4 or R7. Rewrite that line without it, then redo steps 15 to 17 |
| 24 | A path that is not in the list is a file you must not have changed, or a database file a test left behind. For a file you changed, open it and undo your edit by hand. Report any database file. Do not use a git command |

## Final report

When step 24 matches, reply with the numbers 1 to 24, and after each Run step the last line of output you saw. Do not write "done" for a step you did not run.
