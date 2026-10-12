# Phase 2f: `validate_last4`

## Goal

Write one function, `validate_last4`, that checks the last four digits of an account number before they are stored. The tests are given. **You write the function body.** The work is to do the 15 steps in order.

## Read first

- `AGENTS.md`, sections "Running commands" and "Privacy rules" (rules 4 and 5)
- `src/finances/domain/models.py`

## Starting state

- Phase 2e is done and committed. `git status --short` prints nothing.
- `.venv/bin/python -m pytest` ends with `102 passed`.
- `src/finances/domain/models.py` contains `AccountType` and `Account`.
- These commands are written for macOS. On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python`.

## Files

| Path | Action |
|---|---|
| `src/finances/domain/models.py` | add `validate_last4`; you write its body |
| `tests/unit/test_models.py` | replace whole content with the block in step 1 |
| `docs/progress.md` | add one entry at the end |

Do not create or modify any other file.

## What to build

```python
def validate_last4(last4: str | None) -> str | None
```

- **R1.** `None` is allowed (an account may have no known digits): `validate_last4(None)` returns `None`.
- **R2.** A string of exactly four ASCII digits is returned unchanged: `"1234"` gives `"1234"`, `"0042"` gives `"0042"`.
- **R3.** Any other string raises `ValueError("last4 must be exactly 4 digits")`. Nothing is stripped or repaired: `" 1234"`, `"1234\n"`, `"123"`, `"12345"`, and `"12a4"` are all errors.
- **R4.** The message is exactly that constant text. It never contains the input.
- **R5.** Accept only the ASCII digits `0` to `9`. `str.isdigit()` and `\d` also accept digits from other alphabets, so do not rely on them alone.

The test file in step 1 lists every accepted and rejected input. It is the full definition of correct.

### Suggested approach

You may use this or write your own. Any body that satisfies R1 to R5 and passes step 8 is accepted.

1. If `last4` is `None`, return `None`.
2. If `re.fullmatch(r"[0-9]{4}", last4)` is `None`, raise `ValueError("last4 must be exactly 4 digits")`.
3. Return `last4`.

## Rules

- Do not change the test file. If a test fails, the function is wrong.
- Do not change `AccountType` or `Account`.
- `models.py` imports only from the Python standard library, and the imports go at the top of the file.
- Do not add logging or `print`.
- Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.

## How to work

- Each step is **one action**: **Write** (use the block given), **Code** (write code yourself), or **Run** (one command).
- Do all 15 steps, in order. Do not skip a Run step, and do not merge steps.
- After each Run step, compare the output with "Expect". If it differs, use the table under "If a Run step prints something else".
- Type every command exactly as written, starting with `.venv/bin/python`. Do not shorten it to `python`, `python3`, `ruff`, or `pytest`.
- Do not activate the virtual environment and do not create one. `.venv/` already exists.

## Steps

### Step 1: Write

Replace the whole content of `tests/unit/test_models.py` with exactly this:

```python
import dataclasses
from datetime import UTC, datetime
from enum import StrEnum

import pytest

from finances.domain.models import Account, AccountType, validate_last4

CREATED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

VALID_LAST4 = ["1234", "0000", "0042", "9999"]
INVALID_LAST4 = [
    "",
    "123",
    "12345",
    "12a4",
    "abcd",
    " 1234",
    "1234 ",
    "12 4",
    "1234\n",
    "-123",
    "+123",
    "12.4",
    "١٢٣٤",
    "１２３４",
]


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


def test_validate_last4_accepts_none() -> None:
    assert validate_last4(None) is None


@pytest.mark.parametrize("last4", VALID_LAST4)
def test_validate_last4_returns_valid_input_unchanged(last4: str) -> None:
    assert validate_last4(last4) == last4


@pytest.mark.parametrize("last4", INVALID_LAST4)
def test_validate_last4_rejects(last4: str) -> None:
    with pytest.raises(ValueError):
        validate_last4(last4)


def test_validate_last4_error_does_not_echo_input() -> None:
    with pytest.raises(ValueError) as excinfo:
        validate_last4("12a4")
    assert str(excinfo.value) == "last4 must be exactly 4 digits"
