# Phase 2e: `AccountType` and `Account`

## Goal

Write the two domain types that describe an account: the `AccountType` enum and the `Account` dataclass. The tests are given. **You write the members and the fields.** The work is to do the 17 steps in order.

## Read first

- `AGENTS.md`, sections "Running commands" and "Architecture rules"

## Starting state

- Phase 2d is done and committed. `git status --short` prints nothing.
- `.venv/bin/python -m pytest` ends with `89 passed`.
- `src/finances/domain/` contains `__init__.py` and `money.py`.
- These commands are written for macOS. On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python`.

## Files

| Path | Action |
|---|---|
| `src/finances/domain/models.py` | create from the block in step 3; you write the members and fields |
| `tests/unit/test_models.py` | create from the block in step 1 |
| `docs/progress.md` | add one entry at the end |

Do not create or modify any other file.

## What to build

- **R1.** `AccountType` is a `StrEnum` with exactly these four members, in this order:

  | Member | Value |
  |---|---|
  | `CHECKING` | `"checking"` |
  | `SAVINGS` | `"savings"` |
  | `CREDIT_CARD` | `"credit_card"` |
  | `OTHER` | `"other"` |

- **R2.** `Account` is a frozen dataclass with exactly these eight fields, in this order:

  | Field | Type |
  |---|---|
  | `id` | `int` |
  | `name` | `str` |
  | `institution` | `str` |
  | `type` | `AccountType` |
  | `currency` | `str` |
  | `last4` | `str \| None` |
  | `is_active` | `bool` |
  | `created_at` | `datetime` |

- **R3.** No field has a default value. Every field must be given when an `Account` is created.
- **R4.** `models.py` imports only from the Python standard library. It must not import anything from `finances`.

## Rules

- Do not change the test file. If a test fails, `models.py` is wrong.
- Do not add methods, properties, other classes, or functions to `models.py`.
- Do not change `money.py`.
- Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.

## How to work

- Each step is **one action**: **Write** (use the block given), **Code** (write code yourself), or **Run** (one command).
- Do all 17 steps, in order. Do not skip a Run step, and do not merge steps.
- After each Run step, compare the output with "Expect". If it differs, use the table under "If a Run step prints something else".
- Type every command exactly as written, starting with `.venv/bin/python`. Do not shorten it to `python`, `python3`, `ruff`, or `pytest`.
- Do not activate the virtual environment and do not create one. `.venv/` already exists.

## Steps

### Step 1: Write

Create `tests/unit/test_models.py` with exactly this content:

```python
import dataclasses
from datetime import UTC, datetime
from enum import StrEnum

import pytest

from finances.domain.models import Account, AccountType

CREATED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def make_account(**changes: object) -> Account:
    values = {
        "id": 1,
        "name": "Test Checking",
        "institution": "Test Bank",
        "type": AccountType.CHECKING,
        "currency": "USD",
        "last4": "1234",
        "is_active": True,
        "created_at": CREATED,
    }
    values.update(changes)
    return Account(**values)


def test_account_type_is_a_str_enum() -> None:
    assert issubclass(AccountType, StrEnum)


def test_account_type_members_in_order() -> None:
    names = [member.name for member in AccountType]
    assert names == ["CHECKING", "SAVINGS", "CREDIT_CARD", "OTHER"]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("CHECKING", "checking"),
        ("SAVINGS", "savings"),
        ("CREDIT_CARD", "credit_card"),
        ("OTHER", "other"),
    ],
)
def test_account_type_values(name: str, value: str) -> None:
    member = AccountType[name]
    assert member.value == value
    assert str(member) == value
    assert AccountType(value) is member


def test_account_type_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        AccountType("brokerage")


def test_account_fields_in_order() -> None:
    names = [field.name for field in dataclasses.fields(Account)]
    assert names == [
        "id",
        "name",
        "institution",
        "type",
        "currency",
        "last4",
        "is_active",
        "created_at",
    ]


def test_account_has_no_default_values() -> None:
    fields = dataclasses.fields(Account)
    assert len(fields) == 8
    for field in fields:
        assert field.default is dataclasses.MISSING
        assert field.default_factory is dataclasses.MISSING


def test_account_keeps_its_values() -> None:
    account = make_account()
    assert account.id == 1
    assert account.name == "Test Checking"
    assert account.institution == "Test Bank"
    assert account.type is AccountType.CHECKING
    assert account.currency == "USD"
    assert account.last4 == "1234"
    assert account.is_active is True
    assert account.created_at == CREATED


