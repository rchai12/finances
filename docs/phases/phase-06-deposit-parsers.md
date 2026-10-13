# Phase 6: the Truist and Marcus deposit account parsers

## Goal

Add the last two statement parsers. `TruistDepositParser` reads a Truist checking or savings statement, and `MarcusSavingsParser` reads a Marcus by Goldman Sachs online savings statement. With them, every kind of statement the owner receives can be imported.

Deposit accounts differ from cards in two ways. A balance is money the holder has, so it is positive as printed. And the sign of a line is not printed with it: on a Truist statement the section decides it, and on a Marcus statement the running balance does.

A parser is only trusted because reconciliation checks it. Every rule below exists so that the lines add up to the printed closing balance, to the cent.

## Read first

- `AGENTS.md`: "Running commands", "Privacy rules" (rule 6 in particular), "Money and signs"
- `docs/statement-formats.md`: the notes at the top, and sections 4 and 5. Where that document and this spec differ, this spec is right.
- `src/finances/ingest/parsers/boa.py`, `citi.py`, and their tests: the pattern these parsers follow
- `src/finances/ingest/statement.py`, `src/finances/ingest/parsers/__init__.py`, `src/finances/ingest/parsers/helpers.py`, `src/finances/ingest/reconcile.py`
- `tests/fixtures/statements/truist/` and `tests/fixtures/statements/marcus/`: six text files, already in the repository
- `tests/conftest.py`

## Starting state

- Phase 5 is committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `882` when Phases 3e and 5 are the last phases built.
- Three parsers are registered: `capital_one_card`, `boa_card`, `citi_card`.
- `tests/fixtures/statements/truist/` holds `checking.txt`, `savings_no_activity.txt`, and `year_end.txt`. `tests/fixtures/statements/marcus/` holds `basic.txt`, `interest_only.txt`, and `amount_mismatch.txt`. They are synthetic. A form feed character separates the pages of a file.
- `Section` already has `DEPOSITS`, `WITHDRAWALS`, and `CHECKS`. `AccountType` already has `CHECKING` and `SAVINGS`.
- `parse_month_day` reads `MM/DD` and `MM-DD`, and accepts a date up to 60 days before the period starts.
- The tests no longer depend on `FORCE_COLOR`: `tests/conftest.py` removes it for every test. Run the commands as written, without changing the environment.
- `finances.ingest` is at 100% line and branch coverage.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/ingest/parsers/truist.py` | new: `TruistDepositParser` |
| `src/finances/ingest/parsers/marcus.py` | new: `MarcusSavingsParser` |
| `src/finances/ingest/parsers/__init__.py` | five lines added at the end (given below) |
| `tests/unit/test_truist_parser.py`, `tests/unit/test_marcus_parser.py`, `tests/integration/test_truist_marcus_import.py` | given, do not change |
| `tests/unit/test_truist_parser_more.py`, `tests/unit/test_marcus_parser_more.py` | new, written by you |
| `docs/progress.md` | one new entry |

You may add private helpers (names starting with `_`) inside `truist.py` and `marcus.py`. `TruistDepositParser` and `MarcusSavingsParser` are the only public names of their modules. Do not create any other production module, and do not change any other production file, any fixture, `tests/conftest.py`, `tests/real_samples/check_real_samples.py`, or any existing test.

## Out of scope

- Finding transfers between accounts. These statements are full of them; Phase 11 matches them.
- Merchant clean-up. Descriptions stay as printed, apart from collapsed whitespace. A Marcus description printed without spaces (`ACHDepositInternettransferfrom...`) stays without spaces.
- Changes to `helpers.py`, to the three card parsers, to the import service, reconciliation, fingerprints, or PDF text extraction. If you believe one of them has a bug, stop and report it; do not work around it in a parser.
- A base class or a "generic" parser.
- Reading interest summaries, annual percentage yields, or year-to-date figures.
- Reading anything under `data/`, and running `fin import` on anything under `data/`. Only `check_real_samples.py` reads real statements.
- New dependencies.

## Dependencies

None new.

## Design

```python
# truist.py
class TruistDepositParser:
    name = "truist_deposit"

    def detect(self, first_page: str) -> bool: ...
    def parse(self, pages: list[str]) -> ParsedStatement: ...


# marcus.py
class MarcusSavingsParser:
    name = "marcus_savings"

    def detect(self, first_page: str) -> bool: ...
    def parse(self, pages: list[str]) -> ParsedStatement: ...
```

The parsers hold no state between calls. `parse` works on the lines of all pages, in order, each with its outer whitespace removed. Where the pages are split makes no difference to the result.

Add exactly these lines at the end of `src/finances/ingest/parsers/__init__.py`, after the existing lines and one blank line:

```python
from finances.ingest.parsers.marcus import MarcusSavingsParser  # noqa: E402
from finances.ingest.parsers.truist import TruistDepositParser  # noqa: E402

register(TruistDepositParser())
register(MarcusSavingsParser())
```

In this spec an **amount** is digits (plain, or grouped in threes with commas), a point, and exactly two digits. **Money** is an amount with `$` directly before it. A **short date** is two digits, `/`, two digits. A **full date** is a short date followed by `/` and four digits.

### The Truist layout

This is `tests/fixtures/statements/truist/checking.txt`. Columns are separated by runs of spaces whose length varies; never rely on an exact number of spaces. The first line is how part of the page header comes out of the PDF; it is noise.

```
T r u   i s   t .c   o   m
Truist Bank, Member FDIC                              Your account statement
For 09/11/2026
TRUIST ONE CHECKING - LEVEL 1 1000000001111

Account summary
Your previous balance as of 08/12/2026                    $2,552.23
Checks                                                  - 475.50
Other withdrawals, debits and service charges           - 13,434.39
Deposits, credits and interest                          + 13,405.75
Your new balance as of 09/11/2026                         = $2,048.09

Checks
DATE     CHECK #     AMOUNT($)   DATE     CHECK #     AMOUNT($)
08/20     1041     125.00      08/27     1042     40.00
09/03    *1045     310.50
* indicates a skip in sequential check numbers above this item
Total checks                                            = $475.50

