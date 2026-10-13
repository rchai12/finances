# Phase 3a: the statement model and parsing helpers

## Goal

Start the statement importer with the pieces every bank parser will share: the data a parser produces (`Section`, `StatementLine`, `ParsedStatement`) and three helpers for the text statements print (`parse_amount`, `infer_year`, `parse_month_day`). The tests are given. **You write the members and fields of three classes and three function bodies.** The work is to do the 30 steps in order.

Nothing here reads a file or a database. Every function takes text or dates and returns a value.

## Read first

- `AGENTS.md`, sections "Running commands", "Privacy rules", and "Money and signs"
- `src/finances/domain/money.py` (`parse_money`, which `parse_amount` builds on)
- `src/finances/domain/models.py` (`AccountType`, and how `Account` is written as a frozen dataclass)

## Starting state

- Phase 2m is done and committed. `git status --short` prints nothing.
- `.venv/bin/python -m pytest` ends with `315 passed`.
- The folder `src/finances/ingest/` does not exist yet.
- These commands are written for macOS. On Windows, replace `.venv/bin/python` with `.\.venv\Scripts\python`.

## Files

| Path | Action |
|---|---|
| `src/finances/ingest/__init__.py` | create, empty |
| `src/finances/ingest/parsers/__init__.py` | create, empty |
| `src/finances/ingest/statement.py` | create from the block in step 3; you write the members and fields |
| `src/finances/ingest/parsers/helpers.py` | create from the block in step 4; you write three function bodies |
| `tests/unit/test_statement.py` | create from the block in step 5 |
| `tests/unit/test_parser_helpers.py` | create from the block in step 6 |
| `docs/progress.md` | add one entry at the end |

Do not create or modify any other file.

## What to build

Every requirement below is checked by at least one given test. If the tests pass and the coverage step passes, you are done: do not add checks that no requirement asks for.

### Part 1: the three classes in `statement.py`

- **R1.** `Section` has exactly these seven members, in this order:

  | Member | Value |
  |---|---|
  | `PAYMENTS_CREDITS` | `"payments_credits"` |
  | `PURCHASES` | `"purchases"` |
  | `FEES` | `"fees"` |
  | `INTEREST` | `"interest"` |
  | `DEPOSITS` | `"deposits"` |
  | `WITHDRAWALS` | `"withdrawals"` |
  | `CHECKS` | `"checks"` |

- **R2.** `StatementLine` has exactly these eight fields, in this order. The first five have no default.

  | Field | Type | Default |
  |---|---|---|
  | `posted_date` | `date` | |
  | `transaction_date` | `date \| None` | |
  | `description` | `str` | |
  | `amount_cents` | `int` | |
  | `section` | `Section` | |
  | `card_last4` | `str \| None` | `None` |
  | `cardholder` | `str \| None` | `None` |
  | `external_ref` | `str \| None` | `None` |

- **R3.** `ParsedStatement` has exactly these ten fields, in this order. The first nine have no default.

  | Field | Type | Default |
  |---|---|---|
  | `parser_name` | `str` | |
  | `institution` | `str` | |
  | `account_type` | `AccountType` | |
  | `account_last4` | `str` | |
  | `period_start` | `date` | |
  | `period_end` | `date` | |
  | `opening_balance_cents` | `int` | |
  | `closing_balance_cents` | `int` | |
  | `lines` | `list[StatementLine]` | |
  | `declared_section_totals` | `dict[Section, int]` | a new empty dict for each statement: `field(default_factory=dict)` |

### Part 2: `parse_amount`

```python
def parse_amount(text: str) -> int
```

Statements print amounts with signs that `parse_money` does not accept: `- $500.00`, `+ $4,139.73`, `= $4,124.21`. `parse_amount` tidies those up and then calls `parse_money`.

- **R4.** Spaces at either end are ignored. One leading `=` is removed, with any spaces after it: `"= $10.00"` gives `1000`.
- **R5.** After that, one leading `+` is removed, with any spaces after it: `"+ $3.00"` gives `300`. What follows a `+` must be a plain positive amount. If it starts with `-` or `(`, or ends with `-`, raise `ValueError("invalid money text")`: `"+-5"`, `"+(5)"`, and `"+5-"` are all errors.
- **R6.** A leading `-` may be followed by spaces, which are removed: `"- $500.00"` gives `-50000`.
- **R7.** The result of those steps goes to `parse_money`, and its answer is returned. Everything `parse_money` accepts still works (`"(12.34)"`, `"12.34-"`, `"36.49"`), and everything it rejects still raises its `ValueError("invalid money text")`.

