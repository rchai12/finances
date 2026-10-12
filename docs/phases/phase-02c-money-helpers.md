# Phase 2c: Money helpers

## Goal

Two pure functions that every later phase uses for money: `parse_money` turns text into integer cents, and `format_cents` turns integer cents into display text. `domain/money.py` is a critical module (`docs/testing.md`), so both the module and its tests are given below in full. The work is to create the three files exactly and make the checks pass.

## Read first

- `AGENTS.md`, section "Money and signs"
- `docs/progress.md`

## Starting state

- Phases 2a and 2b are done and committed. `git status --short` prints nothing.
- `python -m pytest` ends with `16 passed` and total coverage `98.43%`.
- `src/finances/domain/` does not exist yet.

## Files

| Path | Action |
|---|---|
| `src/finances/domain/__init__.py` | create, empty (zero bytes) |
| `src/finances/domain/money.py` | create |
| `tests/unit/test_money.py` | create |

Do not create or modify any other file, except `docs/progress.md`.

## Out of scope

- A `Money` class, currency conversion, rounding modes, locale formats (`1.234,56`), a `+` sign, enums, dataclasses, database code, `domain/models.py`.
- Changing the algorithm, the pattern, the error message, or a test. Do not add `try` / `except`, logging, or extra functions.
- **Git commands that discard work:** never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`. They undo correct work in other files. A mistake in one file is fixed by editing that file.

## Dependencies

None new.

## Requirements

**R1.** `src/finances/domain/__init__.py` exists and is empty.

**R2.** `src/finances/domain/money.py` has exactly this content:

```python
import re
from decimal import Decimal