Other withdrawals, debits and service charges
DATE    DESCRIPTION                                                        AMOUNT($)
08/17   DEBIT CARD PURCHASE ACME*TERMINAL3 08-15 DALLAS TX 2979               200.00
08/17   INTERNET PAYMENT TRANSFER EXAMPLE SAVINGS BA 000300000001111          11,000.00
08/20   DEBIT CARD RECURRING PYMT STREAMCO.COM 08-19 866-555-0100 CA 2979     9.99
continued
PAGE 1 OF 2
----- page break -----
T r u   i s   t .c   o   m
Truist Bank, Member FDIC                              Your account statement
For 09/11/2026
TRUIST ONE CHECKING - LEVEL 1 1000000001111

Other withdrawals, debits and service charges (continued)
DATE    DESCRIPTION                                                        AMOUNT($)
09/01   ACH CORP DEBIT PAYMENT EXAMPLE CARD CUSTOMER ID 4400000000009999      2,150.00
09/04   DEBIT CARD PURCHASE FOOBAR GROCERY 24-7 09-03 PLANO TX 3141           62.40
09/10   MAINTENANCE FEE                                                       12.00
Total other withdrawals, debits and service charges     = $13,434.39

Deposits, credits and interest
DATE    DESCRIPTION                                                        AMOUNT($)
08/14   INCOMING WIRE TRANSFER WIRE REF# 20260814-00000000                    13,000.00
08/28   ACH CORP CREDIT PAYROLL EXAMPLE EMPLOYER INC                          390.00
09/08   DEBIT CARD PURCHASE RETURN ACME OUTLET 09-06 DALLAS TX 2979           15.75
Total deposits, credits and interest                    = $13,405.75

Important: questions about your statement
10/01   Call the number on your card by this date          1.00
```

A statement with no activity (`savings_no_activity.txt`) has the summary and no sections.

### The Marcus layout

This is `tests/fixtures/statements/marcus/basic.txt`. The PDF text often has no spaces inside a description, and sometimes none inside `EndingBalance`.

```
Marcus by Goldman Sachs                    ONLINE SAVINGS ACCOUNT STATEMENT
Goldman Sachs Bank USA, Member FDIC
Statement Period      09/01/2026 to 09/30/2026
Account Number      300100001111

ACCOUNT ACTIVITY
Date          Description                                        Credits      Debits      Balance
09/01/2026   Beginning Balance                                                  $14,646.12
09/01/2026   ACHDepositInternettransferfromEXAMPLE BANKDDAaccount    $3,000.00              $17,646.12
                ****************1111
09/17/2026   ACHWithdrawalInternettransfertoEXAMPLE BANK,N.A.                    $5,000.00  $12,646.12
                ****************1111
Page 1 of 2
----- page break -----
Marcus by Goldman Sachs                    ONLINE SAVINGS ACCOUNT STATEMENT
Goldman Sachs Bank USA, Member FDIC
Statement Period      09/01/2026 to 09/30/2026
Account Number      300100001111

ACCOUNT ACTIVITY (continued)
Date          Description                                        Credits      Debits      Balance
09/22/2026   ACHWithdrawalInternettransfertoEXAMPLE BANK,N.A.                    $250.50  $12,395.62
09/30/2026   InterestPaid                                            $40.13              $12,435.75
09/30/2026   EndingBalance                                                     $12,435.75