### Part 3: `infer_year`

```python
def infer_year(month: int, day: int, period_start: date, period_end: date) -> date
```

Statement rows print a month and a day but no year. The year comes from the statement period.

- **R8.** The date must fall in the window from `EARLY_DAYS` (60) days before `period_start` to `LATE_DAYS` (7) days after `period_end`, both ends included. Rows can be dated a little outside the period: a purchase on Dec 23 can appear in a period that starts Dec 24.
- **R9.** Try three years: the year before `period_end.year`, that year, and the year after. Return the one date that falls in the window. For the period Dec 24 2025 to Jan 23 2026, month 12 day 23 gives `date(2025, 12, 23)` and month 1 day 5 gives `date(2026, 1, 5)`.
- **R10.** When none of the three falls in the window, raise `StatementError("date is outside the statement period")`. A month and day that do not exist in a given year (Feb 30, or Feb 29 outside a leap year) simply do not count for that year; they are not a separate error.
- **R11.** When more than one falls in the window (possible only for a period longer than about ten months), raise `StatementError("date matches more than one year")`.

### Part 4: `parse_month_day`

```python
def parse_month_day(text: str, period_start: date, period_end: date) -> date
```

- **R12.** After `collapse_ws`, the text must be one of these three shapes, and the result is `infer_year` for that month and day:

  | Shape | Examples |
  |---|---|
  | a three-letter English month name, one space, a one- or two-digit day; upper and lower case both accepted | `Jan 5`, `JAN 05`, `dec 23` |
  | one or two digits, `/`, one or two digits (month first) | `01/05`, `1/5` |
  | one or two digits, `-`, one or two digits (month first) | `01-05` |

- **R13.** Anything else raises `StatementError("unrecognized date text")`: a full month name, a year, extra characters, a missing part, digits that are not `0` to `9`. The whole text must match, not only its start.

### Facts you will need

These are how Python and the earlier code work, not a recipe.

- `class X(StrEnum):` members are written `NAME = "value"`. A frozen dataclass field is written `name: type` or `name: type = default`.
- `date(year, month, day)` raises `ValueError` when that day does not exist. `date - timedelta(days=60)` and `date + timedelta(days=7)` move a date. Dates compare with `<=`.
- `MONTHS` in `helpers.py` holds the twelve lower-case month names in order, so `MONTHS.index("jan") + 1` is `1`.
- `re.fullmatch(pattern, text)` returns a match only when the whole text fits the pattern, and `None` otherwise. In a pattern write `[0-9]` for a digit, not `\d`: `\d` also accepts digits from other alphabets.
- `infer_year` already raises the right error for a month or day that is out of range, so `parse_month_day` can pass on whatever numbers it read.
- `text.lstrip()` removes spaces from the left; `text.startswith(("-", "("))` tests several beginnings at once.

## Rules

- Do not change the test files. If a test fails, the source file is wrong.
- Do not change the given parts of the source files: the docstrings, the imports already there, `StatementError`, the class lines and `@dataclass(frozen=True)` lines, `EARLY_DAYS`, `LATE_DAYS`, `MONTHS`, `collapse_ws`, and the three `def` lines.
- Error messages are the constant texts given above. They never contain the text that was being parsed.
- Do not use `float`, and do not use `datetime.strptime`: its month names change with the computer's language setting.
- Do not print or log anything.
- Do not change anything under `src/finances/domain/`, `src/finances/db/`, or `src/finances/cli/`.
- Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.

## How to work

- Each step is **one action**: **Write** (use the block given), **Code** (write code yourself), or **Run** (one command).
- Do all 30 steps, in order. Do not skip a Run step, and do not merge steps.
- After each Run step, compare the output with "Expect". If it differs, use the table under "If a Run step prints something else".
- Type every command exactly as written, starting with `.venv/bin/python`. Do not shorten it to `python`, `python3`, `pip`, `ruff`, or `pytest`.
- Do not activate the virtual environment and do not create one. `.venv/` already exists.

## Steps

### Step 1: Write

Create an empty file `src/finances/ingest/__init__.py`. Create the folder `src/finances/ingest/` first; it does not exist yet.

### Step 2: Write

Create an empty file `src/finances/ingest/parsers/__init__.py`. Create the folder `src/finances/ingest/parsers/` first.

