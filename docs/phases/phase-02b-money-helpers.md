# Phase 2b: Money helpers

## Goal

Two pure functions that every later phase uses for money: `parse_money` turns text into integer cents, and `format_cents` turns integer cents into display text. Nothing else.

## Read first

- `AGENTS.md`, section "Money and signs"
- `docs/testing.md` (`domain/money.py` is a critical module: every branch must be covered)
- `docs/progress.md`

## Starting state

- Phase 2a is done: `pytest` measures branch coverage and fails below 85%.
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

## Tests (`tests/unit/test_money.py`)

Use exactly these seven test names.

| Test name | Covers | Content |
|---|---|---|
| `test_parse_money_valid` | R1, R2 | `pytest.mark.parametrize` over every row of the R2 table |
| `test_parse_money_invalid` | R3 | `pytest.mark.parametrize` over every R3 input, each inside `pytest.raises(ValueError)` |
| `test_parse_money_error_does_not_echo_input` | R4 | `parse_money("12.345")` raises; `str(excinfo.value) == "invalid money text"` |
| `test_parse_money_rejects_non_ascii_digits` | R5 | `parse_money("١٢")` raises `ValueError` |
| `test_parse_money_returns_int` | R6 | `type(parse_money("12.34")) is int` |
| `test_format_cents` | R7 | `pytest.mark.parametrize` over every row of the R7 table |
| `test_round_trip` | R8 | `pytest.mark.parametrize` over the R8 list |

## Acceptance criteria

Run each command on its own line:

```
ruff check .
ruff format --check .
pytest
```

- All three succeed. `pytest` runs at least 72 tests.
- In the coverage table, the row for `src/finances/domain/money.py` shows 100% with nothing under `Missing`.

## Done

Append the entry to `docs/progress.md` using its template, with the heading `## Phase 2b: Money helpers (YYYY-MM-DD)`.