INTEREST SUMMARY
Annual Percentage Yield Earned      4.25%
Interest Paid Year to Date      $123.45      $1,000.00
```

## Requirements

### Part 1: Truist

- **R1.** `detect` returns `True` when the first page contains both `Truist` and `Your account statement`, with those exact characters. Otherwise `False`.
- **R2.** The **account line** is the first line that, taken whole, contains the word `CHECKING` or the word `SAVINGS` in capitals and ends with whitespace followed by a number of at least four digits. `account_type` is `AccountType.CHECKING` or `AccountType.SAVINGS`, from whichever of the two words comes first on that line. `account_last4` is the last four digits of the number. A transaction row is never an account line, because a row ends in an amount.
- **R3.** `parser_name` is `"truist_deposit"` and `institution` is `"Truist"`.
- **R4.** The opening balance is on the first line that has `Your previous balance as of `, a full date that exists, and, for the label made of those words and that date, an amount that `find_labeled_amount` finds. `opening_balance_cents` is that amount as `find_labeled_amount` returns it: `$2,552.23` is `255223`, and an overdrawn `-$12.50` is `-1250`. The closing balance is found the same way with `Your new balance as of `, where the amount is printed as `= $1,518.59`.
- **R5.** `period_end` is the date of the new balance. `period_start` is the day after the date of the previous balance. Savings statements can cover three months.
- **R6.** `declared_section_totals` has an entry for each of these labels that `find_labeled_amount` finds, and no entry for one it does not find:

  | Label | Section | Value |
  |---|---|---|
  | `Total checks` | `CHECKS` | the negative of the amount |
  | `Total other withdrawals, debits and service charges` | `WITHDRAWALS` | the negative of the amount |
  | `Total deposits, credits and interest` | `DEPOSITS` | the amount |

  The summary lines (`Checks      - 475.50`) are not used: they have no `$`.
- **R7.** A line that is exactly `Checks`, `Other withdrawals, debits and service charges`, or `Deposits, credits and interest`, with nothing else on it, opens that section (`CHECKS`, `WITHDRAWALS`, `DEPOSITS`). A line that starts with `Total ` closes the open section. The open section stays open across page breaks and across every other line.
- **R8.** In `WITHDRAWALS` and `DEPOSITS`, a **row** is the whole of a line of this shape: a short date, whitespace, the description, whitespace, and an amount with no sign and no `$`. It becomes a `StatementLine` with:

  | Field | Value |
  |---|---|
  | `posted_date` | the short date, through `parse_month_day` with the statement period |
  | `description` | the description, through `collapse_ws` |
  | `amount_cents` | the amount, negative in `WITHDRAWALS` and positive in `DEPOSITS` |
  | `section` | the open section |
  | `transaction_date`, `card_last4` | see R9 |
  | `cardholder`, `external_ref` | `None` |

  A row whose amount is zero is left out.
- **R9.** Debit card rows carry two more facts inside the description. Only for a description that starts with `DEBIT CARD ` (after `collapse_ws`):
  - `card_last4` is the last word of the description when that word is exactly four digits. Otherwise `None`.
  - `transaction_date` comes from the last word of the form two digits, `-`, two digits (`08-15`): it is that month and day through `parse_month_day` with the statement period. When there is no such word, or `parse_month_day` raises for it, `transaction_date` is `None` and the row is kept.

  For every other row both are `None`. The description is not shortened: the date and the card digits stay in it.
- **R10.** In `CHECKS`, a line can hold several checks side by side. Every occurrence in the line of a short date, whitespace, an optional `*` with optional whitespace after it, a check number (digits), whitespace, and an amount is one row. It becomes a `StatementLine` with `posted_date` from the date, `description` `CHECK ` followed by the number, `amount_cents` the negative of the amount, `section` `CHECKS`, `external_ref` the number, and `None` for the rest. A check whose amount is zero is left out.
- **R11.** Every other line is ignored: the noise line, column headings, the summary, the line that explains the `*`, and anything outside a section (the fixture has a line shaped like a row after the last `Total` line).
- **R12.** A missing piece raises `StatementError` with one of these messages, checked in this order:

  | Missing | Message |
  |---|---|
  | the account line of R2 | `truist: account line not found` |
  | the opening balance of R4 | `truist: previous balance not found` |
  | the closing balance of R4 | `truist: new balance not found` |

### Part 2: Marcus

- **R13.** `detect` returns `True` when the first page contains both `Goldman Sachs Bank USA` and `ONLINE SAVINGS ACCOUNT STATEMENT`, with those exact characters. Otherwise `False`.
- **R14.** `account_last4` is the last four digits of the first number of at least four digits that follows `Account Number` and whitespace.
- **R15.** The period is the first `Statement Period`, whitespace, a full date, ` to ` (with any whitespace around `to`), and a full date. `period_start` and `period_end` are those dates.
- **R16.** `parser_name` is `"marcus_savings"`, `institution` is `"Marcus by Goldman Sachs"`, and `account_type` is `AccountType.SAVINGS`.
- **R17.** A **balance line** is the whole of a line of this shape: a full date, whitespace, a label, whitespace, and money, optionally with `-` before the `$`. `opening_balance_cents` is the money of the first balance line whose label, with all whitespace removed, is `BeginningBalance`. `closing_balance_cents` is the same for `EndingBalance`. Neither becomes a `StatementLine`.
- **R18.** A **row** is the whole of a line of this shape: a full date, whitespace, the description, whitespace, money (the printed amount), whitespace, and money optionally with `-` before the `$` (the balance after the row). Rows are numbered from 1 in the order they are printed.
- **R19.** The amount of a row is its balance minus the balance before it. The balance before the first row is the opening balance. The size of that difference must equal the printed amount; when it does not, `parse` raises `StatementError` with `marcus: row N does not match its balance`, where N is the row's number. The column the printed amount stands in is not used.
- **R20.** A row becomes a `StatementLine` with:

  | Field | Value |
  |---|---|
  | `posted_date` | the row's date |
  | `description` | the description, through `collapse_ws` |
  | `amount_cents` | the difference of R19: positive for money in, negative for money out |
  | `section` | `INTEREST` when the description, with all whitespace removed, is `InterestPaid`; otherwise `DEPOSITS` for a positive amount and `WITHDRAWALS` for a negative one |
  | everything else | `None` |

  A row that leaves the balance unchanged (printed amount `$0.00`) is left out. It still has a number.
- **R21.** `declared_section_totals` is empty. Every other line is ignored, among them the lines of masked digits under a row and the interest summary.
- **R22.** A missing piece raises `StatementError` with one of these messages, checked in this order, before any row is read:

  | Missing | Message |
  |---|---|
  | the account number of R14 | `marcus: account number not found` |
  | the period of R15, or a period with a date that does not exist | `marcus: statement period not found` |
  | the opening balance | `marcus: beginning balance not found` |
  | the closing balance | `marcus: ending balance not found` |

  A row whose date does not exist raises `marcus: row N has an impossible date`.

### Part 3: both parsers

- **R23.** `lines` holds the rows in the order they are printed.
- **R24.** A Truist row or check whose posted date falls outside the statement period makes `parse_month_day` raise `StatementError`. Let it pass through unchanged.
- **R25.** `parse` raises nothing but `StatementError`, for any list of strings, including an empty list. No message contains text from the statement; a row number is not text from the statement.
- **R26.** Importing `finances.ingest.parsers` registers one `TruistDepositParser` and one `MarcusSavingsParser`, through the five lines under Design. Neither detects the other's statements, nor a card statement.

## Given tests

Create these three files exactly as shown and do not change them. If one of their tests fails, the production code is wrong.

`tests/unit/test_truist_parser.py` checks the parser against its fixtures, every field of every line, and then one rule at a time.

```python
from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers import detect_parser, registered_parsers
from finances.ingest.parsers.truist import TruistDepositParser
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

FIXTURES = Path(__file__).parent.parent / "fixtures" / "statements"
STATEMENTS = ["checking", "savings_no_activity", "year_end"]
OTHER_BANKS = [
    ("capital_one", "single_card"),
    ("capital_one", "multi_card"),
    ("capital_one", "other_bank"),
    ("boa", "two_pages"),
    ("boa", "year_end"),
    ("citi", "two_cardholders"),
    ("citi", "year_end"),
    ("marcus", "basic"),
    ("marcus", "interest_only"),
]


def pages(name: str, bank: str = "truist") -> list[str]:
    return (FIXTURES / bank / f"{name}.txt").read_text(encoding="utf-8").split("\f")


