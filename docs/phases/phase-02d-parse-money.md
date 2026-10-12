# Phase 2d: `parse_money`

## Goal

Write one function, `parse_money`, that turns money text into an integer number of cents. The tests are given. **You write the function body.** The work is to do the 15 steps in order.

## Read first

- `AGENTS.md`, section "Money and signs", and privacy rules 4 and 5
- `src/finances/domain/money.py`

## Starting state

- Phase 2c is done and committed. `git status --short` prints nothing.
- `python -m pytest` ends with `30 passed`.
- `src/finances/domain/money.py` contains `format_cents`.

## Files

| Path | Action |
|---|---|
| `src/finances/domain/money.py` | add `parse_money`; you write its body |
| `tests/unit/test_money.py` | replace whole content with the block in step 1 |
| `docs/progress.md` | add one entry at the end |

Do not create or modify any other file.

## What to build

```python
def parse_money(text: str) -> int
```

- **R1.** It returns cents as an `int`. `"12.34"` gives `1234`, `"$1,234.56"` gives `123456`, `"  7 "` gives `700`, `".5"` gives `50`.
- **R2.** Three ways to write a negative amount, and only one may be used at a time: a leading `-` (`"-12.34"`, `"-$12.34"`), a trailing `-` (`"12.34-"`), or parentheses (`"(12.34)"`). All three give `-1234`.
- **R3.** Anything else raises `ValueError("invalid money text")`. The message is exactly that constant text. It never contains the input.
- **R4.** Use `decimal.Decimal` for the conversion. `float`, the `/` operator, and `round` must not appear in `money.py`.
- **R5.** Accept only the ASCII digits `0` to `9`. In a regular expression write `[0-9]`, not `\d`.

The test file in step 1 lists every accepted and rejected input. It is the full definition of correct.

### Suggested approach

You may use this or write your own. Any body that satisfies R1 to R5 and passes step 8 is accepted.

1. `s = text.strip()`
2. Find the negative marker with `if` / `elif` / `elif`, removing it from `s`: parentheses at both ends, else a trailing `-`, else a leading `-`.
3. If `s` now starts with `$`, remove that one character.
4. Check `s` with `re.fullmatch` against the pattern below. No match means `raise ValueError("invalid money text")`.
5. Remove the commas, then `cents = int(Decimal(s) * 100)`. Return `-cents` if negative.

```python
_AMOUNT = re.compile(r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?|\.[0-9]{1,2}")
```

## Rules

- Do not change the test file. If a test fails, the function is wrong.
- Do not change `format_cents`.
- Do not add logging or `print` to `money.py`.
- Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.

## How to work

- Each step is **one action**: **Write** (use the block given), **Code** (write code yourself), or **Run** (one command).
- Do all 15 steps, in order. Do not skip a Run step, and do not merge steps.
- After each Run step, compare the output with "Expect". If it differs, use the table under "If a Run step prints something else".
- Activate the virtual environment first, so `python` is the project's interpreter.

## Steps

### Step 1: Write

Replace the whole content of `tests/unit/test_money.py` with exactly this:

```python
import pytest

from finances.domain.money import format_cents, parse_money

VALID = [
    ("12.34", 1234),
    ("-12.34", -1234),
    ("$1,234.56", 123456),
    ("(12.34)", -1234),
    ("12.34-", -1234),
    ("  7 ", 700),
    ("-$12.34", -1234),
    ("($1,234.56)", -123456),
    ("$12.34-", -1234),
    ("0", 0),
    ("-0.00", 0),
    (".5", 50),
    ("12.3", 1230),
    ("1.15", 115),
    ("0.29", 29),
    ("4.35", 435),
    ("$0.07", 7),
    ("1,000,000.00", 100000000),
]
INVALID = [
    "",
    "   ",
    "abc",
    "12.345",
    "12.",
    "1,23.45",
    "1234,567",
    "12,34",
    "1.2.3",
    "$",
    "-",
    "--5",
    "(5",
    "5)",
    "()",
    "(-5)",
    "-(5)",
    "-5-",
    "$-5",
    "$$5",
    "+5",
    "1 000",
    "$ 5",
    "- 5",
    "1e3",
    "1_000",
    "0x10",
    "NaN",
    "Infinity",
]
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


@pytest.mark.parametrize(("text", "expected"), VALID)
def test_parse_money_valid(text: str, expected: int) -> None:
    assert parse_money(text) == expected


@pytest.mark.parametrize("text", INVALID)
def test_parse_money_invalid(text: str) -> None:
    with pytest.raises(ValueError):
        parse_money(text)


def test_parse_money_error_does_not_echo_input() -> None:
    with pytest.raises(ValueError) as excinfo:
        parse_money("12.345")
    assert str(excinfo.value) == "invalid money text"


def test_parse_money_rejects_non_ascii_digits() -> None:
    with pytest.raises(ValueError):
        parse_money("١٢")


def test_parse_money_returns_int() -> None:
    assert type(parse_money("12.34")) is int


@pytest.mark.parametrize(("cents", "expected"), FORMAT)
def test_format_cents(cents: int, expected: str) -> None:
    assert format_cents(cents) == expected


def test_format_cents_returns_str() -> None:
    assert type(format_cents(1)) is str


@pytest.mark.parametrize("n", [0, 1, -1, 99, -99, 100, 12345, -12345, 100000000])
def test_round_trip(n: int) -> None:
    assert parse_money(format_cents(n)) == n
```