def test_account_last4_may_be_none() -> None:
    assert make_account(last4=None).last4 is None


def test_account_is_frozen() -> None:
    account = make_account()
    with pytest.raises(dataclasses.FrozenInstanceError):
        account.name = "Other"


def test_accounts_with_equal_values_are_equal() -> None:
    assert make_account() == make_account()
    assert make_account() != make_account(id=2)
    assert hash(make_account()) == hash(make_account())
```

### Step 2: Run

`.venv/bin/python -m ruff format tests/unit/test_models.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 3: Write

Create `src/finances/domain/models.py` with exactly this content:

```python
"""Domain models. This module imports nothing from the rest of the project."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AccountType(StrEnum):
    """Kind of bank or card account."""


@dataclass(frozen=True)
class Account:
    """One bank or card account, as stored."""
```

### Step 4: Run

`.venv/bin/python -m pytest tests/unit/test_models.py --no-cov`

Expect: the last line contains `12 failed, 1 passed`. The tests fail because the members and fields are not written yet.

### Step 5: Code

In `src/finances/domain/models.py`, add the four members to `AccountType`, below its docstring. Follow R1.

### Step 6: Run

`.venv/bin/python -m ruff format src/finances/domain/models.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 7: Run

`.venv/bin/python -m pytest tests/unit/test_models.py --no-cov -k account_type`

Expect: the last line contains `7 passed, 6 deselected`

### Step 8: Code

In `src/finances/domain/models.py`, add the eight fields to `Account`, below its docstring. Follow R2 and R3.

### Step 9: Run

`.venv/bin/python -m ruff format src/finances/domain/models.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 10: Run

`.venv/bin/python -m pytest tests/unit/test_models.py --no-cov`

Expect: the last line contains `13 passed`

### Step 11: Write

Add this entry at the end of `docs/progress.md`, after one blank line. Replace `YYYY-MM-DD` with today's date. If you did anything these steps did not ask for, describe it on the "Deviations" line in place of `None`.

```markdown
## Phase 2e: AccountType and Account (YYYY-MM-DD)
- Built: `AccountType` and `Account` in `src/finances/domain/models.py`, and `tests/unit/test_models.py`. 102 tests pass. `models.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None
```

### Step 12: Run

`.venv/bin/python -m ruff format .`

Expect: `20 files left unchanged`. If it says a file was reformatted, that is fine: go on to step 13.

### Step 13: Run

`.venv/bin/python -m ruff format --check .`

Expect: `20 files already formatted`

### Step 14: Run

`.venv/bin/python -m ruff check .`

Expect: `All checks passed!`

### Step 15: Run

`.venv/bin/python -m pytest`

Expect: the last line contains `102 passed`, the output contains `Required test coverage of 85.0% reached`, and the row for `src/finances/domain/models.py` ends with `100%`.

### Step 16: Run

`git grep -n --untracked -E "^(from|import) finances" -- src/finances/domain`

Expect: no output.

### Step 17: Run

`git status --short`

Expect exactly these three lines and nothing else:

```
 M docs/progress.md
?? src/finances/domain/models.py
?? tests/unit/test_models.py
```

## If a Run step prints something else

| Step | Do this, then run the step again |
|---|---|
| any | If the output says `command not found`, `No such file`, or `No module named ruff` (or `pytest`), the command was not typed as written. Type it again starting with `.venv/bin/python`. If `.venv/bin/python` itself is missing, stop and report that; do not create a virtual environment |
| 4 | If it reports an import error or a syntax error, redo step 3 |
| 7 | Read the first failing test: it names the member or value that is wrong. Change only the members of `AccountType`, then redo step 6 |
| 10 | Read the first failing test: it names the field that is wrong. Change only the fields of `Account`, then redo step 9 |
| 13 | Run step 12 again |
| 14 | Run `.venv/bin/python -m ruff check --fix .`. If an error remains, it names a file and a line: fix that line |
| 16 | Each line printed is an import that R4 forbids. Remove it, then redo steps 9 and 10 |
| 17 | A path that is not in the list is a file you must not have changed. Open it and undo your edit by hand. Do not use a git command |

## Final report

When step 17 matches, reply with the numbers 1 to 17, and after each Run step the last line of output you saw. Do not write "done" for a step you did not run.