def parse(name: str) -> ParsedStatement:
    return TruistDepositParser().parse(pages(name))


def test_the_parser_is_registered_once_under_its_name() -> None:
    names = [parser.name for parser in registered_parsers()]
    assert names.count("truist_deposit") == 1
    assert TruistDepositParser.name == "truist_deposit"


@pytest.mark.parametrize("name", STATEMENTS)
def test_detects_its_own_fixtures(name: str) -> None:
    assert TruistDepositParser().detect(pages(name)[0]) is True
    assert detect_parser(pages(name)).name == "truist_deposit"


@pytest.mark.parametrize(("bank", "name"), OTHER_BANKS)
def test_does_not_detect_another_banks_statement(bank: str, name: str) -> None:
    assert TruistDepositParser().detect(pages(name, bank)[0]) is False


@pytest.mark.parametrize("name", STATEMENTS)
def test_every_fixture_reconciles(name: str) -> None:
    result = reconcile(parse(name))
    assert result.ok is True
    assert result.difference_cents == 0
    assert result.section_mismatches == {}


@pytest.mark.parametrize("name", STATEMENTS)
def test_parsing_twice_gives_the_same_statement(name: str) -> None:
    assert parse(name) == parse(name)


@pytest.mark.parametrize("name", STATEMENTS)
def test_the_page_breaks_do_not_matter(name: str) -> None:
    joined = ["\n".join(pages(name))]
    assert TruistDepositParser().parse(joined) == parse(name)


def test_checking_header_balances_and_totals() -> None:
    statement = parse("checking")
    assert statement.parser_name == "truist_deposit"
    assert statement.institution == "Truist"
    assert statement.account_type is AccountType.CHECKING
    assert statement.account_last4 == "1111"
    assert statement.period_start == date(2026, 8, 13)
    assert statement.period_end == date(2026, 9, 11)
    assert statement.opening_balance_cents == 255223
    assert statement.closing_balance_cents == 204809
    assert statement.declared_section_totals == {
        Section.CHECKS: -47550,
        Section.WITHDRAWALS: -1343439,
        Section.DEPOSITS: 1340575,
    }
    assert len(statement.lines) == 12


def test_checking_lines() -> None:
    assert parse("checking").lines == [
        StatementLine(
            date(2026, 8, 20), None, "CHECK 1041", -12500, Section.CHECKS, external_ref="1041"
        ),
        StatementLine(
            date(2026, 8, 27), None, "CHECK 1042", -4000, Section.CHECKS, external_ref="1042"
        ),
        StatementLine(
            date(2026, 9, 3), None, "CHECK 1045", -31050, Section.CHECKS, external_ref="1045"
        ),
        StatementLine(
            date(2026, 8, 17),
            date(2026, 8, 15),
            "DEBIT CARD PURCHASE ACME*TERMINAL3 08-15 DALLAS TX 2979",
            -20000,
            Section.WITHDRAWALS,
            card_last4="2979",
        ),
        StatementLine(
            date(2026, 8, 17),
            None,
            "INTERNET PAYMENT TRANSFER EXAMPLE SAVINGS BA 000300000001111",
            -1100000,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2026, 8, 20),
            date(2026, 8, 19),
            "DEBIT CARD RECURRING PYMT STREAMCO.COM 08-19 866-555-0100 CA 2979",
            -999,
            Section.WITHDRAWALS,
            card_last4="2979",
        ),
        StatementLine(
            date(2026, 9, 1),
            None,
            "ACH CORP DEBIT PAYMENT EXAMPLE CARD CUSTOMER ID 4400000000009999",
            -215000,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2026, 9, 4),
            date(2026, 9, 3),
            "DEBIT CARD PURCHASE FOOBAR GROCERY 24-7 09-03 PLANO TX 3141",
            -6240,
            Section.WITHDRAWALS,
            card_last4="3141",
        ),
        StatementLine(date(2026, 9, 10), None, "MAINTENANCE FEE", -1200, Section.WITHDRAWALS),
        StatementLine(
            date(2026, 8, 14),
            None,
            "INCOMING WIRE TRANSFER WIRE REF# 20260814-00000000",
            1300000,
            Section.DEPOSITS,
        ),
        StatementLine(
            date(2026, 8, 28),
            None,
            "ACH CORP CREDIT PAYROLL EXAMPLE EMPLOYER INC",
            39000,
            Section.DEPOSITS,
        ),
        StatementLine(
            date(2026, 9, 8),
            date(2026, 9, 6),
            "DEBIT CARD PURCHASE RETURN ACME OUTLET 09-06 DALLAS TX 2979",
            1575,
            Section.DEPOSITS,
            card_last4="2979",
        ),
    ]


def test_savings_no_activity_header_balances_and_totals() -> None:
    statement = parse("savings_no_activity")
    assert statement.parser_name == "truist_deposit"
    assert statement.institution == "Truist"
    assert statement.account_type is AccountType.SAVINGS
    assert statement.account_last4 == "2222"
    assert statement.period_start == date(2026, 7, 1)
    assert statement.period_end == date(2026, 9, 30)
    assert statement.opening_balance_cents == 1250000
    assert statement.closing_balance_cents == 1250000
    assert statement.declared_section_totals == {}
    assert len(statement.lines) == 0


def test_savings_no_activity_has_no_lines() -> None:
    assert parse("savings_no_activity").lines == []


def test_year_end_header_balances_and_totals() -> None:
    statement = parse("year_end")
    assert statement.parser_name == "truist_deposit"
    assert statement.institution == "Truist"
    assert statement.account_type is AccountType.SAVINGS
    assert statement.account_last4 == "3333"
    assert statement.period_start == date(2026, 12, 12)
    assert statement.period_end == date(2027, 1, 12)
    assert statement.opening_balance_cents == 50000
    assert statement.closing_balance_cents == 62505
    assert statement.declared_section_totals == {
        Section.WITHDRAWALS: -12599,
        Section.DEPOSITS: 25104,
    }
    assert len(statement.lines) == 4