### Step 3: Write

Create `src/finances/ingest/statement.py` with exactly this content:

```python
"""What a parser produces from one statement. This module holds data only, no parsing."""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from finances.domain.models import AccountType


class StatementError(Exception):
    """Raised when a statement cannot be read, recognized, or parsed."""


class Section(StrEnum):
    """The part of a statement a line was printed in."""


@dataclass(frozen=True)
class StatementLine:
    """One transaction as printed. Amounts are from the account holder's side."""


@dataclass(frozen=True)
class ParsedStatement:
    """One statement: its header, its balances, and its lines."""
```

### Step 4: Write

Create `src/finances/ingest/parsers/helpers.py` with exactly this content:

```python
"""Small parsing helpers shared by every statement parser."""

from datetime import date, timedelta

from finances.domain.money import parse_money
from finances.ingest.statement import StatementError

EARLY_DAYS = 60
LATE_DAYS = 7
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


def collapse_ws(text: str) -> str:
    """Return text with outer whitespace removed and inner runs of whitespace made one space."""
    return " ".join(text.split())


def parse_amount(text: str) -> int:
    """Return integer cents for an amount as statements print it, such as "- $12.00"."""
    raise NotImplementedError


def infer_year(month: int, day: int, period_start: date, period_end: date) -> date:
    """Return the date with this month and day that belongs to the statement period."""
    raise NotImplementedError


def parse_month_day(text: str, period_start: date, period_end: date) -> date:
    """Return the date for text such as "Jan 5", "01/05" or "01-05"."""
    raise NotImplementedError
```

### Step 5: Write

Create `tests/unit/test_statement.py` with exactly this content:

```python
import dataclasses
import typing
from datetime import date
from enum import StrEnum

import pytest

from finances.domain.models import AccountType
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

SECTIONS = [
    ("PAYMENTS_CREDITS", "payments_credits"),
    ("PURCHASES", "purchases"),
    ("FEES", "fees"),
    ("INTEREST", "interest"),
    ("DEPOSITS", "deposits"),
    ("WITHDRAWALS", "withdrawals"),
    ("CHECKS", "checks"),
]


def make_line(**changes: object) -> StatementLine:
    values = {
        "posted_date": date(2026, 1, 6),
        "transaction_date": date(2026, 1, 5),
        "description": "ACME COFFEE #12",
        "amount_cents": -450,
        "section": Section.PURCHASES,
    }
    values.update(changes)
    return StatementLine(**values)


def make_statement(**changes: object) -> ParsedStatement:
    values = {
        "parser_name": "fake_bank",
        "institution": "Fake Bank",
        "account_type": AccountType.CREDIT_CARD,
        "account_last4": "1111",
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 31),
        "opening_balance_cents": -10000,
        "closing_balance_cents": -10450,
        "lines": [make_line()],
    }
    values.update(changes)
    return ParsedStatement(**values)


def names(cls: type) -> list[str]:
    return [field.name for field in dataclasses.fields(cls)]


def with_defaults(cls: type) -> list[str]:
    missing = dataclasses.MISSING
    return [
        field.name
        for field in dataclasses.fields(cls)
        if field.default is not missing or field.default_factory is not missing
    ]


def test_statement_error_is_an_exception() -> None:
    assert issubclass(StatementError, Exception)
    assert not issubclass(StatementError, ValueError)


def test_section_is_a_str_enum_with_seven_members_in_order() -> None:
    assert issubclass(Section, StrEnum)
    assert [(member.name, member.value) for member in Section] == SECTIONS


@pytest.mark.parametrize(("name", "value"), SECTIONS)
def test_section_values(name: str, value: str) -> None:
    assert Section[name].value == value
    assert str(Section[name]) == value
    assert Section(value) is Section[name]


def test_statement_line_fields_in_order() -> None:
    assert names(StatementLine) == [
        "posted_date",
        "transaction_date",
        "description",
        "amount_cents",
        "section",
        "card_last4",
        "cardholder",
        "external_ref",
    ]


def test_statement_line_field_types() -> None:
    assert typing.get_type_hints(StatementLine) == {
        "posted_date": date,
        "transaction_date": date | None,
        "description": str,
        "amount_cents": int,
        "section": Section,
        "card_last4": str | None,
        "cardholder": str | None,
        "external_ref": str | None,
    }


def test_only_the_last_three_line_fields_have_a_default() -> None:
    assert with_defaults(StatementLine) == ["card_last4", "cardholder", "external_ref"]


def test_only_the_totals_field_of_a_statement_has_a_default() -> None:
    assert with_defaults(ParsedStatement) == ["declared_section_totals"]


def test_statement_line_optional_fields_default_to_none() -> None:
    line = make_line()
    assert (line.card_last4, line.cardholder, line.external_ref) == (None, None, None)


def test_statement_line_needs_its_first_five_fields() -> None:
    with pytest.raises(TypeError):
        StatementLine(date(2026, 1, 6), None, "ACME COFFEE", -450)


def test_statement_line_keeps_its_values() -> None:
    line = make_line(card_last4="2222", cardholder="JANE DOE", external_ref="7838")
    assert line.posted_date == date(2026, 1, 6)
    assert line.transaction_date == date(2026, 1, 5)
    assert line.description == "ACME COFFEE #12"
    assert line.amount_cents == -450
    assert line.section is Section.PURCHASES
    assert (line.card_last4, line.cardholder, line.external_ref) == ("2222", "JANE DOE", "7838")


def test_statement_line_is_frozen_and_compares_by_value() -> None:
    line = make_line()
    with pytest.raises(dataclasses.FrozenInstanceError):
        line.amount_cents = 0
    assert line == make_line()
    assert line != make_line(amount_cents=-451)
    assert hash(line) == hash(make_line())


def test_parsed_statement_fields_in_order() -> None:
    assert names(ParsedStatement) == [
        "parser_name",
        "institution",
        "account_type",
        "account_last4",
        "period_start",
        "period_end",
        "opening_balance_cents",
        "closing_balance_cents",
        "lines",
        "declared_section_totals",
    ]


def test_parsed_statement_field_types() -> None:
    assert typing.get_type_hints(ParsedStatement) == {
        "parser_name": str,
        "institution": str,
        "account_type": AccountType,
        "account_last4": str,
        "period_start": date,
        "period_end": date,
        "opening_balance_cents": int,
        "closing_balance_cents": int,
        "lines": list[StatementLine],
        "declared_section_totals": dict[Section, int],
    }


def test_parsed_statement_keeps_its_values() -> None:
    statement = make_statement(declared_section_totals={Section.PURCHASES: -450})
    assert statement.parser_name == "fake_bank"
    assert statement.institution == "Fake Bank"
    assert statement.account_type is AccountType.CREDIT_CARD
    assert statement.account_last4 == "1111"
    assert (statement.period_start, statement.period_end) == (date(2026, 1, 1), date(2026, 1, 31))
    assert statement.opening_balance_cents == -10000
    assert statement.closing_balance_cents == -10450
    assert statement.lines == [make_line()]
    assert statement.declared_section_totals == {Section.PURCHASES: -450}


def test_parsed_statement_totals_default_to_an_empty_dict_of_its_own() -> None:
    first = make_statement()
    second = make_statement()
    assert first.declared_section_totals == {}
    assert first.declared_section_totals is not second.declared_section_totals


def test_parsed_statement_needs_its_first_nine_fields() -> None:
    with pytest.raises(TypeError):
        ParsedStatement("fake_bank", "Fake Bank", AccountType.CHECKING, "1111")


def test_parsed_statement_is_frozen() -> None:
    statement = make_statement()
    with pytest.raises(dataclasses.FrozenInstanceError):
        statement.closing_balance_cents = 0
```

### Step 6: Write

Create `tests/unit/test_parser_helpers.py` with exactly this content:

```python
from datetime import date

import pytest

from finances.ingest.parsers.helpers import collapse_ws, infer_year, parse_amount, parse_month_day
from finances.ingest.statement import StatementError

WRAP = (date(2025, 12, 24), date(2026, 1, 23))
DECEMBER = (date(2025, 12, 1), date(2025, 12, 28))
LEAP = (date(2024, 2, 1), date(2024, 2, 29))
NOT_LEAP = (date(2025, 2, 1), date(2025, 2, 28))
QUARTER = (date(2026, 7, 1), date(2026, 9, 30))
LONG = (date(2025, 1, 1), date(2026, 6, 30))
OUTSIDE = "date is outside the statement period"
AMBIGUOUS = "date matches more than one year"
UNRECOGNIZED = "unrecognized date text"

VALID_AMOUNTS = [
    ("$3.00", 300),
    ("36.49", 3649),
    ("-43.19", -4319),
    ("-$6,985.57", -698557),
    ("- $500.00", -50000),
    ("-   $1.00", -100),
    ("-\t$2.00", -200),
    ("  - $1.00  ", -100),
    ("+$759.22", 75922),
    ("+ $4,139.73", 413973),
    ("+0.00", 0),
    ("=$10.00", 1000),
    ("= $4,124.21", 412421),
    ("= - $5.00", -500),
    ("= + $5.00", 500),
    ("(12.34)", -1234),
    ("12.34-", -1234),
]
INVALID_AMOUNTS = [
    "",
    "=",
    "+",
    "-",
    "-$",
    "abc",
    "= abc",
    "$ 5",
    "5 +",
    "+-5",
    "+ -5",
    "+(5)",
    "+5-",
    "++5",
    "+ +5",
    "--5",
    "- -5",
    "- (5)",
    "==5",
    "= = 5",
    "+ = 5",
    "- = 5",
]
YEARS = [
    (WRAP, 12, 23, date(2025, 12, 23)),
    (WRAP, 12, 24, date(2025, 12, 24)),
    (WRAP, 1, 5, date(2026, 1, 5)),
    (WRAP, 1, 23, date(2026, 1, 23)),
    (WRAP, 1, 30, date(2026, 1, 30)),
    (WRAP, 10, 25, date(2025, 10, 25)),
    (DECEMBER, 12, 15, date(2025, 12, 15)),
    (DECEMBER, 1, 2, date(2026, 1, 2)),
    (DECEMBER, 1, 4, date(2026, 1, 4)),
    (LEAP, 2, 29, date(2024, 2, 29)),
    (QUARTER, 8, 17, date(2026, 8, 17)),
]
OUTSIDE_DATES = [
    (WRAP, 1, 31),
    (WRAP, 10, 24),
    (WRAP, 6, 15),
    (DECEMBER, 1, 5),
    (NOT_LEAP, 2, 29),
    (WRAP, 2, 30),
    (WRAP, 4, 31),
    (WRAP, 13, 1),
    (WRAP, 0, 5),
    (WRAP, 1, 0),
]
MONTH_DAY = [
    ("Dec 23", date(2025, 12, 23)),
    ("Jan 5", date(2026, 1, 5)),
    ("Jan 05", date(2026, 1, 5)),
    ("JAN 5", date(2026, 1, 5)),
    ("jan 5", date(2026, 1, 5)),
    ("Jan   5", date(2026, 1, 5)),
    ("  Jan 5  ", date(2026, 1, 5)),
    ("01/05", date(2026, 1, 5)),
    ("1/5", date(2026, 1, 5)),
    ("12/23", date(2025, 12, 23)),
    ("01-05", date(2026, 1, 5)),
    ("12-23", date(2025, 12, 23)),
]
UNRECOGNIZED_DATES = [
    "",
    "Jan",
    "5",
    "Jan5",
    "Janu 5",
    "January 5",
    "Xyz 5",
    "Jan 5th",
    "Jan -5",
    "Jan 123",
    "01/05/2026",
    "1/5/26",
    "01.05",
    "01/",
    "/05",
    "123/05",
    "١/٥",
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ACME COFFEE", "ACME COFFEE"),
        ("  ACME   COFFEE  ", "ACME COFFEE"),
        ("ACME\tCOFFEE\n#12", "ACME COFFEE #12"),
        ("   ", ""),
    ],
)
def test_collapse_ws(text: str, expected: str) -> None:
    assert collapse_ws(text) == expected


@pytest.mark.parametrize(("text", "expected"), VALID_AMOUNTS)
def test_parse_amount_valid(text: str, expected: int) -> None:
    result = parse_amount(text)
    assert result == expected
    assert type(result) is int


@pytest.mark.parametrize("text", INVALID_AMOUNTS)
def test_parse_amount_invalid(text: str) -> None:
    with pytest.raises(ValueError) as excinfo:
        parse_amount(text)
    assert str(excinfo.value) == "invalid money text"


@pytest.mark.parametrize(("period", "month", "day", "expected"), YEARS)
def test_infer_year(period: tuple[date, date], month: int, day: int, expected: date) -> None:
    assert infer_year(month, day, *period) == expected


@pytest.mark.parametrize(("period", "month", "day"), OUTSIDE_DATES)
def test_infer_year_outside_the_period(period: tuple[date, date], month: int, day: int) -> None:
    with pytest.raises(StatementError) as excinfo:
        infer_year(month, day, *period)
    assert str(excinfo.value) == OUTSIDE


def test_infer_year_refuses_to_guess_between_two_years() -> None:
    with pytest.raises(StatementError) as excinfo:
        infer_year(3, 15, *LONG)
    assert str(excinfo.value) == AMBIGUOUS


@pytest.mark.parametrize(("text", "expected"), MONTH_DAY)
def test_parse_month_day(text: str, expected: date) -> None:
    assert parse_month_day(text, *WRAP) == expected


@pytest.mark.parametrize("month", range(1, 13))
def test_parse_month_day_knows_every_month(month: int) -> None:
    name = date(2026, month, 15).strftime("%b")
    period = (date(2026, month, 1), date(2026, month, 28))
    assert parse_month_day(f"{name} 15", *period) == date(2026, month, 15)


@pytest.mark.parametrize("text", UNRECOGNIZED_DATES)
def test_parse_month_day_unrecognized(text: str) -> None:
    with pytest.raises(StatementError) as excinfo:
        parse_month_day(text, *WRAP)
    assert str(excinfo.value) == UNRECOGNIZED


@pytest.mark.parametrize("text", ["Jun 15", "06/15", "06-15", "Feb 30", "13/01", "00/10"])
def test_parse_month_day_outside_the_period(text: str) -> None:
    with pytest.raises(StatementError) as excinfo:
        parse_month_day(text, *WRAP)
    assert str(excinfo.value) == OUTSIDE
```

