# Phase 2g: `accounts` table and `to_account`

## Goal

Add SQLAlchemy to the project, describe the `accounts` table as an ORM class, and write the function that turns a table row into the `Account` dataclass. The tests are given. **You write seven columns and one function body.** The work is to do the 23 steps in order.

This phase is larger than the earlier ones: it has two Code steps, a new dependency, and four files.

## Read first

- `AGENTS.md`, sections "Running commands" and "Architecture rules"
- `src/finances/domain/models.py`

## Starting state

- Phase 2f is done and committed. `git status --short` prints nothing.
- `.venv/bin/python -m pytest` ends with `122 passed`.
- `src/finances/domain/models.py` contains `AccountType`, `Account`, and `validate_last4`.
- The folder `src/finances/db/` does not exist yet, and SQLAlchemy is not installed.
- These commands are written for macOS. On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python`.

## Files

| Path | Action |
|---|---|
| `pyproject.toml` | replace whole content with the block in step 1 |
| `src/finances/db/__init__.py` | create, empty |
| `src/finances/db/orm.py` | create from the block in step 8; you write the columns and the function body |
| `tests/unit/test_orm.py` | create from the block in step 6 |
| `docs/progress.md` | add one entry at the end |

Do not create or modify any other file.

## What to build

### Part 1: the columns of `AccountRow`

The class, its table name, and its `id` column are given in step 8. Add the other seven columns below `id`, in this order:

| Column | Python type | Column type | Null allowed | Other |
|---|---|---|---|---|
| `name` | `str` | `String(100)` | no | unique |
| `institution` | `str` | `String(100)` | no | |
| `type` | `str` | `String(20)` | no | |
| `currency` | `str` | `String(3)` | no | Python default `"USD"` |
| `last4` | `str \| None` | `String(4)` | yes | |
| `is_active` | `bool` | `Boolean` | no | Python default `True` |
| `created_at` | `datetime` | `DateTime(timezone=True)` | no | Python default: the current time in UTC |

- **R1.** Each column is written in the same style as `id`: `name: Mapped[<Python type>] = mapped_column(...)`.
- **R2.** `type` is plain text. It stores the value of an `AccountType` member, such as `"checking"`. Do not use SQLAlchemy's `Enum` type.
- **R3.** A "Python default" is passed as `default=...` to `mapped_column`. Do not use `server_default`.
- **R4.** The default of `created_at` is a function that returns `datetime.now(UTC)`, so the time has a time zone. Do not use `datetime.utcnow`, which returns a time without one.

Example of one finished column: `currency: Mapped[str] = mapped_column(String(3), default="USD")`

### Part 2: `to_account`

```python
def to_account(row: AccountRow) -> Account
```

- **R5.** It returns an `Account` whose eight fields have the values of the row's eight columns.
- **R6.** `type` is converted from text to the enum with `AccountType(row.type)`. A row whose `type` is not one of the four values therefore raises `ValueError`.
- **R7.** SQLite gives back `created_at` without a time zone. If `row.created_at.tzinfo` is `None`, use `row.created_at.replace(tzinfo=UTC)`. If it already has a time zone, keep it unchanged.

### Both parts

- **R8.** From this project, `orm.py` imports only `finances.domain.models`.

## Rules

- Do not change the test file. If a test fails, `orm.py` is wrong.
- Do not change the given parts of `orm.py`: the module docstring, `NAMING_CONVENTION`, `Base`, the `AccountRow` class line, its docstring, `__tablename__`, and the `id` column.
- Do not add other classes, tables, or functions.
- Do not create a database, an engine, or a session in this phase.
- Do not change anything under `src/finances/domain/`.
- Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.

## How to work

- Each step is **one action**: **Write** (use the block given), **Code** (write code yourself), or **Run** (one command).
- Do all 23 steps, in order. Do not skip a Run step, and do not merge steps.
- After each Run step, compare the output with "Expect". If it differs, use the table under "If a Run step prints something else".
- Type every command exactly as written, starting with `.venv/bin/python`. Do not shorten it to `python`, `python3`, `pip`, `ruff`, or `pytest`.
- Do not activate the virtual environment and do not create one. `.venv/` already exists.

## Steps

### Step 1: Write

Replace the whole content of `pyproject.toml` with exactly this. The only change is the new line `"sqlalchemy>=2.0",`.

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

Expect: the output contains `Successfully installed` and the word `sqlalchemy`. This step needs the network and can take a minute.

### Step 4: Run

`.venv/bin/python -c "import sqlalchemy; print(sqlalchemy.__version__.split('.')[0])"`

Expect: `2`

### Step 5: Write

Create an empty file `src/finances/db/__init__.py`. Create the folder `src/finances/db/` first; it does not exist yet.

### Step 6: Write

Create `tests/unit/test_orm.py` with exactly this content:

```python
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Boolean, DateTime, Enum, Integer, String, UniqueConstraint

