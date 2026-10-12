# Phase 2c: `format_cents`

## Goal

Write one function, `format_cents`, that turns an integer number of cents into display text. The tests are given. **You write the function body.** The work is to do the 14 steps in order.

## Read first

- `AGENTS.md`, section "Money and signs"

## Starting state

- Phases 2a and 2b are done and committed. `git status --short` prints nothing.
- `python -m pytest` ends with `16 passed`.
- The folder `src/finances/domain/` does not exist yet.

## Files

| Path | Action |
|---|---|
| `src/finances/domain/__init__.py` | create, empty |
| `src/finances/domain/money.py` | create; you write the body of `format_cents` |
| `tests/unit/test_money.py` | create from the block in step 2 |
| `docs/progress.md` | add one entry at the end |

Do not create or modify any other file.

## What to build

```python
def format_cents(cents: int) -> str
```

- **R1.** The result is: `-` if `cents` is negative, then `$`, then the dollars with `,` between groups of three digits, then `.`, then exactly two cent digits. Examples: `123456` gives `$1,234.56`, `-1234` gives `-$12.34`, `0` gives `$0.00`, `5` gives `$0.05`.
- **R2.** Use integer arithmetic only. `float`, the `/` operator, and `round` must not appear in `money.py`. (`divmod(abs(cents), 100)` gives the dollars and the cents.)
- **R3.** `money.py` imports nothing.

How you write the body is up to you, as long as R1 to R3 hold and step 8 passes.

## Rules

- Do not change the test file. If a test fails, the function is wrong.
- Do not add other functions, classes, logging, or `print` to `money.py`.
- Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.

## How to work

- Each step is **one action**: **Write** (create a file from the block given), **Code** (write code yourself), or **Run** (one command).
- Do all 14 steps, in order. Do not skip a Run step, and do not merge steps.
- After each Run step, compare the output with "Expect". If it differs, use the table under "If a Run step prints something else".
- Activate the virtual environment first, so `python` is the project's interpreter.

## Steps

### Step 1: Write

Create an empty file `src/finances/domain/__init__.py`. Create the folder `src/finances/domain/` first; it does not exist yet.

### Step 2: Write

Create `tests/unit/test_money.py` with exactly this content:

```python
import pytest

from finances.domain.money import format_cents

FORMAT = [
    (123456, "$1,234.56"),
    (-1234, "-$12.34"),
    (0, "$0.00"),
    (5, "$0.05"),
    (-5, "-$0.05"),
    (100, "$1.00"),
    (-100, "-$1.00"),
    (99, "$0.99"),
    (10, "$0.10"),
    (100000000, "$1,000,000.00"),
    (-100000000, "-$1,000,000.00"),
    (123456789012, "$1,234,567,890.12"),
    (9007199254740993, "$90,071,992,547,409.93"),
]


@pytest.mark.parametrize(("cents", "expected"), FORMAT)
def test_format_cents(cents: int, expected: str) -> None:
    assert format_cents(cents) == expected


def test_format_cents_returns_str() -> None:
    assert type(format_cents(1)) is str
```

### Step 3: Run

`python -m ruff format tests/unit/test_money.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 4: Write

Create `src/finances/domain/money.py` with exactly this content:

```python
def format_cents(cents: int) -> str:
    """Return display text for integer cents: 123456 -> "$1,234.56", -1234 -> "-$12.34"."""
    raise NotImplementedError
```

### Step 5: Run

`python -m pytest tests/unit/test_money.py --no-cov`

Expect: the last line contains `14 failed`. The tests fail because the function is not written yet.

### Step 6: Code

In `src/finances/domain/money.py`, replace the line `raise NotImplementedError` with your implementation of `format_cents`. Keep the `def` line and the docstring as they are. Follow R1 to R3.

### Step 7: Run

`python -m ruff format src/finances/domain/money.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 8: Run

`python -m pytest tests/unit/test_money.py --no-cov`

Expect: the last line contains `14 passed`

### Step 9: Write

Add this entry at the end of `docs/progress.md`, after one blank line. Replace `YYYY-MM-DD` with today's date. If you did anything these steps did not ask for, describe it on the "Deviations" line in place of `None`.

```markdown
## Phase 2c: format_cents (YYYY-MM-DD)
- Built: `format_cents` in `src/finances/domain/money.py`, and `tests/unit/test_money.py`. 30 tests pass. `money.py` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None
```

### Step 10: Run

`python -m ruff format .`

Expect: `18 files left unchanged`. If it says a file was reformatted, that is fine: go on to step 11.

### Step 11: Run

`python -m ruff format --check .`

Expect: `18 files already formatted`

### Step 12: Run

`python -m ruff check .`

Expect: `All checks passed!`

### Step 13: Run

`python -m pytest`

Expect: the last line contains `30 passed`, the output contains `Required test coverage of 85.0% reached`, and the row for `src/finances/domain/money.py` ends with `100%`.

### Step 14: Run

`git status --short`

Expect exactly these three lines and nothing else:

```
 M docs/progress.md
?? src/finances/domain/
?? tests/unit/test_money.py
```

## If a Run step prints something else

| Step | Do this, then run the step again |
|---|---|
| 5 | If it reports an import error, check step 1 and step 4. If it says `14 passed`, you skipped ahead: carry on from step 7 |
| 8 | Read the first failing test: it shows the input, what your function returned, and what was expected. Change only the body of `format_cents`, then redo step 7 |
| 11 | Run step 10 again |
| 12 | Run `python -m ruff check --fix .`. If an error remains, it names a file and a line: fix that line |
| 13, `money.py` below `100%` | The "Missing" column lists lines of your function that no test reaches. Remove that code, then redo steps 7 and 8 |
| 14 | A path that is not in the list is a file you must not have changed. Open it and undo your edit by hand. Do not use a git command |

## Final report

When step 14 matches, reply with the numbers 1 to 14, and after each Run step the last line of output you saw. Do not write "done" for a step you did not run.