def test_year_end_lines() -> None:
    assert parse("year_end").lines == [
        StatementLine(
            date(2026, 12, 15),
            None,
            "INTERNET PAYMENT TRANSFER TO EXAMPLE CHECKING 1000000001111",
            -10000,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2027, 1, 4),
            date(2026, 12, 30),
            "DEBIT CARD PURCHASE ACME TOYS 12-30 AUSTIN TX 2979",
            -2599,
            Section.WITHDRAWALS,
            card_last4="2979",
        ),
        StatementLine(date(2026, 12, 31), None, "INTEREST PAYMENT", 104, Section.DEPOSITS),
        StatementLine(date(2027, 1, 8), None, "MOBILE DEPOSIT", 25000, Section.DEPOSITS),
    ]


@pytest.mark.parametrize(
    "first_page",
    [
        "",
        "Truist Bank, Member FDIC",
        "Your account statement",
        "TRUIST BANK\nYOUR ACCOUNT STATEMENT",
        "T r u i s t\nYour account statement",
    ],
)
def test_detect_needs_both_markers(first_page: str) -> None:
    assert TruistDepositParser().detect(first_page) is False


def test_detect_with_both_markers() -> None:
    assert TruistDepositParser().detect("Your account statement\nTruist.com") is True


def edited(name: str, old: str, new: str) -> ParsedStatement:
    text = "\f".join(pages(name))
    assert old in text
    return TruistDepositParser().parse(text.replace(old, new).split("\f"))


def test_spaces_inside_a_description_are_collapsed() -> None:
    statement = edited("checking", "MAINTENANCE FEE", "MAINTENANCE     FEE")
    assert statement == parse("checking")


def test_the_last_month_day_token_is_the_purchase_date() -> None:
    statement = edited("checking", "ACME*TERMINAL3 08-15 DALLAS", "ACME 07-04 SALE 08-16 DALLAS")
    line = statement.lines[3]
    assert line.description == "DEBIT CARD PURCHASE ACME 07-04 SALE 08-16 DALLAS TX 2979"
    assert line.transaction_date == date(2026, 8, 16)
    assert line.posted_date == date(2026, 8, 17)


def test_a_purchase_date_that_cannot_be_dated_is_left_out() -> None:
    statement = edited("checking", "ACME*TERMINAL3 08-15 DALLAS", "ACME*TERMINAL3 02-30 DALLAS")
    assert statement.lines[3].transaction_date is None
    assert statement.lines[3].card_last4 == "2979"
    statement = edited("checking", "ACME*TERMINAL3 08-15 DALLAS", "ACME*TERMINAL3 03-15 DALLAS")
    assert statement.lines[3].transaction_date is None


def test_only_debit_card_rows_get_a_card_and_a_purchase_date() -> None:
    statement = edited("checking", "MAINTENANCE FEE", "TRANSFER 09-09 REF 2979")
    line = statement.lines[8]
    assert line.description == "TRANSFER 09-09 REF 2979"
    assert (line.transaction_date, line.card_last4) == (None, None)


def test_a_debit_card_row_that_does_not_end_in_four_digits_has_no_card() -> None:
    statement = edited(
        "checking", "DALLAS TX 2979               200.00", "DALLAS TX 29790              200.00"
    )
    assert statement.lines[3].card_last4 is None
    assert statement.lines[3].transaction_date == date(2026, 8, 15)


def test_a_row_with_a_zero_amount_is_left_out() -> None:
    statement = edited(
        "checking",
        "MAINTENANCE FEE                                                       12.00",
        "MAINTENANCE FEE     0.00",
    )
    assert [item.description for item in statement.lines if "FEE" in item.description] == []
    assert len(statement.lines) == 11


def test_an_overdrawn_balance_is_negative() -> None:
    statement = edited("savings_no_activity", "$12,500.00", "-$12.50")
    assert (statement.opening_balance_cents, statement.closing_balance_cents) == (-1250, -1250)


def test_the_account_type_comes_from_the_account_line() -> None:
    old = "TRUIST ONE SAVINGS 4110000002222"
    statement = edited("savings_no_activity", old, "TRUIST DIMENSION CHECKING - LEVEL 2   90210")
    assert (statement.account_type, statement.account_last4) == (AccountType.CHECKING, "0210")
    statement = edited(
        "savings_no_activity", old, "TRUIST SAVINGS FOR CHECKING CLIENTS 4110000002222"
    )
    assert statement.account_type is AccountType.SAVINGS


@pytest.mark.parametrize(
    "line",
    [
        "TRUIST ONE SAVINGS 411",
        "TRUIST ONE SAVINGS",
        "TRUIST ONE Savings 4110000002222",
        "TRUIST ONE MONEY MARKET 4110000002222",
        "TRUIST ONE SAVINGS4110000002222",
        "TRUIST ONE SAVINGS 4110000002222 (continued)",
    ],
)
def test_lines_that_are_not_an_account_line(line: str) -> None:
    with pytest.raises(StatementError) as caught:
        edited("savings_no_activity", "TRUIST ONE SAVINGS 4110000002222", line)
    assert str(caught.value) == "truist: account line not found"


def test_a_check_with_a_zero_amount_is_left_out() -> None:
    statement = edited("checking", "08/27     1042     40.00", "08/27     1042     0.00")
    assert [item.external_ref for item in statement.lines[:2]] == ["1041", "1045"]
    assert len(statement.lines) == 11


def test_three_checks_on_one_line() -> None:
    old = "08/20     1041     125.00      08/27     1042     40.00"
    new = "08/20  1041  125.00  08/27 *1042 40.00  08/31 * 77 1,000.01"
    statement = edited("checking", old, new)
    found = [
        (item.posted_date, item.external_ref, item.amount_cents) for item in statement.lines[:4]
    ]
    assert found == [
        (date(2026, 8, 20), "1041", -12500),
        (date(2026, 8, 27), "1042", -4000),
        (date(2026, 8, 31), "77", -100001),
        (date(2026, 9, 3), "1045", -31050),
    ]
    assert statement.lines[2].description == "CHECK 77"