### Step 7: Run

`.venv/bin/python -m ruff format src/finances/ingest tests/unit/test_statement.py tests/unit/test_parser_helpers.py`

Expect: the output ends with `reformatted` or `left unchanged`. Both are fine.

### Step 8: Run

`.venv/bin/python -m pytest tests/unit/test_statement.py tests/unit/test_parser_helpers.py --no-cov`

Expect: the last line contains `128 failed, 7 passed`. The tests fail because the classes are empty and the functions are not written yet.

### Step 9: Code

In `src/finances/ingest/statement.py`, add the seven members to `Section`, the eight fields to `StatementLine`, and the ten fields to `ParsedStatement`, each below its docstring. Follow Part 1 (R1 to R3).

### Step 10: Run

`.venv/bin/python -m ruff format src/finances/ingest/statement.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 11: Run

`.venv/bin/python -m pytest tests/unit/test_statement.py --no-cov`

Expect: the last line contains `23 passed`

### Step 12: Code

In `src/finances/ingest/parsers/helpers.py`, replace the first `raise NotImplementedError` with your implementation of `parse_amount`. Follow Part 2 (R4 to R7).

### Step 13: Run

`.venv/bin/python -m ruff format src/finances/ingest/parsers/helpers.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 14: Run

`.venv/bin/python -m pytest tests/unit/test_parser_helpers.py --no-cov -k "collapse_ws or parse_amount"`

Expect: the last line contains `43 passed, 69 deselected`

### Step 15: Code

In `src/finances/ingest/parsers/helpers.py`, replace the next `raise NotImplementedError` with your implementation of `infer_year`. Follow Part 3 (R8 to R11).

### Step 16: Run

`.venv/bin/python -m ruff format src/finances/ingest/parsers/helpers.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 17: Run

`.venv/bin/python -m pytest tests/unit/test_parser_helpers.py --no-cov -k "infer_year"`

Expect: the last line contains `22 passed, 90 deselected`

### Step 18: Code

In `src/finances/ingest/parsers/helpers.py`, replace the last `raise NotImplementedError` with your implementation of `parse_month_day`. Follow Part 4 (R12 and R13). If you need an import, add it at the top of the file.

### Step 19: Run

`.venv/bin/python -m ruff format src/finances/ingest/parsers/helpers.py`

Expect: `1 file reformatted` or `1 file left unchanged`. Both are fine.

### Step 20: Run

`.venv/bin/python -m ruff check --fix src/finances/ingest`

Expect: the last line is `All checks passed!`. A line saying an error was fixed is fine.

### Step 21: Run

`.venv/bin/python -m pytest tests/unit/test_statement.py tests/unit/test_parser_helpers.py --no-cov`

Expect: the last line contains `135 passed`

### Step 22: Run

`.venv/bin/python -m pytest tests/unit/test_statement.py tests/unit/test_parser_helpers.py -o addopts="" --import-mode=importlib --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