_AMOUNT = re.compile(r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?|\.[0-9]{1,2}")


def parse_money(text: str) -> int:
    """Return integer cents for a money string such as "$1,234.56", "(12.34)" or "12.34-"."""
    s = text.strip()
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    elif s.endswith("-"):
        negative = True
        s = s[:-1]
    elif s.startswith("-"):
        negative = True
        s = s[1:]
    if s.startswith("$"):
        s = s[1:]
    if _AMOUNT.fullmatch(s) is None:
        raise ValueError("invalid money text")
    cents = int(Decimal(s.replace(",", "")) * 100)
    return -cents if negative else cents


def format_cents(cents: int) -> str:
    """Return display text for integer cents: 123456 -> "$1,234.56", -1234 -> "-$12.34"."""
    dollars, rest = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    return f"{sign}${dollars:,}.{rest:02d}"
```

**R3.** `tests/unit/test_money.py` has exactly this content:

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
    ("1,000,000.00", 100000000),
]
INVALID = ["", "   ", "abc", "12.345", "12.", "1,23.45", "1234,567", "$", "-", "--5", "(5", "5)"]
INVALID += ["(-5)", "-5-", "$-5", "$$5", "+5", "1 000", "$ 5", "- 5", "1e3", "NaN"]
FORMAT = [
    (123456, "$1,234.56"),
    (-1234, "-$12.34"),
    (0, "$0.00"),
    (5, "$0.05"),
    (-5, "-$0.05"),
    (100, "$1.00"),
    (100000000, "$1,000,000.00"),
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
        parse_money("\u0661\u0662")


def test_parse_money_returns_int() -> None:
    assert type(parse_money("12.34")) is int


@pytest.mark.parametrize(("cents", "expected"), FORMAT)
def test_format_cents(cents: int, expected: str) -> None:
    assert format_cents(cents) == expected


@pytest.mark.parametrize("n", [0, 1, -1, 99, -99, 100, 12345, -12345, 100000000])
def test_round_trip(n: int) -> None:
    assert parse_money(format_cents(n)) == n
```

**R4.** Do not change either block. If a test fails, the copy of `money.py` is wrong: replace the whole file with the R2 block again.

**R5.** `python -m pytest` ends with `72 passed`, and the coverage table shows `src/finances/domain/money.py` at `100%`.

## What the code does

This section explains R2. It is not a second set of instructions.

- Money is an `int` number of cents. `float` never appears: no `float(...)`, no `/` division, no `round(...)`.
- The error message is the constant `invalid money text`. It never contains the input (`AGENTS.md` privacy rules 4 and 5).
- Only ASCII digits are accepted: the pattern uses `[0-9]`, not `\d`.

### `parse_money`

The code follows these steps in this order.

1. `s = text.strip()`
2. Detect at most one negative marker, using `if` / `elif` / `elif` in this order:
   - if `s` starts with `(` and ends with `)`: negative, remove both characters;
   - otherwise, if `s` ends with `-`: negative, remove the last character;
   - otherwise, if `s` starts with `-`: negative, remove the first character.
3. If `s` now starts with `$`, remove that one character.
4. `s` must now match this pattern completely (`re.fullmatch`), otherwise raise `ValueError("invalid money text")`:

   ```python
   _AMOUNT = re.compile(r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?|\.[0-9]{1,2}")
   ```

5. Remove the commas, then `cents = int(Decimal(s) * 100)`. Return `-cents` if negative, else `cents`.

Nothing is stripped after step 1, so whitespace inside the text is an error.

Valid inputs:

| Input | Result |
|---|---|
| `"12.34"` | `1234` |
| `"-12.34"` | `-1234` |
| `"$1,234.56"` | `123456` |
| `"(12.34)"` | `-1234` |
| `"12.34-"` | `-1234` |
| `"  7 "` | `700` |
| `"-$12.34"` | `-1234` |
| `"($1,234.56)"` | `-123456` |
| `"$12.34-"` | `-1234` |
| `"0"` | `0` |
| `"-0.00"` | `0` |
| `".5"` | `50` |
| `"12.3"` | `1230` |
| `"1.15"` | `115` |
| `"1,000,000.00"` | `100000000` |

Each of these 22 inputs raises `ValueError`:

`""`, `"   "`, `"abc"`, `"12.345"`, `"12."`, `"1,23.45"`, `"1234,567"`, `"$"`, `"-"`, `"--5"`, `"(5"`, `"5)"`, `"(-5)"`, `"-5-"`, `"$-5"`, `"$$5"`, `"+5"`, `"1 000"`, `"$ 5"`, `"- 5"`, `"1e3"`, `"NaN"`

The exception message is exactly `invalid money text` for every invalid input. It does not include the input.

Only ASCII digits `0` to `9` are accepted. The pattern uses `[0-9]`, never `\d`.

The return value is an `int` (`type(result) is int`).

### `format_cents`

Format is an optional leading `-`, then `$`, then dollars with `,` thousands separators, then `.`, then exactly two cent digits. Compute dollars and cents with `divmod(abs(cents), 100)`.

| Input | Result |
|---|---|
| `123456` | `"$1,234.56"` |
| `-1234` | `"-$12.34"` |
| `0` | `"$0.00"` |
| `5` | `"$0.05"` |
| `-5` | `"-$0.05"` |
| `100` | `"$1.00"` |
| `100000000` | `"$1,000,000.00"` |

Round trip: `parse_money(format_cents(n)) == n` for every `n` in `[0, 1, -1, 99, -99, 100, 12345, -12345, 100000000]`.

## Work order

Activate the virtual environment first, so `python` is the project's interpreter. Run each command on its own line. Do not start a step until every check of the previous step passes.

A block copied from this spec may end without a final newline. That is why each step runs the formatter on the file it just wrote: `ruff format` adds the newline. Never skip it.

1. Create the folder `src/finances/domain/` and an empty file `src/finances/domain/__init__.py`.
   Check: `python -c "import finances.domain"` prints nothing and reports no error.
2. Create `src/finances/domain/money.py` from the R2 block. Then run:
   `python -m ruff format src/finances/domain/money.py`
   Checks:
   - `python -m ruff format --check src/finances/domain/money.py` prints `1 file already formatted`
   - `python -m ruff check src/finances/domain/money.py` prints `All checks passed!`
3. Create `tests/unit/test_money.py` from the R3 block. Then run:
   `python -m ruff format tests/unit/test_money.py`
   Checks:
   - `python -m ruff format --check tests/unit/test_money.py` prints `1 file already formatted`
   - `python -m pytest tests/unit/test_money.py --no-cov` ends with `56 passed`
4. Run `python -m ruff check .`
   Check: it prints `All checks passed!`
5. Add this entry at the end of `docs/progress.md`, after one blank line. Copy it, and replace `YYYY-MM-DD` with today's date. If you did anything this spec did not ask for, describe it on the "Deviations" line in place of `None`.

```markdown
## Phase 2c: Money helpers (YYYY-MM-DD)
- Built: `src/finances/domain/money.py` with `parse_money` and `format_cents`, and `tests/unit/test_money.py`. 72 tests pass. `money.py` coverage: 100%. TOTAL coverage: 98.77%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None
```

## Before you stop

Every item must be true. If one is not, fix it by editing that file, then run the whole list again.

- [ ] `python -m ruff check .` prints `All checks passed!`
- [ ] `python -m ruff format --check .` prints `18 files already formatted`
- [ ] `python -m pytest` ends with `72 passed` (exactly 72: the 16 from Phase 2b plus 56 new)
- [ ] The `python -m pytest` output contains `Total coverage: 98.77%`, and the row for `src/finances/domain/money.py` shows `100%`
- [ ] `git status --short` lists exactly these three lines and nothing else: `docs/progress.md`, `src/finances/domain/`, `tests/unit/test_money.py`
- [ ] `docs/progress.md` ends with the `## Phase 2c: Money helpers` entry
