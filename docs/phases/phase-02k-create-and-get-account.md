# Phase 2k: `get_account_by_name` and `create_account`

## Goal

Write the first two repository functions: `get_account_by_name` finds an account, and `create_account` adds one. The tests are given, and they run against a migrated temporary database. **You write both function bodies.** The work is to do the 21 steps in order.

## Read first

- `AGENTS.md`, sections "Running commands" and "Architecture rules"
- `src/finances/db/orm.py` (`AccountRow`, `to_account`)
- `src/finances/domain/models.py` (`Account`, `AccountType`, `validate_last4`)

## Starting state

- Phase 2j is done and committed. `git status --short` prints nothing.
- `.venv/bin/python -m pytest` ends with `228 passed`.
- `tests/conftest.py` provides the `db_engine` fixture: an engine for a temporary database that already has the `accounts` table.
- These commands are written for macOS. On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python`.

## Files

| Path | Action |
|---|---|
| `src/finances/db/repositories.py` | create from the block in step 1; you write both function bodies |
| `tests/integration/test_repositories.py` | create from the block in step 3 |
| `docs/progress.md` | add one entry at the end |

Do not create or modify any other file.

## What to build

Every requirement below is checked by at least one given test. If the tests pass and the coverage step passes, you are done: do not add checks that no requirement asks for.

### Part 1: `get_account_by_name`

```python
def get_account_by_name(session: Session, name: str) -> Account | None
```

- **R1.** It returns the account whose name equals `name`, ignoring upper and lower case and ignoring spaces at either end of `name`. `"  test CHECKING "` finds the account named `"Test Checking"`.
- **R2.** The whole name must match: `"Test"` does not find `"Test Checking"`. When no account matches, it returns `None`.

### Part 2: `create_account`

```python
def create_account(
    session: Session,
    name: str,
    institution: str,
    account_type: AccountType | str,
    currency: str = "USD",
    last4: str | None = None,
) -> Account
```

- **R3.** It adds one row to the `accounts` table and returns it as an `Account`, with its new `id`. `name` and `institution` are stored without spaces at either end.
- **R4.** A `name` that is empty after removing those spaces raises `ValueError("account name must not be empty")`. An `institution` that is empty the same way raises `ValueError("institution must not be empty")`.
- **R5.** If an account with that name already exists (compared as in R1), it raises `AccountExistsError("an account with this name already exists")`. Find this out by looking first, not by letting the database reject the insert: after the error, the same session must still work.
- **R6.** `last4` is checked with `validate_last4`. Its `ValueError` is not caught.
- **R7.** `account_type` may be an `AccountType` member or its text, such as `"savings"`. `AccountType(account_type)` accepts both and raises `ValueError` for anything else. The row stores the text value.
- **R8.** When any of R4 to R7 raises, nothing has been added to the table. When it succeeds, the function has sent the row to the database with `session.flush()` so that `id` is filled in, and has **not** committed: the caller's `session_scope` commits.

### SQLAlchemy facts you will need

These are how the library works, not a recipe.

- `select(AccountRow).where(<condition>)` builds a query. `session.scalars(<query>).first()` runs it and returns the first `AccountRow`, or `None`.
- `func.lower(AccountRow.name)` is the name in lower case, computed by the database. Compare it with a lower-case Python string.
- `AccountRow(name=..., institution=..., type=..., currency=..., last4=...)` makes a row. `is_active` and `created_at` have defaults.
- `session.add(row)` schedules the row. `session.flush()` sends it to the database inside the current transaction and fills in `row.id`.
- `to_account(row)` turns a row into an `Account`.

## Rules

- Do not change the test file. If a test fails, `repositories.py` is wrong.
- Do not change the given parts of `repositories.py`: the module docstring, the `AccountExistsError` class, the two `def` lines with their parameters, and the two docstrings.
- Do not call `session.commit()`, `session.rollback()`, or `session.close()` in `repositories.py`.
- Do not print or log anything.
- Do not change any other source file or test file.
- Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.

## How to work

- Each step is **one action**: **Write** (use the block given), **Code** (write code yourself), or **Run** (one command).
- Do all 21 steps, in order. Do not skip a Run step, and do not merge steps.
- After each Run step, compare the output with "Expect". If it differs, use the table under "If a Run step prints something else".
- Type every command exactly as written, starting with `.venv/bin/python`. Do not shorten it to `python`, `python3`, `pip`, `ruff`, or `pytest`.
- Do not activate the virtual environment and do not create one. `.venv/` already exists.

## Steps

### Step 1: Write

Create `src/finances/db/repositories.py` with exactly this content:

```python
"""Database reads and writes. Functions take a Session and return domain objects."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finances.db.orm import AccountRow, to_account
from finances.domain.models import Account, AccountType, validate_last4


class AccountExistsError(Exception):
    """Raised when an account with the same name already exists."""


def get_account_by_name(session: Session, name: str) -> Account | None:
    """Return the account with this name, ignoring case and outer spaces, or None."""
    raise NotImplementedError


def create_account(
    session: Session,
    name: str,
    institution: str,
    account_type: AccountType | str,
    currency: str = "USD",
    last4: str | None = None,
) -> Account:
    """Add an account and return it. The caller commits."""
    raise NotImplementedError
```

### Step 2: Run

`.venv/bin/python -m ruff format src/finances/db/repositories.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 3: Write

Create `tests/integration/test_repositories.py` with exactly this content:

```python
from datetime import timedelta

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import AccountRow
from finances.db.repositories import AccountExistsError, create_account, get_account_by_name
from finances.domain.models import Account, AccountType

EXISTS = "an account with this name already exists"


def add_row(engine: Engine, name: str, **values: object) -> None:
    row = {"name": name, "institution": "Test Bank", "type": "checking"}
    row.update(values)
    with session_scope(engine) as session:
        session.add(AccountRow(**row))


def count_rows(engine: Engine) -> int:
    with session_scope(engine) as session:
        return session.scalar(select(func.count()).select_from(AccountRow))


def stored_names(engine: Engine) -> list[str]:
    with session_scope(engine) as session:
        return list(session.scalars(select(AccountRow.name).order_by(AccountRow.id)))


def test_get_account_by_name_returns_none_when_there_are_no_accounts(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        assert get_account_by_name(session, "Test Checking") is None


def test_get_account_by_name_finds_the_account(db_engine: Engine) -> None:
    add_row(db_engine, "Test Checking", type="savings", last4="1234")
    with session_scope(db_engine) as session:
        account = get_account_by_name(session, "Test Checking")
    assert type(account) is Account
    assert account.id == 1
    assert account.name == "Test Checking"
    assert account.institution == "Test Bank"
    assert account.type is AccountType.SAVINGS
    assert account.last4 == "1234"


@pytest.mark.parametrize(
    "asked",
    ["test checking", "TEST CHECKING", "tEsT cHeCkInG", "  Test Checking", "Test Checking\n"],
)
def test_get_account_by_name_ignores_case_and_outer_spaces(db_engine: Engine, asked: str) -> None:
    add_row(db_engine, "Test Checking")
    with session_scope(db_engine) as session:
        account = get_account_by_name(session, asked)
    assert account is not None
    assert account.name == "Test Checking"


@pytest.mark.parametrize("asked", ["Test", "Checking", "Test Checking 2", "TestChecking", ""])
def test_get_account_by_name_needs_the_whole_name(db_engine: Engine, asked: str) -> None:
    add_row(db_engine, "Test Checking")
    with session_scope(db_engine) as session:
        assert get_account_by_name(session, asked) is None


def test_get_account_by_name_picks_the_right_one(db_engine: Engine) -> None:
    add_row(db_engine, "Test Checking")
    add_row(db_engine, "Test Savings", type="savings")
    add_row(db_engine, "Test Card", type="credit_card")
    with session_scope(db_engine) as session:
        account = get_account_by_name(session, "test savings")
    assert account.id == 2
    assert account.type is AccountType.SAVINGS


def test_create_account_returns_the_new_account(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        account = create_account(session, "Test Checking", "Test Bank", AccountType.CHECKING)
    assert type(account) is Account
    assert account.id == 1
    assert account.name == "Test Checking"
    assert account.institution == "Test Bank"
    assert account.type is AccountType.CHECKING
    assert account.currency == "USD"
    assert account.last4 is None
    assert account.is_active is True
    assert account.created_at.utcoffset() == timedelta(0)


def test_create_account_stores_the_row(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Card", "Test Bank", AccountType.CREDIT_CARD, "CAD", "0042")
    with session_scope(db_engine) as session:
        row = session.scalars(select(AccountRow)).one()
        found = (row.name, row.institution, row.type, row.currency, row.last4, row.is_active)
    assert found == ("Test Card", "Test Bank", "credit_card", "CAD", "0042", True)


def test_create_account_gives_each_account_its_own_id(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        first = create_account(session, "Test Checking", "Test Bank", AccountType.CHECKING)
        second = create_account(session, "Test Savings", "Test Bank", AccountType.SAVINGS)
    assert (first.id, second.id) == (1, 2)


def test_create_account_does_not_commit(db_engine: Engine) -> None:
    session = Session(db_engine)
    account = create_account(session, "Test Checking", "Test Bank", AccountType.CHECKING)
    assert account.id == 1
    session.rollback()
    session.close()
    assert count_rows(db_engine) == 0


def test_create_account_removes_outer_spaces(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        account = create_account(session, "  Test Checking ", " Test Bank\n", AccountType.CHECKING)
    assert (account.name, account.institution) == ("Test Checking", "Test Bank")
    assert stored_names(db_engine) == ["Test Checking"]


@pytest.mark.parametrize("name", ["", "   ", "\n\t"])
def test_create_account_rejects_an_empty_name(db_engine: Engine, name: str) -> None:
    with session_scope(db_engine) as session:
        with pytest.raises(ValueError) as excinfo:
            create_account(session, name, "Test Bank", AccountType.CHECKING)
    assert str(excinfo.value) == "account name must not be empty"
    assert count_rows(db_engine) == 0


@pytest.mark.parametrize("institution", ["", "   "])
def test_create_account_rejects_an_empty_institution(db_engine: Engine, institution: str) -> None:
    with session_scope(db_engine) as session:
        with pytest.raises(ValueError) as excinfo:
            create_account(session, "Test Checking", institution, AccountType.CHECKING)
    assert str(excinfo.value) == "institution must not be empty"
    assert count_rows(db_engine) == 0


@pytest.mark.parametrize("name", ["Test Checking", "test checking", "TEST CHECKING", " Test Checking "])
def test_create_account_rejects_a_duplicate_name(db_engine: Engine, name: str) -> None:
    add_row(db_engine, "Test Checking")
    with session_scope(db_engine) as session:
        with pytest.raises(AccountExistsError) as excinfo:
            create_account(session, name, "Other Bank", AccountType.SAVINGS)
    assert str(excinfo.value) == EXISTS
    assert stored_names(db_engine) == ["Test Checking"]


def test_create_account_rejects_a_duplicate_in_the_same_session(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Checking", "Test Bank", AccountType.CHECKING)
        with pytest.raises(AccountExistsError):
            create_account(session, "test checking", "Test Bank", AccountType.CHECKING)
    assert stored_names(db_engine) == ["Test Checking"]


def test_the_session_still_works_after_a_duplicate(db_engine: Engine) -> None:
    add_row(db_engine, "Test Checking")
    with session_scope(db_engine) as session:
        with pytest.raises(AccountExistsError):
            create_account(session, "Test Checking", "Test Bank", AccountType.CHECKING)
        create_account(session, "Test Savings", "Test Bank", AccountType.SAVINGS)
    assert stored_names(db_engine) == ["Test Checking", "Test Savings"]


def test_account_exists_error_is_not_a_value_error() -> None:
    assert not issubclass(AccountExistsError, ValueError)


@pytest.mark.parametrize("member", list(AccountType))
def test_create_account_accepts_the_type_as_text(db_engine: Engine, member: AccountType) -> None:
    with session_scope(db_engine) as session:
        account = create_account(session, "Test Account", "Test Bank", member.value)
    assert account.type is member
    with session_scope(db_engine) as session:
        assert session.scalars(select(AccountRow.type)).one() == member.value


def test_create_account_rejects_an_unknown_type(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        with pytest.raises(ValueError):
            create_account(session, "Test Account", "Test Bank", "brokerage")
    assert count_rows(db_engine) == 0


@pytest.mark.parametrize("last4", ["123", "12345", "12a4", " 1234"])
def test_create_account_rejects_a_bad_last4(db_engine: Engine, last4: str) -> None:
    with session_scope(db_engine) as session:
        with pytest.raises(ValueError) as excinfo:
            create_account(session, "Test Account", "Test Bank", AccountType.OTHER, last4=last4)
    assert str(excinfo.value) == "last4 must be exactly 4 digits"
    assert count_rows(db_engine) == 0
```

### Step 4: Run

`.venv/bin/python -m ruff format tests/integration/test_repositories.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 5: Run

`.venv/bin/python -m pytest tests/integration/test_repositories.py --no-cov`

Expect: the last line contains `38 failed, 1 passed`. The tests fail because the functions are not written yet.

### Step 6: Code

In `src/finances/db/repositories.py`, replace the first `raise NotImplementedError` with your implementation of `get_account_by_name`. Keep the `def` line and the docstring as they are. Follow Part 1 (R1 and R2).

### Step 7: Run

`.venv/bin/python -m ruff format src/finances/db/repositories.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 8: Run

`.venv/bin/python -m pytest tests/integration/test_repositories.py --no-cov -k "test_get_account_by_name"`

Expect: the last line contains `13 passed, 26 deselected`

### Step 9: Code

In `src/finances/db/repositories.py`, replace the remaining `raise NotImplementedError` with your implementation of `create_account`. Keep the `def` lines and the docstring as they are. Follow Part 2 (R3 to R8).

### Step 10: Run

`.venv/bin/python -m ruff format src/finances/db/repositories.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 11: Run

`.venv/bin/python -m ruff check --fix src/finances/db/repositories.py`

Expect: the last line is `All checks passed!`. A line saying an error was fixed is fine: it removes an import you did not use.

### Step 12: Run

`.venv/bin/python -m pytest tests/integration/test_repositories.py --no-cov`

Expect: the last line contains `39 passed`

### Step 13: Run

`.venv/bin/python -m pytest tests/integration/test_repositories.py -o addopts="" --import-mode=importlib --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100`

Expect: the output contains `Required test coverage of 100% reached`.

This step checks that every line you wrote is used by a test. If it prints `FAIL Required test coverage of 100% not reached`, the "Missing" column lists line numbers in `repositories.py` that no test runs. Those lines are code that no requirement asks for: delete them. Do not go on until this step passes.

### Step 14: Write

Add this entry at the end of `docs/progress.md`, after one blank line. Replace `YYYY-MM-DD` with today's date. If you did anything these steps did not ask for, describe it on the "Deviations" line in place of `None`.

```markdown
## Phase 2k: get_account_by_name and create_account (YYYY-MM-DD)
- Built: `AccountExistsError`, `get_account_by_name`, and `create_account` in `src/finances/db/repositories.py`; `tests/integration/test_repositories.py`. 267 tests pass. `repositories.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None
```

### Step 15: Run

`.venv/bin/python -m ruff format .`

Expect: `32 files left unchanged`. If it says a file was reformatted, that is fine: go on to step 16.

### Step 16: Run

`.venv/bin/python -m ruff format --check .`

Expect: `32 files already formatted`

### Step 17: Run

`.venv/bin/python -m ruff check .`

Expect: `All checks passed!`

### Step 18: Run

`.venv/bin/python -m pytest`

Expect: the last line contains `267 passed`, and the output contains `Required test coverage of 85.0% reached`.

### Step 19: Run

`.venv/bin/python -m pytest tests/integration/test_repositories.py -o addopts="" --import-mode=importlib --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100`

Expect: the output contains `Required test coverage of 100% reached`. This is step 13 again, in case a later step changed the file.

### Step 20: Run

`git grep -n --untracked -E "commit\(|rollback\(|close\(|print\(|logging|IntegrityError" -- src/finances/db/repositories.py`

Expect: no output.

### Step 21: Run

`git status --short`

Expect exactly these three lines and nothing else:

```
 M docs/progress.md
?? src/finances/db/repositories.py
?? tests/integration/test_repositories.py
```

## If a Run step prints something else

| Step | Do this, then run the step again |
|---|---|
| any | If the output says `command not found`, `No such file`, or `No module named ruff` (or `pytest`), the command was not typed as written. Type it again starting with `.venv/bin/python`. If `.venv/bin/python` itself is missing, stop and report that; do not create a virtual environment |
| 5 | If it reports an import error or a syntax error, redo step 1 |
| 8 | Read the first failing test: `ignores_case_and_outer_spaces` is R1, `needs_the_whole_name` is R2. Change only the body of `get_account_by_name`, then redo step 7 |
| 11 | The error names a line: fix that line, then redo step 10 |
| 12 | Read the first failing test: its name says which requirement is not met (`removes_outer_spaces` is R3, `empty` is R4, `duplicate` and `session_still_works` are R5, `bad_last4` is R6, `type` is R7, `does_not_commit` is R8). Change only the body of `create_account`, then redo steps 10 and 11. If a `get_account_by_name` test fails, you changed that function: put it back |
| 13 or 19 | Delete the lines listed under "Missing", then redo steps 10 to 12 |
| 16 | Run step 15 again |
| 17 | Run `.venv/bin/python -m ruff check --fix .`. If an error remains, it names a file and a line: fix that line |
| 20 | Each line printed breaks a rule or R5. Rewrite that line without it, then redo steps 10 to 13 |
| 21 | A path that is not in the list is a file you must not have changed, or a database file a test left behind. For a file you changed, open it and undo your edit by hand. Report any database file. Do not use a git command |

## Final report

When step 21 matches, reply with the numbers 1 to 21, and after each Run step the last line of output you saw. Do not write "done" for a step you did not run.