Expect: the output contains `Required test coverage of 100% reached`.

This step checks that every line you wrote is used by a test. If it prints `FAIL Required test coverage of 100% not reached`, the "Missing" column lists line numbers that no test runs. Those lines are code that no requirement asks for: delete them. Do not go on until this step passes.

### Step 23: Write

Add this entry at the end of `docs/progress.md`, after one blank line. Replace `YYYY-MM-DD` with today's date. If you did anything these steps did not ask for, describe it on the "Deviations" line in place of `None`.

```markdown
## Phase 3a: the statement model and parsing helpers (YYYY-MM-DD)
- Built: `StatementError`, `Section`, `StatementLine`, and `ParsedStatement` in `src/finances/ingest/statement.py`; `collapse_ws`, `parse_amount`, `infer_year`, and `parse_month_day` in `src/finances/ingest/parsers/helpers.py`; `tests/unit/test_statement.py` and `tests/unit/test_parser_helpers.py`. 450 tests pass. `finances.ingest` coverage: 100%.
- Deviations from spec (and why): None
- Follow-ups / known issues: None
```

### Step 24: Run

`.venv/bin/python -m ruff format .`

Expect: `41 files left unchanged`. If it says a file was reformatted, that is fine: go on to step 25.

### Step 25: Run

`.venv/bin/python -m ruff format --check .`

Expect: `41 files already formatted`

### Step 26: Run

`.venv/bin/python -m ruff check .`

Expect: `All checks passed!`

### Step 27: Run

`.venv/bin/python -m pytest`

Expect: the last line contains `450 passed`, and the output contains `Required test coverage of 85.0% reached`.

### Step 28: Run

`.venv/bin/python -m pytest tests/unit/test_statement.py tests/unit/test_parser_helpers.py -o addopts="" --import-mode=importlib --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

Expect: the output contains `Required test coverage of 100% reached`. This is step 22 again, in case a later step changed a file.

### Step 29: Run

`git grep -n --untracked -F -e "\d" -e "strptime" -e "float" -e "print(" -e "logging" -- src/finances/ingest`

Expect: no output.

### Step 30: Run

`git status --short`

Expect exactly these four lines and nothing else:

```
 M docs/progress.md
?? src/finances/ingest/
?? tests/unit/test_parser_helpers.py
?? tests/unit/test_statement.py
```

## If a Run step prints something else

| Step | Do this, then run the step again |
|---|---|
| any | If the output says `command not found`, `No such file`, or `No module named ruff` (or `pytest`), the command was not typed as written. Type it again starting with `.venv/bin/python`. If `.venv/bin/python` itself is missing, stop and report that; do not create a virtual environment |
| 8 | If it reports an import error or a syntax error, the message names a file: redo the Write step for that file (steps 1 to 6) |
| 11 | Read the first failing test: `section` tests are R1, `statement_line` tests are R2, `parsed_statement` tests are R3. The test shows the expected names, order, or types. Change only that class, then redo step 10. If the error is raised while importing `statement.py`, a field without a default comes after one with a default: put the fields in the order of the tables |
| 14 | Read the first failing test: it shows the text and the expected number. Change only the body of `parse_amount`, then redo step 13 |
| 17 | Read the first failing test: it shows the period, the month, and the day. `outside_the_period` is R10, `two_years` is R11, the rest are R8 and R9. Change only the body of `infer_year`, then redo step 16 |
| 20 | The error names a line: fix that line, then redo step 19 |
| 21 | Read the first failing test: `unrecognized` is R13, the other `parse_month_day` tests are R12. Change only the body of `parse_month_day`, then redo steps 19 and 20. If an earlier test fails, you changed an earlier function: put it back |
| 22 or 28 | Delete the lines listed under "Missing", then redo steps 19 to 21 |
| 25 | Run step 24 again |
| 26 | Run `.venv/bin/python -m ruff check --fix .`. If an error remains, it names a file and a line: fix that line |
| 27 | A test in another file fails only if a file outside this phase was changed. Find it with step 30 and undo the edit by hand |
| 29 | Each line printed breaks a rule. Rewrite that line without it (`[0-9]` in place of `\d`), then redo steps 19 to 22 |
| 30 | A path that is not in the list is a file you must not have changed. Open it and undo your edit by hand. Do not use a git command |

## Final report

When step 30 matches, reply with the numbers 1 to 30, and after each Run step the last line of output you saw. Do not write "done" for a step you did not run.