```

`tests/unit/test_marcus_parser.py` does the same for Marcus.

```python
from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers import detect_parser, registered_parsers
from finances.ingest.parsers.marcus import MarcusSavingsParser
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

FIXTURES = Path(__file__).parent.parent / "fixtures" / "statements"
STATEMENTS = ["basic", "interest_only"]
OTHER_BANKS = [
    ("capital_one", "single_card"),
    ("capital_one", "multi_card"),
    ("capital_one", "other_bank"),
    ("boa", "two_pages"),
    ("boa", "year_end"),
    ("citi", "two_cardholders"),
    ("citi", "year_end"),
    ("truist", "checking"),
    ("truist", "savings_no_activity"),
]


def pages(name: str, bank: str = "marcus") -> list[str]:
    return (FIXTURES / bank / f"{name}.txt").read_text(encoding="utf-8").split("\f")


def parse(name: str) -> ParsedStatement:
    return MarcusSavingsParser().parse(pages(name))


def test_the_parser_is_registered_once_under_its_name() -> None:
    names = [parser.name for parser in registered_parsers()]
    assert names.count("marcus_savings") == 1
    assert MarcusSavingsParser.name == "marcus_savings"


@pytest.mark.parametrize("name", STATEMENTS)
def test_detects_its_own_fixtures(name: str) -> None:
    assert MarcusSavingsParser().detect(pages(name)[0]) is True
    assert detect_parser(pages(name)).name == "marcus_savings"


@pytest.mark.parametrize(("bank", "name"), OTHER_BANKS)
def test_does_not_detect_another_banks_statement(bank: str, name: str) -> None:
    assert MarcusSavingsParser().detect(pages(name, bank)[0]) is False


@pytest.mark.parametrize("name", STATEMENTS)
def test_every_fixture_reconciles(name: str) -> None:
    result = reconcile(parse(name))
    assert result.ok is True
    assert result.difference_cents == 0
    assert result.section_mismatches == {}


@pytest.mark.parametrize("name", STATEMENTS)
def test_parsing_twice_gives_the_same_statement(name: str) -> None:
    assert parse(name) == parse(name)


@pytest.mark.parametrize("name", STATEMENTS)
def test_the_page_breaks_do_not_matter(name: str) -> None:
    joined = ["\n".join(pages(name))]
    assert MarcusSavingsParser().parse(joined) == parse(name)


def test_basic_header_balances_and_totals() -> None:
    statement = parse("basic")
    assert statement.parser_name == "marcus_savings"
    assert statement.institution == "Marcus by Goldman Sachs"
    assert statement.account_type is AccountType.SAVINGS
    assert statement.account_last4 == "1111"
    assert statement.period_start == date(2026, 9, 1)
    assert statement.period_end == date(2026, 9, 30)
    assert statement.opening_balance_cents == 1464612
    assert statement.closing_balance_cents == 1243575
    assert statement.declared_section_totals == {}
    assert len(statement.lines) == 4


def test_basic_lines() -> None:
    assert parse("basic").lines == [
        StatementLine(
            date(2026, 9, 1),
            None,
            "ACHDepositInternettransferfromEXAMPLE BANKDDAaccount",
            300000,
            Section.DEPOSITS,
        ),
        StatementLine(
            date(2026, 9, 17),
            None,
            "ACHWithdrawalInternettransfertoEXAMPLE BANK,N.A.",
            -500000,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2026, 9, 22),
            None,
            "ACHWithdrawalInternettransfertoEXAMPLE BANK,N.A.",
            -25050,
            Section.WITHDRAWALS,
        ),
        StatementLine(date(2026, 9, 30), None, "InterestPaid", 4013, Section.INTEREST),
    ]


def test_interest_only_header_balances_and_totals() -> None:
    statement = parse("interest_only")
    assert statement.parser_name == "marcus_savings"
    assert statement.institution == "Marcus by Goldman Sachs"
    assert statement.account_type is AccountType.SAVINGS
    assert statement.account_last4 == "4444"
    assert statement.period_start == date(2026, 12, 1)
    assert statement.period_end == date(2026, 12, 31)
    assert statement.opening_balance_cents == 100000
    assert statement.closing_balance_cents == 100354
    assert statement.declared_section_totals == {}
    assert len(statement.lines) == 1


def test_interest_only_lines() -> None:
    assert parse("interest_only").lines == [
        StatementLine(date(2026, 12, 31), None, "Interest Paid", 354, Section.INTEREST),
    ]


def test_amount_mismatch_is_refused() -> None:
    assert MarcusSavingsParser().detect(pages("amount_mismatch")[0]) is True
    with pytest.raises(StatementError) as caught:
        parse("amount_mismatch")
    assert str(caught.value) == "marcus: row 2 does not match its balance"


@pytest.mark.parametrize(
    "first_page",
    [
        "",
        "Goldman Sachs Bank USA",
        "ONLINE SAVINGS ACCOUNT STATEMENT",
        "Marcus by Goldman Sachs\nONLINE SAVINGS ACCOUNT STATEMENT",
        "GOLDMAN SACHS BANK USA\nOnline Savings Account Statement",
    ],
)
def test_detect_needs_both_markers(first_page: str) -> None:
    assert MarcusSavingsParser().detect(first_page) is False


def test_detect_with_both_markers() -> None:
    page = "ONLINE SAVINGS ACCOUNT STATEMENT\nGoldman Sachs Bank USA, Member FDIC"
    assert MarcusSavingsParser().detect(page) is True


def edited(name: str, old: str, new: str) -> ParsedStatement:
    text = "\f".join(pages(name))
    assert old in text
    return MarcusSavingsParser().parse(text.replace(old, new).split("\f"))


def test_spaces_inside_a_description_are_collapsed() -> None:
    statement = edited("basic", "EXAMPLE BANKDDAaccount", "EXAMPLE    BANKDDAaccount")
    assert statement == parse("basic")


