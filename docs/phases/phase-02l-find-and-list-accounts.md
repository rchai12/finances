# Phase 2l: `find_accounts_by_last4` and `list_accounts`

## Goal

Write the other two account repository functions: `find_accounts_by_last4` finds the accounts a statement could belong to, and `list_accounts` returns the accounts to show the user. The tests are given. **You write both function bodies.** The work is to do the 21 steps in order.

## Read first

- `AGENTS.md`, sections "Running commands" and "Architecture rules"
- `src/finances/db/repositories.py` (the two functions from Phase 2k)

## Starting state

- Phase 2k is done and committed. `git status --short` prints nothing.
- `.venv/bin/python -m pytest` ends with `267 passed`.
- `src/finances/db/repositories.py` contains `AccountExistsError`, `get_account_by_name`, and `create_account`.
- These commands are written for macOS. On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python`.

## Files

| Path | Action |
|---|---|
| `src/finances/db/repositories.py` | add the two functions from the block in step 3; you write both bodies |
| `tests/integration/test_repositories.py` | replace whole content with the block in step 1 |
| `docs/progress.md` | add one entry at the end |

Do not create or modify any other file.

## What to build

Every requirement below is checked by at least one given test. If the tests pass and the coverage step passes, you are done: do not add checks that no requirement asks for.

### Part 1: `find_accounts_by_last4`

```python
def find_accounts_by_last4(session: Session, last4: str) -> list[Account]
```

- **R1.** It returns every account whose `last4` equals the argument, as a `list` of `Account`, in order of `id`. Inactive accounts are included: a statement for a closed card must still find its account.
- **R2.** When no account matches, it returns an empty list. An account with no `last4` never matches.
- **R3.** The argument is checked first with `validate_last4`, so text that is not exactly four digits raises `ValueError("last4 must be exactly 4 digits")` without querying the database.

### Part 2: `list_accounts`

```python
def list_accounts(session: Session, include_inactive: bool = False) -> list[Account]
```

- **R4.** By default it returns only the accounts whose `is_active` is true. With `include_inactive=True` it returns all of them.
- **R5.** The result is a `list` of `Account`, sorted by name without regard to upper and lower case: `"apple"`, `"Banana"`, `"cherry"`.
- **R6.** When there are no accounts to return, it returns an empty list.

### SQLAlchemy facts you will need

These are how the library works, not a recipe.

- `select(AccountRow).where(<condition>).order_by(<expression>)` builds a query. `.where(...)` can be left out, and it can be added to a query later: `query = query.where(...)`.
- `session.scalars(<query>).all()` runs it and returns the matching `AccountRow` objects.
- `AccountRow.last4 == value` and `AccountRow.is_active.is_(True)` are conditions. Do not write `== True`: the linter rejects it.
- `func.lower(AccountRow.name)` is the name in lower case, and can be used in `order_by`.
- `to_account(row)` turns a row into an `Account`. `validate_last4(text)` raises `ValueError` for bad input and returns the text otherwise.

## Rules

- Do not change the test file. If a test fails, `repositories.py` is wrong.
- Do not change `AccountExistsError`, `get_account_by_name`, or `create_account`.
- Do not change the two new `def` lines or their docstrings.
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

Replace the whole content of `tests/integration/test_repositories.py` with exactly this. The tests from Phase 2k are unchanged; the import line is longer, and the tests after `test_create_account_rejects_a_bad_last4` are new.

```python
from datetime import timedelta

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import AccountRow
from finances.db.repositories import (
    AccountExistsError,
    create_account,
    find_accounts_by_last4,
    get_account_by_name,
    list_accounts,
)
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


@pytest.mark.parametrize(
    "name", ["Test Checking", "test checking", "TEST CHECKING", " Test Checking "]
)
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


def names(accounts: list[Account]) -> list[str]:
    return [account.name for account in accounts]


def test_find_accounts_by_last4_returns_the_matching_account(db_engine: Engine) -> None:
    add_row(db_engine, "Test Checking", last4="1234")
    add_row(db_engine, "Test Savings", last4="5678")
    with session_scope(db_engine) as session:
        accounts = find_accounts_by_last4(session, "1234")
    assert type(accounts) is list
    assert [type(account) for account in accounts] == [Account]
    assert names(accounts) == ["Test Checking"]