from finances.db.orm import AccountRow, Base, to_account
from finances.domain.models import Account, AccountType

TABLE = AccountRow.__table__
CREATED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
COLUMN_NAMES = [
    "id",
    "name",
    "institution",
    "type",
    "currency",
    "last4",
    "is_active",
    "created_at",
]


def make_row(**changes: object) -> AccountRow:
    values = {
        "id": 3,
        "name": "Test Card",
        "institution": "Test Bank",
        "type": "credit_card",
        "currency": "USD",
        "last4": "4321",
        "is_active": True,
        "created_at": CREATED,
    }
    values.update(changes)
    return AccountRow(**values)


def test_table_is_named_accounts() -> None:
    assert TABLE.name == "accounts"
    assert Base.metadata.tables["accounts"] is TABLE


def test_columns_in_order() -> None:
    assert [column.name for column in TABLE.columns] == COLUMN_NAMES


@pytest.mark.parametrize(
    ("name", "type_class", "length"),
    [
        ("id", Integer, None),
        ("name", String, 100),
        ("institution", String, 100),
        ("type", String, 20),
        ("currency", String, 3),
        ("last4", String, 4),
        ("is_active", Boolean, None),
        ("created_at", DateTime, None),
    ],
)
def test_column_type(name: str, type_class: type, length: int | None) -> None:
    column_type = TABLE.columns[name].type
    assert isinstance(column_type, type_class)
    assert not isinstance(column_type, Enum)
    if length is not None:
        assert column_type.length == length


@pytest.mark.parametrize("name", COLUMN_NAMES)
def test_only_last4_allows_null(name: str) -> None:
    assert TABLE.columns[name].nullable is (name == "last4")


def test_id_is_the_only_primary_key() -> None:
    assert [column.name for column in TABLE.primary_key.columns] == ["id"]