def test_the_sign_comes_from_the_balance_not_the_column() -> None:
    moved = "$250.50" + " " * 30 + "$12,395.62"
    assert edited("basic", "$250.50  $12,395.62", moved) == parse("basic")


@pytest.mark.parametrize("label", ["Beginning Balance", "BeginningBalance", "Beginning  Balance"])
def test_the_beginning_balance_label_with_or_without_spaces(label: str) -> None:
    assert edited("basic", "Beginning Balance", label) == parse("basic")


@pytest.mark.parametrize("label", ["Ending Balance", "EndingBalance"])
def test_the_ending_balance_label_with_or_without_spaces(label: str) -> None:
    assert edited("basic", "EndingBalance", label) == parse("basic")


@pytest.mark.parametrize("text", ["InterestPaid", "Interest Paid"])
def test_interest_has_its_own_section(text: str) -> None:
    line = edited("basic", "InterestPaid", text).lines[3]
    assert (line.description, line.section, line.amount_cents) == (text, Section.INTEREST, 4013)


def test_a_withdrawal_called_interest_something_else_is_a_withdrawal() -> None:
    line = edited(
        "basic",
        "InterestPaid                                            $40.13              $12,435.75",
        "InterestPaidBack   $40.13   $12,355.49",
    ).lines[3]
    assert (line.section, line.amount_cents) == (Section.WITHDRAWALS, -4013)


def test_a_row_that_leaves_the_balance_unchanged_is_left_out() -> None:
    statement = edited(
        "basic",
        "InterestPaid                                            $40.13              $12,435.75",
        "InterestPaid   $0.00   $12,395.62",
    )
    assert len(statement.lines) == 3
    assert statement.closing_balance_cents == 1243575
```

`tests/integration/test_truist_marcus_import.py` builds real PDFs and imports them through the registry and the import service.

```python
from datetime import date

from sqlalchemy import Engine

from finances.db.engine import session_scope
from finances.db.repositories import create_account, latest_balance, list_transactions
from finances.ingest.service import ImportStatus, StatementImportResult, import_statement

TRUIST = [
    "Truist Bank, Member FDIC   Your account statement",
    "For 05/31/2026",
    "TRUIST ONE CHECKING - LEVEL 1 1000000007777",
    "Your previous balance as of 04/30/2026   $500.00",
    "Checks   - 75.00",
    "Other withdrawals, debits and service charges   - 31.75",
    "Deposits, credits and interest   + 250.00",
    "Your new balance as of 05/31/2026   = $643.25",
    "Checks",
    "05/06   2001   75.00",
    "Total checks   = $75.00",
    "Other withdrawals, debits and service charges",
    "05/04\tDEBIT CARD PURCHASE ACME GROCERY 05-02 DECATUR GA 4242   31.75",
    "Total other withdrawals, debits and service charges   = $31.75",
    "Deposits, credits and interest",
    "05/15\tACH CORP CREDIT PAYROLL EXAMPLE EMPLOYER   250.00",
    "Total deposits, credits and interest   = $250.00",
]
MARCUS = [
    "Marcus by Goldman Sachs   ONLINE SAVINGS ACCOUNT STATEMENT",
    "Goldman Sachs Bank USA, Member FDIC",
    "Statement Period   05/01/2026 to 05/31/2026",
    "Account Number   300100008888",
    "05/01/2026\tBeginning Balance   $1,000.00",
    "05/12/2026\tACHWithdrawalInternettransfertoEXAMPLE BANK   $200.00   $800.00",
    "05/31/2026\tInterestPaid   $2.75   $802.75",
    "05/31/2026\tEndingBalance   $802.75",
]


def stored(session) -> list[tuple]:
    rows = sorted(list_transactions(session), key=lambda item: item.id)
    return [
        (r.posted_date, r.transaction_date, r.amount_cents, r.description, r.section) for r in rows
    ]


def test_a_truist_pdf_is_imported(db_engine: Engine, make_pdf) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Checking", "Truist", "checking", last4="7777")
        result = import_statement(session, filename="truist-may.pdf", content=make_pdf([TRUIST]))
    assert result == StatementImportResult(
        filename="truist-may.pdf",
        status=ImportStatus.IMPORTED,
        message="imported",
        parser_name="truist_deposit",
        account_name="Test Checking",
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        lines_parsed=3,
        inserted=3,
        duplicates=0,
    )
    with session_scope(db_engine) as session:
        assert stored(session) == [
            (date(2026, 5, 6), None, -7500, "CHECK 2001", "checks"),
            (
                date(2026, 5, 4),
                date(2026, 5, 2),
                -3175,
                "DEBIT CARD PURCHASE ACME GROCERY 05-02 DECATUR GA 4242",
                "withdrawals",
            ),
            (
                date(2026, 5, 15),
                None,
                25000,
                "ACH CORP CREDIT PAYROLL EXAMPLE EMPLOYER",
                "deposits",
            ),
        ]
        rows = sorted(list_transactions(session), key=lambda item: item.id)
        assert [(r.card_last4, r.external_id) for r in rows] == [
            (None, "2001"),
            ("4242", None),
            (None, None),
        ]
        assert latest_balance(session, 1).balance_cents == 64325


def test_a_marcus_pdf_is_imported(db_engine: Engine, make_pdf) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Savings", "Marcus by Goldman Sachs", "savings", last4="8888")
        result = import_statement(session, filename="marcus-may.pdf", content=make_pdf([MARCUS]))
    assert result == StatementImportResult(
        filename="marcus-may.pdf",
        status=ImportStatus.IMPORTED,
        message="imported",
        parser_name="marcus_savings",
        account_name="Test Savings",
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        lines_parsed=2,
        inserted=2,
        duplicates=0,
    )
    with session_scope(db_engine) as session:
        assert stored(session) == [
            (
                date(2026, 5, 12),
                None,
                -20000,
                "ACHWithdrawalInternettransfertoEXAMPLE BANK",
                "withdrawals",
            ),
            (date(2026, 5, 31), None, 275, "InterestPaid", "interest"),
        ]
        assert latest_balance(session, 1).balance_cents == 80275