def test_find_accounts_by_last4_returns_every_match_in_id_order(db_engine: Engine) -> None:
    add_row(db_engine, "Zebra Card", last4="1234", type="credit_card")
    add_row(db_engine, "Other Card", last4="9999", type="credit_card")
    add_row(db_engine, "Apple Card", last4="1234", type="credit_card")
    with session_scope(db_engine) as session:
        accounts = find_accounts_by_last4(session, "1234")
    assert [account.id for account in accounts] == [1, 3]
    assert names(accounts) == ["Zebra Card", "Apple Card"]


def test_find_accounts_by_last4_includes_inactive_accounts(db_engine: Engine) -> None:
    add_row(db_engine, "Closed Card", last4="1234", is_active=False)
    with session_scope(db_engine) as session:
        accounts = find_accounts_by_last4(session, "1234")
    assert names(accounts) == ["Closed Card"]
    assert accounts[0].is_active is False


def test_find_accounts_by_last4_no_match_gives_an_empty_list(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        assert find_accounts_by_last4(session, "1234") == []
    add_row(db_engine, "Test Checking", last4="1234")
    with session_scope(db_engine) as session:
        assert find_accounts_by_last4(session, "0000") == []


def test_find_accounts_by_last4_ignores_accounts_without_last4(db_engine: Engine) -> None:
    add_row(db_engine, "No Digits")
    with session_scope(db_engine) as session:
        assert find_accounts_by_last4(session, "1234") == []


@pytest.mark.parametrize("last4", ["", "123", "12345", "12a4", " 1234"])
def test_find_accounts_by_last4_rejects_bad_input(db_engine: Engine, last4: str) -> None:
    add_row(db_engine, "Test Checking", last4="1234")
    with session_scope(db_engine) as session:
        with pytest.raises(ValueError) as excinfo:
            find_accounts_by_last4(session, last4)
    assert str(excinfo.value) == "last4 must be exactly 4 digits"


def test_list_accounts_is_empty_when_there_are_no_accounts(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        accounts = list_accounts(session)
    assert type(accounts) is list
    assert accounts == []


def test_list_accounts_sorted_by_name_ignoring_case(db_engine: Engine) -> None:
    for name in ["cherry", "Banana", "apple", "Date"]:
        add_row(db_engine, name)
    with session_scope(db_engine) as session:
        accounts = list_accounts(session)
    assert type(accounts) is list
    assert [type(account) for account in accounts] == [Account] * 4
    assert names(accounts) == ["apple", "Banana", "cherry", "Date"]


def test_list_accounts_leaves_out_inactive_by_default(db_engine: Engine) -> None:
    add_row(db_engine, "Open One")
    add_row(db_engine, "Closed", is_active=False)
    add_row(db_engine, "Open Two")
    with session_scope(db_engine) as session:
        assert names(list_accounts(session)) == ["Open One", "Open Two"]
        assert names(list_accounts(session, False)) == ["Open One", "Open Two"]
        assert names(list_accounts(session, include_inactive=False)) == ["Open One", "Open Two"]


def test_list_accounts_include_inactive_returns_all(db_engine: Engine) -> None:
    add_row(db_engine, "Open One")
    add_row(db_engine, "Closed", is_active=False)
    add_row(db_engine, "Open Two")
    with session_scope(db_engine) as session:
        accounts = list_accounts(session, include_inactive=True)
    assert names(accounts) == ["Closed", "Open One", "Open Two"]
    assert [account.is_active for account in accounts] == [False, True, True]


def test_list_accounts_is_empty_when_every_account_is_inactive(db_engine: Engine) -> None:
    add_row(db_engine, "Closed", is_active=False)
    with session_scope(db_engine) as session:
        assert list_accounts(session) == []
```

### Step 2: Run

`.venv/bin/python -m ruff format tests/integration/test_repositories.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 3: Write

Add these two functions at the end of `src/finances/db/repositories.py`, after two blank lines. Do not change anything above them.

```python
def find_accounts_by_last4(session: Session, last4: str) -> list[Account]:
    """Return the accounts with these last four digits, active or not, in id order."""
    raise NotImplementedError


def list_accounts(session: Session, include_inactive: bool = False) -> list[Account]:
    """Return the accounts sorted by name, leaving out inactive ones unless asked."""
    raise NotImplementedError
```

### Step 4: Run

`.venv/bin/python -m ruff format src/finances/db/repositories.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 5: Run

`.venv/bin/python -m pytest tests/integration/test_repositories.py --no-cov`

Expect: the last line contains `15 failed, 39 passed`. The new tests fail because the functions are not written yet.

### Step 6: Code

In `src/finances/db/repositories.py`, replace the first `raise NotImplementedError` with your implementation of `find_accounts_by_last4`. Keep the `def` line and the docstring as they are. Follow Part 1 (R1 to R3).

### Step 7: Run

`.venv/bin/python -m ruff format src/finances/db/repositories.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 8: Run

`.venv/bin/python -m pytest tests/integration/test_repositories.py --no-cov -k "test_find_accounts_by_last4"`

Expect: the last line contains `10 passed, 44 deselected`

### Step 9: Code

In `src/finances/db/repositories.py`, replace the remaining `raise NotImplementedError` with your implementation of `list_accounts`. Keep the `def` line and the docstring as they are. Follow Part 2 (R4 to R6).

### Step 10: Run

`.venv/bin/python -m ruff format src/finances/db/repositories.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 11: Run

`.venv/bin/python -m ruff check --fix src/finances/db/repositories.py`

Expect: the last line is `All checks passed!`.

### Step 12: Run

`.venv/bin/python -m pytest tests/integration/test_repositories.py --no-cov`

Expect: the last line contains `54 passed`

### Step 13: Run

`.venv/bin/python -m pytest tests/integration/test_repositories.py -o addopts="" --import-mode=importlib --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100`

Expect: the output contains `Required test coverage of 100% reached`.

This step checks that every line you wrote is used by a test. If it prints `FAIL Required test coverage of 100% not reached`, the "Missing" column lists line numbers in `repositories.py` that no test runs. Those lines are code that no requirement asks for: delete them. Do not go on until this step passes.

### Step 14: Write

Add this entry at the end of `docs/progress.md`, after one blank line. Replace `YYYY-MM-DD` with today's date. If you did anything these steps did not ask for, describe it on the "Deviations" line in place of `None`.

```markdown
## Phase 2l: find_accounts_by_last4 and list_accounts (YYYY-MM-DD)
- Built: `find_accounts_by_last4` and `list_accounts` in `src/finances/db/repositories.py`, with their tests in `tests/integration/test_repositories.py`. 282 tests pass. `repositories.py` coverage: 100%.
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

Expect: the last line contains `282 passed`, and the output contains `Required test coverage of 85.0% reached`.

### Step 19: Run

`.venv/bin/python -m pytest tests/integration/test_repositories.py -o addopts="" --import-mode=importlib --cov=finances.db.repositories --cov-branch --cov-report=term-missing --cov-fail-under=100`

Expect: the output contains `Required test coverage of 100% reached`. This is step 13 again, in case a later step changed the file.

### Step 20: Run

`git grep -n -E "commit\(|rollback\(|close\(|print\(|logging|== True|== False" -- src/finances/db/repositories.py`

Expect: no output.

### Step 21: Run

`git status --short`

Expect exactly these three lines and nothing else:

```
 M docs/progress.md
 M src/finances/db/repositories.py
 M tests/integration/test_repositories.py
```

## If a Run step prints something else

| Step | Do this, then run the step again |
|---|---|
| any | If the output says `command not found`, `No such file`, or `No module named ruff` (or `pytest`), the command was not typed as written. Type it again starting with `.venv/bin/python`. If `.venv/bin/python` itself is missing, stop and report that; do not create a virtual environment |
| 5 | If it reports an import error or a syntax error, the functions from step 3 are missing or misplaced: redo step 3 |
| 8 | Read the first failing test: `includes_inactive` and `id_order` are R1, `no_match` and `ignores_accounts_without_last4` are R2, `rejects` is R3. Change only the body of `find_accounts_by_last4`, then redo step 7 |
| 11 | The error names a line: fix that line, then redo step 10. If it says `E712`, replace `== True` with `.is_(True)` |
| 12 | Read the first failing test: `leaves_out_inactive` and `include_inactive` are R4, `sorted` is R5, `empty` is R6. Change only the body of `list_accounts`, then redo steps 10 and 11. If an earlier test fails, you changed an earlier function: put it back |
| 13 or 19 | Delete the lines listed under "Missing", then redo steps 10 to 12 |
| 16 | Run step 15 again |
| 17 | Run `.venv/bin/python -m ruff check --fix .`. If an error remains, it names a file and a line: fix that line |
| 20 | Each line printed breaks a rule. Rewrite that line without it, then redo steps 10 to 13 |
| 21 | A path that is not in the list is a file you must not have changed, or a database file a test left behind. For a file you changed, open it and undo your edit by hand. Report any database file. Do not use a git command |

## Final report

When step 21 matches, reply with the numbers 1 to 21, and after each Run step the last line of output you saw. Do not write "done" for a step you did not run.