def test_name_is_the_only_unique_column() -> None:
    unique = [
        [column.name for column in constraint.columns]
        for constraint in TABLE.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    assert unique == [["name"]]


def test_currency_defaults_to_usd() -> None:
    assert TABLE.columns["currency"].default.arg == "USD"


def test_is_active_defaults_to_true() -> None:
    assert TABLE.columns["is_active"].default.arg is True


def test_created_at_keeps_the_time_zone() -> None:
    assert TABLE.columns["created_at"].type.timezone is True


def test_created_at_defaults_to_now_in_utc() -> None:
    value = TABLE.columns["created_at"].default.arg(None)
    assert isinstance(value, datetime)
    assert value.utcoffset() == timedelta(0)
    assert abs(datetime.now(UTC) - value) < timedelta(minutes=1)


@pytest.mark.parametrize("name", ["id", "name", "institution", "type", "last4"])
def test_columns_without_a_default(name: str) -> None:
    assert TABLE.columns[name].default is None


@pytest.mark.parametrize("name", COLUMN_NAMES)
def test_no_server_defaults(name: str) -> None:
    assert TABLE.columns[name].server_default is None


def test_to_account_copies_every_value() -> None:
    assert to_account(make_row()) == Account(
        id=3,
        name="Test Card",
        institution="Test Bank",
        type=AccountType.CREDIT_CARD,
        currency="USD",
        last4="4321",
        is_active=True,
        created_at=CREATED,
    )


def test_to_account_returns_an_account() -> None:
    assert type(to_account(make_row())) is Account


@pytest.mark.parametrize("member", list(AccountType))
def test_to_account_converts_type_to_the_enum(member: AccountType) -> None:
    assert to_account(make_row(type=member.value)).type is member


def test_to_account_rejects_an_unknown_type() -> None:
    with pytest.raises(ValueError):
        to_account(make_row(type="brokerage"))


def test_to_account_keeps_a_missing_last4() -> None:
    assert to_account(make_row(last4=None)).last4 is None


def test_to_account_keeps_inactive() -> None:
    assert to_account(make_row(is_active=False)).is_active is False


def test_to_account_treats_a_naive_time_as_utc() -> None:
    naive = datetime(2026, 1, 2, 3, 4, 5)
    account = to_account(make_row(created_at=naive))
    assert account.created_at == CREATED
    assert account.created_at.utcoffset() == timedelta(0)


def test_to_account_keeps_an_aware_time_unchanged() -> None:
    plus_five = timezone(timedelta(hours=5))
    aware = datetime(2026, 1, 2, 8, 4, 5, tzinfo=plus_five)
    account = to_account(make_row(created_at=aware))
    assert account.created_at == CREATED
    assert account.created_at.utcoffset() == timedelta(hours=5)
```

### Step 7: Run

`.venv/bin/python -m ruff format tests/unit/test_orm.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 8: Write

Create `src/finances/db/orm.py` with exactly this content:

```python
"""SQLAlchemy ORM tables. From this project, this module imports only the domain models."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from finances.domain.models import Account, AccountType

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class of every ORM table."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class AccountRow(Base):
    """One row of the accounts table."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)


def to_account(row: AccountRow) -> Account:
    """Return the domain Account for a row of the accounts table."""
    raise NotImplementedError
```

### Step 9: Run

`.venv/bin/python -m pytest tests/unit/test_orm.py --no-cov`

Expect: the last line contains `42 failed, 6 passed`. Most tests fail because the columns and the function are not written yet.

### Step 10: Code

In `src/finances/db/orm.py`, add the seven columns to `AccountRow`, below the `id` line. Follow Part 1 (R1 to R4).

### Step 11: Run

`.venv/bin/python -m ruff format src/finances/db/orm.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 12: Run

`.venv/bin/python -m pytest tests/unit/test_orm.py --no-cov -k "not to_account"`

Expect: the last line contains `37 passed, 11 deselected`

### Step 13: Code

In `src/finances/db/orm.py`, replace the line `raise NotImplementedError` with your implementation of `to_account`. Keep the `def` line and the docstring as they are. Follow Part 2 (R5 to R7).

### Step 14: Run

`.venv/bin/python -m ruff format src/finances/db/orm.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 15: Run

`.venv/bin/python -m ruff check --fix src/finances/db/orm.py`

Expect: the last line is `All checks passed!`. A line saying an error was fixed is fine: it removes an import you did not use.

### Step 16: Run

`.venv/bin/python -m pytest tests/unit/test_orm.py --no-cov`

Expect: the last line contains `48 passed`

### Step 17: Write

Add this entry at the end of `docs/progress.md`, after one blank line. Replace `YYYY-MM-DD` with today's date. If you did anything these steps did not ask for, describe it on the "Deviations" line in place of `None`.

```markdown
## Phase 2g: accounts table and to_account (YYYY-MM-DD)
- Built: SQLAlchemy dependency; `Base`, `AccountRow`, and `to_account` in `src/finances/db/orm.py`; `tests/unit/test_orm.py`. 170 tests pass. `orm.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None
```

### Step 18: Run

`.venv/bin/python -m ruff format .`

Expect: `23 files left unchanged`. If it says a file was reformatted, that is fine: go on to step 19.

### Step 19: Run

`.venv/bin/python -m ruff format --check .`

Expect: `23 files already formatted`

### Step 20: Run

`.venv/bin/python -m ruff check .`

Expect: `All checks passed!`

### Step 21: Run

`.venv/bin/python -m pytest`

Expect: the last line contains `170 passed`, the output contains `Required test coverage of 85.0% reached`, and the row for `src/finances/db/orm.py` ends with `100%`.

### Step 22: Run

`git grep -n --untracked -E "server_default|utcnow|Enum|create_engine|create_all|Session" -- src/finances/db`

Expect: no output.

### Step 23: Run

`git status --short`

Expect exactly these four lines and nothing else:

```
 M docs/progress.md
 M pyproject.toml
?? src/finances/db/
?? tests/unit/test_orm.py
```

## If a Run step prints something else

| Step | Do this, then run the step again |
|---|---|
| any | If the output says `command not found`, `No such file`, or `No module named ruff` (or `pytest`, or `pip`), the command was not typed as written. Type it again starting with `.venv/bin/python`. If `.venv/bin/python` itself is missing, stop and report that; do not create a virtual environment |
| 3 | If it cannot reach the network, stop and report that. If it reports an error in `pyproject.toml`, redo steps 1 and 2 |
| 4 | Run step 3 again |
| 9 | If it reports an import error or a syntax error, redo step 8. If it reports `No module named 'sqlalchemy'`, redo step 3 |
| 12 | Read the first failing test: its name says which column or property is wrong. Change only that column, then redo step 11. If the output is an error raised while importing `orm.py`, the last column you wrote has a mistake: compare it with the example in Part 1 |
| 15 | The error names a line: fix that line, then redo step 14 |
| 16 | Read the first failing test: it shows the input and what was expected. Change only the body of `to_account`, then redo steps 14 and 15 |
| 19 | Run step 18 again |
| 20 | Run `.venv/bin/python -m ruff check --fix .`. If an error remains, it names a file and a line: fix that line |
| 21, `orm.py` below `100%` | The "Missing" column lists lines of `orm.py` that no test reaches. Remove that code, then redo steps 14 to 16 |
| 22 | Each line printed breaks R2, R3, R4, or the rule against creating a database. Rewrite that line without it, then redo steps 14 to 16 |
| 23 | A path that is not in the list is a file you must not have changed. Open it and undo your edit by hand. Do not use a git command |

## Final report

When step 23 matches, reply with the numbers 1 to 23, and after each Run step the last line of output you saw. Do not write "done" for a step you did not run.
