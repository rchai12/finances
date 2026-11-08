# Phase 46: Marcus CD statements

## Goal

The owner's Marcus CD statements are refused on upload with `unrecognized statement format`. A check of the owner's two real CD statements, counts and yes or no answers only, found:
- both carry `Goldman Sachs Bank USA` and the heading `CD ACCOUNT STATEMENT` once on the first page, as the importer reads it;
- neither carries `ONLINE SAVINGS ACCOUNT STATEMENT`, the heading `MarcusSavingsParser.detect` requires;
- with detection set aside, `MarcusSavingsParser.parse` reads both, and both reconcile.

With the owner's choices (2026-11-08):

- the Marcus parser also recognizes a CD statement;
- a CD imports as a `savings` account, under the same parser name `marcus_savings`, so nothing stored or listed changes.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/ingest/parsers/marcus.py`, `docs/statement-formats.md` section 5 (updated for this phase), `tests/unit/test_marcus_parser.py`

## Starting state

N is `4302` when Phase 45c is the last phase built. **Sections: parsers.** No migration.

## Scope

| Path | What changes |
|---|---|
| `src/finances/ingest/parsers/marcus.py` | `detect`; the module docstring names CD statements too (R1) |
| `tests/fixtures/statements/marcus/cd.txt` | new: given (synthetic) |
| `tests/unit/test_marcus_cd.py` | new: given |
| `docs/progress.md` | one new entry |

## Out of scope

- A `cd` account type; reading the maturity date, term, or rate; a parser of its own for CDs; renaming `MarcusSavingsParser` or `marcus_savings`.

## Dependencies

None new.

## Design

`detect(first_page)` is true when `Goldman Sachs Bank USA` is on the page and so is `ONLINE SAVINGS ACCOUNT STATEMENT` or `CD ACCOUNT STATEMENT`, each as written (case matters, as today). `parse` is unchanged: a CD's summary lines (term, yield, maturity date) match no row and are ignored, which the given fixture shows.

## Requirements

- **R1.** `detect` as designed; every earlier Marcus test passes unchanged.

## Given fixture

`tests/fixtures/statements/marcus/cd.txt` (synthetic):

```text
Marcus by Goldman Sachs                    CD ACCOUNT STATEMENT
Goldman Sachs Bank USA, Member FDIC
Statement Period      07/01/2026 to 09/30/2026
Account Number      300200007777

CD SUMMARY
Term      12 Months
Annual Percentage Yield      4.40%
Maturity Date      03/31/2027

ACCOUNT ACTIVITY
Date          Description                                        Credits      Debits      Balance
07/01/2026   Beginning Balance                                                  $5,000.00
09/30/2026   Interest Paid                                           $54.61              $5,054.61
09/30/2026   Ending Balance                                                     $5,054.61

INTEREST SUMMARY
Interest Paid Year to Date      $108.12
```

## Given tests

7 tests in one file. Do not change them. Five of them pass before the change: they pin what must not move (the parse, and the headings that stay refused).

`tests/unit/test_marcus_cd.py`

```python
from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers import detect_parser
from finances.ingest.parsers.marcus import MarcusSavingsParser
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import Section, StatementLine

CD = Path(__file__).parent.parent / "fixtures" / "statements" / "marcus" / "cd.txt"


def pages() -> list[str]:
    return CD.read_text(encoding="utf-8").split("\f")


def test_a_cd_statement_is_detected() -> None:
    assert MarcusSavingsParser().detect(pages()[0]) is True
    assert detect_parser(pages()[0]).name == "marcus_savings"


def test_a_cd_statement_parses_as_savings() -> None:
    statement = MarcusSavingsParser().parse(pages())
    assert (
        statement.parser_name,
        statement.institution,
        statement.account_type,
        statement.account_last4,
        statement.period_start,
        statement.period_end,
        statement.opening_balance_cents,
        statement.closing_balance_cents,
    ) == (
        "marcus_savings",
        "Marcus by Goldman Sachs",
        AccountType.SAVINGS,
        "7777",
        date(2026, 7, 1),
        date(2026, 9, 30),
        500000,
        505461,
    )
    assert statement.lines == [
        StatementLine(date(2026, 9, 30), None, "Interest Paid", 5461, Section.INTEREST)
    ]
    assert reconcile(statement).ok


@pytest.mark.parametrize(
    "first_page",
    [
        "CD ACCOUNT STATEMENT",
        "Marcus by Goldman Sachs\nCD ACCOUNT STATEMENT",
        "Goldman Sachs Bank USA\nCd Account Statement",
        "Goldman Sachs Bank USA\nCD STATEMENT",
    ],
)
def test_a_cd_heading_alone_or_misspelt_is_not_detected(first_page: str) -> None:
    assert MarcusSavingsParser().detect(first_page) is False


def test_both_headings_with_the_bank_are_detected() -> None:
    for heading in ("ONLINE SAVINGS ACCOUNT STATEMENT", "CD ACCOUNT STATEMENT"):
        assert MarcusSavingsParser().detect(f"{heading}\nGoldman Sachs Bank USA, Member FDIC")
```

## Tests to write

None: the given file covers the phase.

## Rules for this phase

- No earlier test changes.
- Do not open, print, or copy anything from `data/samples/` (AGENTS.md privacy rule 6). The owner runs the real-sample check.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the check: `.venv/bin/python scripts/check.py --first parsers`;
- the given test file above, 7 tests; at least N + 7 passed in all;
- `git diff --stat HEAD -- tests` prints nothing (the new files are untracked);
- the coverage command: `.venv/bin/python -m coverage report --include="*/finances/ingest/parsers/marcus.py" --fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 46: Marcus CD statements (YYYY-MM-DD)`.
