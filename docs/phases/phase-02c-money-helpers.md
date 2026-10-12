# Phase 2c: Money helpers

## Goal

Two pure functions that every later phase uses for money: `parse_money` turns text into integer cents, and `format_cents` turns integer cents into display text. Nothing else.

## Read first

- `AGENTS.md`, section "Money and signs"
- `docs/testing.md` (`domain/money.py` is a critical module: every branch must be covered)
- `docs/progress.md`

## Starting state

- Phases 2a and 2b are done: `python -m pytest` runs 16 tests, measures branch coverage, and fails below 85%.
- `src/finances/domain/` does not exist yet.

## Files

| Path | Action |
|---|---|
| `src/finances/domain/__init__.py` | create, empty |
| `src/finances/domain/money.py` | create |
| `tests/unit/test_money.py` | create |

Do not create or modify any other file, except `docs/progress.md`.

## Out of scope

A `Money` class, currency conversion, rounding modes, locale formats (`1.234,56`), a `+` sign, enums, dataclasses, database code. Do not add `domain/models.py`.

## Dependencies

None new. `money.py` imports only `decimal` and `re` from the standard library.

## Rules that apply here

- Money is an `int` number of cents. `float` must not appear anywhere in `money.py`: no `float(...)`, no `/` division, no `round(...)`.
- Error messages never contain the input text (`AGENTS.md` privacy rules 4 and 5).
- No `try` / `except` is needed in `money.py`. The pattern in R1 rejects every invalid input before conversion.
- No `try` / `except` is needed in `money.py`. The pattern in R1 rejects every invalid input before conversion.

## Requirements

```python
def parse_money(text: str) -> int: ...
def format_cents(cents: int) -> str: ...
```

### `parse_money`

**R1.** Follow these steps in this order.

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

**R2.** Valid inputs:

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

**R3.** Each of these 22 inputs raises `ValueError`:

`""`, `"   "`, `"abc"`, `"12.345"`, `"12."`, `"1,23.45"`, `"1234,567"`, `"$"`, `"-"`, `"--5"`, `"(5"`, `"5)"`, `"(-5)"`, `"-5-"`, `"$-5"`, `"$$5"`, `"+5"`, `"1 000"`, `"$ 5"`, `"- 5"`, `"1e3"`, `"NaN"`

**R4.** The exception message is exactly `invalid money text` for every invalid input. It does not include the input.

**R5.** Only ASCII digits `0` to `9` are accepted. The pattern uses `[0-9]`, never `\d`.

**R6.** The return value is an `int` (`type(result) is int`).

### `format_cents`

**R7.** Format is an optional leading `-`, then `$`, then dollars with `,` thousands separators, then `.`, then exactly two cent digits. Compute dollars and cents with `divmod(abs(cents), 100)`.

| Input | Result |
|---|---|
| `123456` | `"$1,234.56"` |
| `-1234` | `"-$12.34"` |
| `0` | `"$0.00"` |
| `5` | `"$0.05"` |
| `-5` | `"-$0.05"` |
| `100` | `"$1.00"` |
| `100000000` | `"$1,000,000.00"` |

**R8.** Round trip: `parse_money(format_cents(n)) == n` for every `n` in `[0, 1, -1, 99, -99, 100, 12345, -12345, 100000000]`.

## Tests

Create `tests/unit/test_money.py` with **exactly** this content. Copy it unchanged: do not rename, add, remove, or reorder tests, and do not change a value.

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

If a test fails, the bug is in `money.py`. Fix `money.py`. Never change the test file to make a test pass.

## Work order

Activate the virtual environment first, so `python` is the project's interpreter. Run each command on its own line. Do not start a step until the check of the previous step passes.

1. Create `src/finances/domain/__init__.py` as an empty file.
2. Create `tests/unit/test_money.py` from the block above.
   Check: `python -m pytest tests/unit/test_money.py --no-cov` fails with an import error for `finances.domain.money`. That is expected at this step.
3. Create `src/finances/domain/money.py` with `parse_money` (R1 to R6) and `format_cents` (R7).
   Check: `python -m pytest tests/unit/test_money.py --no-cov` ends with `56 passed`.
4. Run `python -m ruff format .` and then `python -m ruff check --fix .`.
5. Append the entry to `docs/progress.md` using its template, with the heading `## Phase 2c: Money helpers (YYYY-MM-DD)` and today's date.

## Before you stop

Every item must be true. If one is not, fix it and run the whole list again.

- [ ] `python -m ruff check .` prints `All checks passed!`
- [ ] `python -m ruff format --check .` reports no file to reformat
- [ ] `python -m pytest` ends with `72 passed` (exactly 72: the 16 that exist after Phase 2b plus 56 new)
- [ ] In the coverage table, the row for `src/finances/domain/money.py` shows `100%` with nothing under `Missing`
- [ ] `git status --short` lists only `src/finances/domain/` (holding `__init__.py` and `money.py`), `tests/unit/test_money.py`, and `docs/progress.md`
- [ ] `tests/unit/test_money.py` is still identical to the block in this spec
- [ ] `docs/progress.md` ends with the `## Phase 2c: Money helpers` entry, with all three template lines filled in