### Step 2: Run

`python -m ruff format tests/unit/test_money.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 3: Write

Add this function at the end of `src/finances/domain/money.py`, after two blank lines. Do not change anything above it.

```python
def parse_money(text: str) -> int:
    """Return integer cents for money text such as "$1,234.56", "(12.34)" or "12.34-"."""
    raise NotImplementedError
```

### Step 4: Run

`python -m pytest tests/unit/test_money.py --no-cov`

Expect: the last line contains `59 failed, 14 passed`. Most tests fail because the function is not written yet.

### Step 5: Code

In `src/finances/domain/money.py`, replace the line `raise NotImplementedError` with your implementation of `parse_money`. Keep the `def` line and the docstring as they are. Add the imports you need at the top of the file. Follow R1 to R5.

### Step 6: Run

`python -m ruff format src/finances/domain/money.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 7: Run

`python -m ruff check --fix src/finances/domain/money.py`

Expect: the last line is `All checks passed!`. A line saying an error was fixed is fine.

### Step 8: Run

`python -m pytest tests/unit/test_money.py --no-cov`

Expect: the last line contains `73 passed`

### Step 9: Write

Add this entry at the end of `docs/progress.md`, after one blank line. Replace `YYYY-MM-DD` with today's date. If you did anything these steps did not ask for, describe it on the "Deviations" line in place of `None`.

```markdown
## Phase 2d: parse_money (YYYY-MM-DD)
- Built: `parse_money` in `src/finances/domain/money.py`, with the full money tests in `tests/unit/test_money.py`. 89 tests pass. `money.py` coverage: 100%.
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

Expect: the last line contains `89 passed`, the output contains `Required test coverage of 85.0% reached`, and the row for `src/finances/domain/money.py` ends with `100%`.

### Step 14: Run

`git grep -n -E "float|round\(| / |print\(|logging" -- src/finances/domain/money.py`

Expect: no output.

### Step 15: Run

`git status --short`

Expect exactly these three lines and nothing else:

```
 M docs/progress.md
 M src/finances/domain/money.py
 M tests/unit/test_money.py
```

## If a Run step prints something else

| Step | Do this, then run the step again |
|---|---|
| 4 | If it reports an import error or a syntax error, the function from step 3 is missing or misplaced: redo step 3 |
| 7 | The error names a line: fix that line, then redo step 6 |
| 8 | Read the first failing test: it shows the input and what was expected. Change only the body of `parse_money`, then redo steps 6 and 7. If `test_format_cents` fails, you changed `format_cents`: put it back |
| 11 | Run step 10 again |
| 12 | Run `python -m ruff check --fix .`. If an error remains, it names a file and a line: fix that line |
| 13, `money.py` below `100%` | The "Missing" column lists lines of your function that no test reaches. Remove that code, then redo steps 6 to 8 |
| 14 | Each line printed breaks R4 or the logging rule. Rewrite that line without it, then redo steps 6 to 8 |
| 15 | A path that is not in the list is a file you must not have changed. Open it and undo your edit by hand. Do not use a git command |

## Final report

When step 15 matches, reply with the numbers 1 to 15, and after each Run step the last line of output you saw. Do not write "done" for a step you did not run.