```

### Step 2: Run

`.venv/bin/python -m ruff format tests/unit/test_models.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 3: Write

Add this function at the end of `src/finances/domain/models.py`, after two blank lines. Do not change anything above it.

```python
def validate_last4(last4: str | None) -> str | None:
    """Return last4 unchanged if it is None or exactly four ASCII digits; otherwise raise."""
    raise NotImplementedError
```

### Step 4: Run

`.venv/bin/python -m pytest tests/unit/test_models.py --no-cov`

Expect: the last line contains `20 failed, 13 passed`. The new tests fail because the function is not written yet.

### Step 5: Code

In `src/finances/domain/models.py`, replace the line `raise NotImplementedError` with your implementation of `validate_last4`. Keep the `def` line and the docstring as they are. If you need an import, add it at the top of the file. Follow R1 to R5.

### Step 6: Run

`.venv/bin/python -m ruff format src/finances/domain/models.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 7: Run

`.venv/bin/python -m ruff check --fix src/finances/domain/models.py`

Expect: the last line is `All checks passed!`. A line saying an error was fixed is fine.

### Step 8: Run

`.venv/bin/python -m pytest tests/unit/test_models.py --no-cov`

Expect: the last line contains `33 passed`

### Step 9: Write

Add this entry at the end of `docs/progress.md`, after one blank line. Replace `YYYY-MM-DD` with today's date. If you did anything these steps did not ask for, describe it on the "Deviations" line in place of `None`.

```markdown
## Phase 2f: validate_last4 (YYYY-MM-DD)
- Built: `validate_last4` in `src/finances/domain/models.py`, with its tests in `tests/unit/test_models.py`. 122 tests pass. `models.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None
```

### Step 10: Run

`.venv/bin/python -m ruff format .`

Expect: `20 files left unchanged`. If it says a file was reformatted, that is fine: go on to step 11.

### Step 11: Run

`.venv/bin/python -m ruff format --check .`

Expect: `20 files already formatted`

### Step 12: Run

`.venv/bin/python -m ruff check .`

Expect: `All checks passed!`

### Step 13: Run

`.venv/bin/python -m pytest`

Expect: the last line contains `122 passed`, the output contains `Required test coverage of 85.0% reached`, and the row for `src/finances/domain/models.py` ends with `100%`.

### Step 14: Run

`git grep -n -E "^(from|import) finances|print\(|logging" -- src/finances/domain/models.py`

Expect: no output.

### Step 15: Run

`git status --short`

Expect exactly these three lines and nothing else:

```
 M docs/progress.md
 M src/finances/domain/models.py
 M tests/unit/test_models.py
```

## If a Run step prints something else

| Step | Do this, then run the step again |
|---|---|
| any | If the output says `command not found`, `No such file`, or `No module named ruff` (or `pytest`), the command was not typed as written. Type it again starting with `.venv/bin/python`. If `.venv/bin/python` itself is missing, stop and report that; do not create a virtual environment |
| 4 | If it reports an import error or a syntax error, the function from step 3 is missing or misplaced: redo step 3 |
| 7 | The error names a line: fix that line, then redo step 6 |
| 8 | Read the first failing test: it shows the input and what was expected. Change only the body of `validate_last4`, then redo steps 6 and 7. If an `account` test fails, you changed `AccountType` or `Account`: put it back |
| 11 | Run step 10 again |
| 12 | Run `.venv/bin/python -m ruff check --fix .`. If an error remains, it names a file and a line: fix that line |
| 13, `models.py` below `100%` | The "Missing" column lists lines of your function that no test reaches. Remove that code, then redo steps 6 to 8 |
| 14 | Each line printed breaks a rule. Rewrite that line without it, then redo steps 6 to 8 |
| 15 | A path that is not in the list is a file you must not have changed. Open it and undo your edit by hand. Do not use a git command |

## Final report

When step 15 matches, reply with the numbers 1 to 15, and after each Run step the last line of output you saw. Do not write "done" for a step you did not run.