def test_a_marcus_statement_whose_amounts_disagree_is_not_imported(
    db_engine: Engine, make_pdf
) -> None:
    lines = [line.replace("$200.00   $800.00", "$201.00   $800.00") for line in MARCUS]
    with session_scope(db_engine) as session:
        create_account(session, "Test Savings", "Marcus by Goldman Sachs", "savings", last4="8888")
        result = import_statement(session, filename="bad.pdf", content=make_pdf([lines]))
        assert list_transactions(session) == []
    assert result.status is ImportStatus.FAILED
    assert result.message == "marcus: row 1 does not match its balance"


def test_five_banks_are_told_apart(db_engine: Engine, make_pdf) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Checking", "Truist", "checking", last4="7777")
        create_account(session, "Test Savings", "Marcus by Goldman Sachs", "savings", last4="8888")
        first = import_statement(session, filename="a.pdf", content=make_pdf([TRUIST]))
        second = import_statement(session, filename="b.pdf", content=make_pdf([MARCUS]))
    assert (first.parser_name, first.account_name) == ("truist_deposit", "Test Checking")
    assert (second.parser_name, second.account_name) == ("marcus_savings", "Test Savings")
```

## Tests to write

`tests/unit/test_truist_parser_more.py` and `tests/unit/test_marcus_parser_more.py`, with synthetic text only. Build statements as lists of lines in the test, or by editing the text of a fixture as the given tests do. The given tests cover the fixtures; yours cover what the fixtures do not.

Truist:

- each of the three messages, exactly, and which one is reported when two pieces are missing
- a balance line whose date does not exist (`08/32/2026`), and one whose amount has no `$`: both are passed over, so the message of R12 follows
- declared totals when a `Total` line is missing: that entry is left out and the others stay
- R24: a row dated outside the period, and a check dated outside the period, with the helper's message
- R25: an empty list of pages, and a page of unrelated text
- a row before any section heading, and a row after a `Total` line, both ignored
- a debit card row with no `MM-DD` word; a row in `DEPOSITS` that starts with `DEBIT CARD ` (a refund): positive, with its card and date
- a statement with only a `Checks` section

Marcus:

- each of the four messages of R22, exactly, and the order in which missing pieces are reported
- a period with a date that does not exist
- `marcus: row N has an impossible date` and `marcus: row N does not match its balance` for a row other than the first, with the right N when a zero row comes before it
- R25: an empty list of pages, and a page of unrelated text
- a balance that goes below zero and comes back (`-$5.00`)
- a line with a date and one money that is neither balance label: ignored
- two identical rows on the same day: both kept, with the right running balance

Every line and branch of `truist.py` and `marcus.py` must be reached by a test.

## Rules for this phase

- **Money is `int` cents.** Amounts are read with `parse_amount` and `find_labeled_amount` only. `float` does not appear in `truist.py` or `marcus.py`.
- **Signs are from the account holder's side** (`AGENTS.md`): withdrawals, checks, and fees negative; deposits and interest positive; a balance the holder has is positive.
- **Constant messages.** The nine messages in R12, R19, and R22 are the only ones these modules create. The row number is the only part that varies. Nothing from a statement goes into an exception, and nothing is logged or printed.
- **ASCII digits.** Patterns use `[0-9]`, not `\d`.
- **Synthetic data only** in tests: invented names, merchants, and numbers.
- **Real statements.** Do not open, print, copy, or quote anything under `data/samples/`. The only permitted use is running `check_real_samples.py`, whose output is limited to sample numbers, the parser name, counts, and differences in cents (`AGENTS.md` privacy rule 6).
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, at least N + 94 passed, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_truist_parser.py tests/unit/test_marcus_parser.py tests/integration/test_truist_marcus_import.py --no-cov` | exactly `94 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| the search below | no output |
| `git diff HEAD --stat -- src/finances/ingest/parsers/helpers.py src/finances/ingest/parsers/capital_one.py src/finances/ingest/parsers/boa.py src/finances/ingest/parsers/citi.py tests/fixtures tests/conftest.py` | no output |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -F -e "strptime" -e "float" -e "print(" -e "logging" -e "\d" -- src/finances/ingest/parsers/truist.py src/finances/ingest/parsers/marcus.py`

### Real statements

Then run the check on real statements, if this machine has them:

`.venv/bin/python -m pytest tests/real_samples/check_real_samples.py --no-cov -rA`

- If it reports `no PDF files in data/samples`, say so in your report. That is not a failure of this phase.
- If it runs, every sample should now pass, and none should show as `xfail`: a parser exists for every bank.
- If a Truist or Marcus sample fails, report the summary line the check printed (sample number, parser name, line count, difference in cents, sections that differ) and nothing else. Then find the cause using the synthetic layouts in this spec and in `docs/statement-formats.md`. Do not open the PDF or print its text to find out.
- Three parts of the Truist layout are the architect's best estimate and have not been confirmed on a real statement: the rows of the `Checks` section (R10), section headings standing alone on a line (R7), and each balance standing on the same line as its label (R4). If a sample fails and one of these is the likely cause, stop and report that: the architect will add a synthetic example of the real layout.
- If a sample shows as `xfail` with `unrecognized statement format`, report its number only. It is a statement of a kind no spec describes yet.
- If a card sample fails, report its summary line and change nothing. Those parsers belong to Phases 4 and 5.

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 6: the Truist and Marcus deposit account parsers (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N, the final passed count, and the outcome of the real-statement check as counts only (for example "5 passed" or "no samples on this machine"). Under "Deviations", list your design choices (private helpers, how each parse is divided) and anything you did that the spec did not ask for, or `None`. Under "Follow-ups", write that the Truist `Checks` rows, headings, and balance lines are unconfirmed until real statements pass.

In your final message, give the output line of each acceptance command, and for each of R1 to R26 the name of a test that covers it.
