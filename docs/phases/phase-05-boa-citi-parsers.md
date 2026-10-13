# Phase 5: the Bank of America and Citi credit card parsers

## Goal

Add two more bank parsers, built the way `CapitalOneCardParser` was in Phase 4. `BoaCardParser` reads a Bank of America credit card statement and `CitiCardParser` reads a Citi credit card statement (seen on the Costco Anywhere Visa, with several cardholders). Each returns a `ParsedStatement` with the account, the billing period, both balances, every transaction, and the totals the statement declares.

Both parsers find summary amounts by their labels, as the Capital One parser does. That rule now has three users, so this phase puts it in `helpers.py` as `find_labeled_amount`.

When this phase is done, `import_statement` imports statements from three banks with no further change, because each parser registers itself.

A parser is only trusted because reconciliation checks it. Every rule below exists so that the lines add up to the printed closing balance, to the cent.

## Read first

- `AGENTS.md`: "Running commands", "Privacy rules" (rule 6 in particular), "Money and signs"
- `docs/statement-formats.md`: the notes at the top, and sections 2 and 3. Where that document and this spec differ, this spec is right.
- `src/finances/ingest/parsers/capital_one.py` and `tests/unit/test_capital_one_parser_more.py`: the pattern these parsers follow
- `src/finances/ingest/statement.py`, `src/finances/ingest/parsers/__init__.py`, `src/finances/ingest/parsers/helpers.py`, `src/finances/ingest/reconcile.py`
- `tests/fixtures/statements/boa/` and `tests/fixtures/statements/citi/`: five text files, already in the repository
- `tests/conftest.py`

## Starting state

- Phase 4 is committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `703` when Phase 4 is the last phase built.
- One parser is registered: `registered_parsers()` returns a list with `capital_one_card`.
- `tests/fixtures/statements/boa/` holds `two_pages.txt`, `year_end.txt`, and `credit_balance.txt`. `tests/fixtures/statements/citi/` holds `two_cardholders.txt` and `year_end.txt`. They are synthetic. A form feed character separates the pages of a file.
- `helpers.py` has `MONTHS`, `collapse_ws`, `parse_amount`, `infer_year`, and `parse_month_day`. `parse_month_day` reads both `Mon D` and `MM/DD`.
- `finances.ingest` is at 100% line and branch coverage.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/ingest/parsers/helpers.py` | one function added: `find_labeled_amount` |
| `src/finances/ingest/parsers/boa.py` | new: `BoaCardParser` |
| `src/finances/ingest/parsers/citi.py` | new: `CitiCardParser` |
| `src/finances/ingest/parsers/__init__.py` | five lines added at the end (given below) |
| `tests/unit/test_find_labeled_amount.py`, `tests/unit/test_boa_parser.py`, `tests/unit/test_citi_parser.py`, `tests/integration/test_boa_citi_import.py` | given, do not change |
| `tests/unit/test_boa_parser_more.py`, `tests/unit/test_citi_parser_more.py` | new, written by you |
| `docs/progress.md` | one new entry |

You may add private helpers (names starting with `_`) inside `boa.py` and `citi.py`. `BoaCardParser` and `CitiCardParser` are the only public names of their modules. Do not create any other production module, and do not change any other production file, any fixture, `tests/real_samples/check_real_samples.py`, or any existing test.

## Out of scope

- **`capital_one.py` does not change.** It keeps its private `_find`. Moving it onto `find_labeled_amount` is a later clean-up, done only after real Capital One statements have passed.
- A base class or a "generic" parser shared by the banks. Two parsers that look alike are fine.
- Any other new function in `helpers.py`.
- Parsers for deposit accounts (Phase 6) and CSV files.
- Changes to the import service, reconciliation, fingerprints, or PDF text extraction. If you believe one of them has a bug, stop and report it; do not work around it in a parser.
- Merchant clean-up. Descriptions stay as printed, apart from collapsed whitespace.
- Reading rewards pages, year-to-date totals, credit limits, or cash advance summaries.
- Reading anything under `data/`. Only `check_real_samples.py` does that.
- New dependencies.

## Dependencies

None new.

## Design

```python
# helpers.py
def find_labeled_amount(lines: list[str], label: str) -> int | None:
    """Return the amount printed after label on the first line that has one, or None."""


# boa.py
class BoaCardParser:
    name = "boa_card"

    def detect(self, first_page: str) -> bool: ...
    def parse(self, pages: list[str]) -> ParsedStatement: ...


# citi.py
class CitiCardParser:
    name = "citi_card"

    def detect(self, first_page: str) -> bool: ...
    def parse(self, pages: list[str]) -> ParsedStatement: ...
```

The parsers hold no state between calls. `parse` works on the lines of all pages, in order, each with its outer whitespace removed. Where the pages are split makes no difference to the result.

Add exactly these lines at the end of `src/finances/ingest/parsers/__init__.py`, after the Capital One lines and one blank line:

```python
from finances.ingest.parsers.boa import BoaCardParser  # noqa: E402
from finances.ingest.parsers.citi import CitiCardParser  # noqa: E402

register(BoaCardParser())
register(CitiCardParser())
```

### The Bank of America layout

This is `tests/fixtures/statements/boa/two_pages.txt`. Columns are separated by runs of spaces whose length varies; never rely on an exact number of spaces.

```
Bank of America                                        www.bankofamerica.com
Customized Cash Rewards Visa Signature
Account# 4400 0000 0000 1111
March 29 - April 28, 2026

Account Summary
Previous Balance                          $1,559.05
Payments and Other Credits                -$945.24
Purchases and Adjustments                 $1,540.09
Fees Charged                              $29.00
Interest Charged                          $12.34
New Balance Total                         $2,195.24
Total Credit Line                         $20,000.00
Statement Closing Date                    04/28/2026

Transactions
Transaction   Posting                                      Reference   Account
Date          Date      Description                        Number      Number      Amount
Payments and Other Credits
04/03   04/06   EXAMPLESOFT*STORE REDMOND WA                3012   1111   -43.19
04/07   04/07   PAYMENT FROM CHK 9999 CONF#M00000000        4733   1111   -902.05
TOTAL PAYMENTS AND OTHER CREDITS FOR THIS PERIOD          -$945.24
Purchases and Adjustments
03/28   03/30   ACME GROCERY #123 DECATUR GA                7838   2222   36.49
04/01   04/02   FOOBAR CAFE ATLANTA GA                      1190   1111   12.75
continued on next page...
Page 1 of 2
----- page break -----
Bank of America                                        www.bankofamerica.com
Customized Cash Rewards Visa Signature
Account# 4400 0000 0000 1111
March 29 - April 28, 2026

Transactions (continued)
Transaction   Posting                                      Reference   Account
Date          Date      Description                        Number      Number      Amount
04/01   04/02   FOOBAR CAFE ATLANTA GA                      1191   1111   12.75
04/10   04/11   EXAMPLE AIRLINES 0061234567890 TX           5521   2222   412.60
04/20   04/21   ACME HARDWARE #88 2026 MARIETTA GA          0042   1111   1,065.50
TOTAL PURCHASES AND ADJUSTMENTS FOR THIS PERIOD           $1,540.09
Fees Charged
04/15   04/15   LATE FEE FOR PAYMENT DUE 04/10                            29.00
TOTAL FEES CHARGED FOR THIS PERIOD                        $29.00
Interest Charged
04/28   04/28   INTEREST CHARGED ON PURCHASES                             12.34
04/28   04/28   INTEREST CHARGED ON BALANCE TRANSFERS                     0.00
TOTAL INTEREST CHARGED FOR THIS PERIOD                    $12.34

2026 Totals Year-to-Date
Total fees charged in 2026      $29.00
Total interest charged in 2026      $12.34

Rewards
04/28   04/28   CASH BACK EARNED THIS PERIOD                    12.00
```

### The Citi layout

This is `tests/fixtures/statements/citi/two_cardholders.txt`.

```
Citi                                                  www.citicards.com
Costco Anywhere Visa Card by Citi
Account number ending in: 1111
Billing Period: 08/13/26-09/10/26

Account Summary
Previous balance                      $0.00
Payments                              -$0.00
Credits                               -$43.28
Purchases                             +$759.22
Cash advances                         +$0.00
Fees                                  +$0.00
Interest                              +$0.00
New balance                           $715.94
Credit Limit                          $10,000.00

CARDHOLDER SUMMARY
JOHN DOE      Card ending in 1111      New Charges      $759.22
JANE DOE      Card ending in 2222      New Charges      $0.00

ACCOUNT ACTIVITY
Sale    Post
Date    Date    Description                                  Amount
Payments, Credits and Adjustments
09/03   09/03   ACME WHSE #1234 ALLEN TX                    -$43.28
JOHN DOE
Standard Purchases
09/01   09/01   ACME GAS #1234 ALLEN TX                     $28.96
        09/06   EXAMPLE CENTER DALLAS TX                    $27.05
09/08   09/09   ACME WHSE #1234 ALLEN TX                    $703.21
JANE DOE
No Activity
Fees Charged
TOTAL FEES FOR THIS PERIOD                      $0.00
Interest Charged
TOTAL INTEREST FOR THIS PERIOD                  $0.00

2026 totals year-to-date
Total fees charged in 2026      $0.00
Total interest charged in 2026      $0.00
----- page break -----
Citi                                                  www.citicards.com
Costco Anywhere Visa Card by Citi
Account number ending in: 1111
Billing Period: 08/13/26-09/10/26

Costco Cash Rewards Summary
Rewards balance from last statement      $12.34
09/10   Rewards earned this period      $7.59
Purchases      1% on all other purchases
```

## Requirements

### Part 1: the shared label rule

- **R1.** `find_labeled_amount(lines, label)` returns the amount, in cents, from the first line in `lines` that **fits**, or `None` when no line fits. A line fits when all of these hold:
  - the label is at the start of the line, or has at least two whitespace characters directly before it;
  - directly after the label comes at least one whitespace character, then a money token: any number of the signs `-`, `+`, `=`, each optionally followed by spaces, then `$`, then digits (plain, or grouped in threes with commas), a point, and exactly two digits;
  - `parse_amount` accepts the money token. A line whose token it rejects (such as `+ - $5.00`) does not fit, and the search goes on to the next line.

  The label is matched as literal characters, upper and lower case as written. Text may come before the label and after the money token. The result is what `parse_amount` returns for the token: `- $250.00` gives `-25000`.
- **R2.** `find_labeled_amount` never raises for any list of strings and any label.

This is the rule Phase 4 described under "Part 3". It keeps `Payments      -$20.00` apart from the heading `Payments, Credits and Adjustments`, `Fees      +$0.00` apart from `Fees Charged` and from `TOTAL FEES FOR THIS PERIOD      $0.00`, and `Previous Balance      $250.00` apart from a rewards line such as `Previous Balance      1,234 points`.

### Part 2: Bank of America

- **R3.** `detect` returns `True` when the first page contains both `bankofamerica.com` and `Account#`, with those exact characters. Otherwise `False`.
- **R4.** `account_last4` is the last four digits of the first `Account# ` that is followed by four groups of four digits with one space between groups.
- **R5.** The period is the first text of the form `Month D - Month D, YYYY`: a month name (one capital letter, then lower-case letters), a one- or two-digit day, ` - `, a month name, a day, a comma, and a four-digit year. A month is identified by its first three letters, lower-cased, in the `MONTHS` tuple. Only the end date carries a year. `period_end` has that year. `period_start` has the same year, or the year before when the start month is later in the calendar than the end month: `December 20 - January 19, 2027` starts on 20 December 2026. Do not use `datetime.strptime`.
- **R6.** `parser_name` is `"boa_card"`, `institution` is `"Bank of America"`, and `account_type` is `AccountType.CREDIT_CARD`.
- **R7.** `opening_balance_cents` is the negative of the amount labeled `Previous Balance`, and `closing_balance_cents` is the negative of the amount labeled `New Balance Total`, both found with `find_labeled_amount`. A balance owed, `$1,559.05`, becomes `-155905`. A credit balance is printed with a minus and becomes positive.
- **R8.** `declared_section_totals` has an entry for each of these labels that `find_labeled_amount` finds, and no entry for one it does not find:

  | Label | Section | Value |
  |---|---|---|
  | `Payments and Other Credits` | `PAYMENTS_CREDITS` | the negative of the amount |
  | `Purchases and Adjustments` | `PURCHASES` | the negative of the amount |
  | `Fees Charged` | `FEES` | the negative of the amount |
  | `Interest Charged` | `INTEREST` | the negative of the amount |

  With `Payments and Other Credits      -$945.24` the first entry is `94524`.
- **R9.** A line that is exactly one of those four labels, with nothing else on it, opens that section. A line that starts with `TOTAL` closes the open section. The open section stays open across page breaks and across every other line. The summary line `Fees Charged      $29.00` is not a heading, because it has more on it.
- **R10.** A **row** is read only while a section is open, and is the whole of a line in one of two shapes. The first shape is tried first.

  | Shape | Parts, separated by whitespace |
  |---|---|
  | six parts | transaction date, posting date, description, reference (four digits), card (four digits), amount |
  | four parts | transaction date, posting date, description, amount |

  A date is two digits, `/`, two digits. An amount is an optional `-`, digits (plain, or grouped in threes with commas), a point, and two digits. It has no `$`. The description is everything between the second date and the next part, so a description may itself contain digits, dates, and four-digit numbers.
- **R11.** A row becomes a `StatementLine` with:

  | Field | Value |
  |---|---|
  | `transaction_date` | the first date |
  | `posted_date` | the second date |
  | `description` | the description, through `collapse_ws` |
  | `amount_cents` | the negative of `parse_amount` of the amount: `36.49` is a purchase and becomes `-3649`; `-902.05` is a payment and becomes `90205` |
  | `section` | the open section |
  | `external_ref` | the reference of a six-part row; `None` for a four-part row |
  | `card_last4` | the card of a six-part row; `None` for a four-part row |
  | `cardholder` | `None` |

  Both dates get their year from `parse_month_day` with the statement period. A row whose amount is zero is left out. The sign comes from the printed minus alone, whatever the section.
- **R12.** Every other line is ignored: column headings, `continued on next page...`, the summary, and rows that appear while no section is open (the rewards row after the last `TOTAL` line in the fixture is one).
- **R13.** A missing piece raises `StatementError` with one of these messages, checked in this order:

  | Missing | Message |
  |---|---|
  | the account number of R4 | `boa: account number not found` |
  | the period of R5, or a period with an unknown month name or a date that does not exist | `boa: statement period not found` |
  | `Previous Balance` with an amount | `boa: previous balance not found` |
  | `New Balance Total` with an amount | `boa: new balance not found` |

### Part 3: Citi

- **R14.** `detect` returns `True` when the first page contains both `citicards.com` and `Billing Period:`, with those exact characters. Otherwise `False`.
- **R15.** `account_last4` is the four digits after the first `Account number ending in: `.
- **R16.** The period is the first `Billing Period: MM/DD/YY-MM/DD/YY`. Each year is `2000` plus its two digits. `period_start` and `period_end` are those two dates.
- **R17.** `parser_name` is `"citi_card"`, `institution` is `"Citi"`, and `account_type` is `AccountType.CREDIT_CARD`.
- **R18.** `opening_balance_cents` is the negative of the amount labeled `Previous balance`, and `closing_balance_cents` is the negative of the amount labeled `New balance` (both with a small `b`), found with `find_labeled_amount`.
- **R19.** `declared_section_totals` has these entries, each present only when its labels are found:

  | Section | Value |
  |---|---|
  | `PAYMENTS_CREDITS` | the negative of (`Payments` plus `Credits`); both labels must be found |
  | `PURCHASES` | the negative of `Purchases` |
  | `FEES` | the negative of `Fees` |
  | `INTEREST` | the negative of `Interest` |

  With `Payments      -$500.00` and `Credits      -$19.99` the first entry is `51999`.
- **R20.** A **cardholder line** starts with a name, then whitespace, then `Card ending in ` and four digits. It gives one cardholder: the name through `collapse_ws`, and that card. All cardholder lines of the statement are collected before any row is read.
- **R21.** These lines set the open section. Each is the whole line.

  | Line | Section | Cardholder and card of its rows |
  |---|---|---|
  | `Payments, Credits and Adjustments` | `PAYMENTS_CREDITS` | none |
  | a cardholder's name (compared after `collapse_ws`) | `PURCHASES` | that cardholder and card |
  | `Fees Charged` | `FEES` | none |
  | `Interest Charged` | `INTEREST` | none |

  A line that starts with `TOTAL` closes the open section. The open section stays open across page breaks and across every other line, such as `Standard Purchases` and `No Activity`.
- **R22.** A **row** is read only while a section is open, and is the whole of a line of this shape: an optional sale date followed by whitespace, a post date, whitespace, the description, whitespace, and an amount. A date is two digits, `/`, two digits. An amount is an optional `-`, then `$`, digits (plain, or grouped in threes with commas), a point, and two digits.
- **R23.** A row becomes a `StatementLine` with:

  | Field | Value |
  |---|---|
  | `transaction_date` | the sale date, or `None` when the row has none |
  | `posted_date` | the post date |
  | `description` | the description, through `collapse_ws` |
  | `amount_cents` | the negative of `parse_amount` of the amount: `$28.96` becomes `-2896`; `-$43.28` becomes `4328` |
  | `section`, `cardholder`, `card_last4` | from the open section |
  | `external_ref` | `None` |

  Dates get their year from `parse_month_day` with the statement period. A row whose amount is zero is left out.
- **R24.** Every other line is ignored, including everything after the last `TOTAL` line. The rewards page of the fixture has a line that looks like a row; it must not be read.
- **R25.** A missing piece raises `StatementError` with one of these messages, checked in this order:

  | Missing | Message |
  |---|---|
  | `Account number ending in: ` with four digits | `citi: account number not found` |
  | the period of R16, or a period with a date that does not exist | `citi: billing period not found` |
  | `Previous balance` with an amount | `citi: previous balance not found` |
  | `New balance` with an amount | `citi: new balance not found` |

### Part 4: both parsers

- **R26.** `lines` holds the rows in the order they are printed.
- **R27.** A row whose date falls outside the statement period makes `parse_month_day` raise `StatementError`. Let it pass through unchanged: a row the parser cannot date must stop the import.
- **R28.** `parse` raises nothing but `StatementError`, for any list of strings, including an empty list. No message contains text from the statement.
- **R29.** Importing `finances.ingest.parsers` registers one `BoaCardParser` and one `CitiCardParser`, through the five lines under Design. Neither parser detects the other's statements, nor Capital One's.

## Given tests

Create these four files exactly as shown and do not change them. If one of their tests fails, the production code is wrong.

`tests/unit/test_find_labeled_amount.py` covers every branch of the helper.

```python
import pytest

from finances.ingest.parsers.helpers import find_labeled_amount

SUMMARY = [
    "Rewards      Previous Balance      1,234 points",
    "Payment Due Date      Feb 20, 2026              Previous Balance      $250.00",
    "New Balance      $242.58                    Payments      - $250.00",
    "Minimum Payment Due      $25.00            Other Credits      - $15.65",
    "Credits                               -$43.28",
    "Purchases                             +$759.22",
    "Fees                                  +$0.00",
    "New balance                           = - $67.50",
    "JANE DOE #1111: Payments, Credits and Adjustments",
    "Standard Purchases",
    "Fees Charged",
    "TOTAL FEES FOR THIS PERIOD                      $9.00",
    "Total Transactions for This Period                    $1,258.10",
    "Previous Balance      $999.99",
]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Previous Balance", 25000),
        ("New Balance", 24258),
        ("Payments", -25000),
        ("Other Credits", -1565),
        ("Credits", -4328),
        ("Purchases", 75922),
        ("Fees", 0),
        ("New balance", -6750),
        ("Minimum Payment Due", 2500),
        ("TOTAL FEES FOR THIS PERIOD", 900),
        ("Total Transactions for This Period", 125810),
    ],
)
def test_finds_the_amount_after_a_label(label: str, expected: int) -> None:
    result = find_labeled_amount(SUMMARY, label)
    assert result == expected
    assert type(result) is int


@pytest.mark.parametrize(
    "label",
    [
        "Interest",
        "Transactions",
        "Payment",
        "Balance",
        "Standard Purchases",
        "previous balance",
    ],
)
def test_returns_none_when_no_line_fits(label: str) -> None:
    assert find_labeled_amount(SUMMARY, label) is None


def test_no_lines() -> None:
    assert find_labeled_amount([], "Previous Balance") is None


def test_the_first_fitting_line_wins() -> None:
    assert find_labeled_amount(["Total   $1.00", "Total   $2.00"], "Total") == 100


@pytest.mark.parametrize(
    "line",
    [
        "Fees $5.00",
        "Fees\t$5.00",
        "Fees      $5.00",
        "Other      Fees      $5.00      more text",
        "x  Fees $5.00",
    ],
)
def test_the_label_is_at_the_start_or_after_two_spaces(line: str) -> None:
    assert find_labeled_amount([line], "Fees") == 500


@pytest.mark.parametrize(
    "line",
    [
        "Total Fees $5.00",
        "LateFees $5.00",
        "Fees: $5.00",
        "Fees Charged $5.00",
        "Fees 5.00",
        "Fees $5",
        "Fees $5.0",
        "Fees $ 5.00",
        "Fees",
        "$5.00 Fees",
    ],
)
def test_lines_that_do_not_fit(line: str) -> None:
    assert find_labeled_amount([line], "Fees") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$1,234.56", 123456),
        ("-$1,234.56", -123456),
        ("- $1,234.56", -123456),
        ("+$0.07", 7),
        ("+ $0.07", 7),
        ("= $10.00", 1000),
        ("= - $67.50", -6750),
        ("$1234.56", 123456),
    ],
)
def test_money_forms(text: str, expected: int) -> None:
    assert find_labeled_amount([f"Total      {text}"], "Total") == expected


def test_a_line_whose_money_cannot_be_read_is_passed_over() -> None:
    lines = ["Total      + - $5.00", "Total      = = $6.00", "Total      $7.00"]
    assert find_labeled_amount(lines, "Total") == 700


def test_a_label_with_special_characters_is_matched_literally() -> None:
    assert find_labeled_amount(["Fees (est.)   $3.00"], "Fees (est.)") == 300
    assert find_labeled_amount(["Fees (estX)   $3.00"], "Fees (est.)") is None


def test_ascii_digits_only() -> None:
    assert find_labeled_amount(["Total   $١٢.٣٤"], "Total") is None
```

`tests/unit/test_boa_parser.py` checks the parser against its fixtures: every field of every line.

```python
from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers import detect_parser, registered_parsers
from finances.ingest.parsers.boa import BoaCardParser
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementLine

FIXTURES = Path(__file__).parent.parent / "fixtures" / "statements"
STATEMENTS = ["two_pages", "year_end", "credit_balance"]
OTHER_BANKS = [
    ("capital_one", "single_card"),
    ("capital_one", "multi_card"),
    ("capital_one", "other_bank"),
    ("citi", "two_cardholders"),
    ("citi", "year_end"),
]


def pages(name: str, bank: str = "boa") -> list[str]:
    return (FIXTURES / bank / f"{name}.txt").read_text(encoding="utf-8").split("\f")


def parse(name: str) -> ParsedStatement:
    return BoaCardParser().parse(pages(name))


def test_the_parser_is_registered_once_under_its_name() -> None:
    names = [parser.name for parser in registered_parsers()]
    assert names.count("boa_card") == 1
    assert BoaCardParser.name == "boa_card"


@pytest.mark.parametrize("name", STATEMENTS)
def test_detects_its_own_fixtures(name: str) -> None:
    assert BoaCardParser().detect(pages(name)[0]) is True
    assert detect_parser(pages(name)).name == "boa_card"


@pytest.mark.parametrize(("bank", "name"), OTHER_BANKS)
def test_does_not_detect_another_banks_statement(bank: str, name: str) -> None:
    assert BoaCardParser().detect(pages(name, bank)[0]) is False


@pytest.mark.parametrize("name", STATEMENTS)
def test_every_fixture_reconciles(name: str) -> None:
    result = reconcile(parse(name))
    assert result.difference_cents == 0
    assert result.section_mismatches == {}
    assert result.ok is True


@pytest.mark.parametrize("name", STATEMENTS)
def test_parsing_twice_gives_the_same_statement(name: str) -> None:
    assert parse(name) == parse(name)


@pytest.mark.parametrize("name", STATEMENTS)
def test_the_page_breaks_do_not_matter(name: str) -> None:
    joined = ["\n".join(pages(name))]
    assert BoaCardParser().parse(joined) == parse(name)


def test_two_pages_header_balances_and_totals() -> None:
    statement = parse("two_pages")
    assert statement.parser_name == "boa_card"
    assert statement.institution == "Bank of America"
    assert statement.account_type is AccountType.CREDIT_CARD
    assert statement.account_last4 == "1111"
    assert statement.period_start == date(2026, 3, 29)
    assert statement.period_end == date(2026, 4, 28)
    assert statement.opening_balance_cents == -155905
    assert statement.closing_balance_cents == -219524
    assert statement.declared_section_totals == {
        Section.PAYMENTS_CREDITS: 94524,
        Section.PURCHASES: -154009,
        Section.FEES: -2900,
        Section.INTEREST: -1234,
    }


def test_two_pages_lines() -> None:
    assert parse("two_pages").lines == [
        StatementLine(
            date(2026, 4, 6),
            date(2026, 4, 3),
            "EXAMPLESOFT*STORE REDMOND WA",
            4319,
            Section.PAYMENTS_CREDITS,
            card_last4="1111",
            external_ref="3012",
        ),
        StatementLine(
            date(2026, 4, 7),
            date(2026, 4, 7),
            "PAYMENT FROM CHK 9999 CONF#M00000000",
            90205,
            Section.PAYMENTS_CREDITS,
            card_last4="1111",
            external_ref="4733",
        ),
        StatementLine(
            date(2026, 3, 30),
            date(2026, 3, 28),
            "ACME GROCERY #123 DECATUR GA",
            -3649,
            Section.PURCHASES,
            card_last4="2222",
            external_ref="7838",
        ),
        StatementLine(
            date(2026, 4, 2),
            date(2026, 4, 1),
            "FOOBAR CAFE ATLANTA GA",
            -1275,
            Section.PURCHASES,
            card_last4="1111",
            external_ref="1190",
        ),
        StatementLine(
            date(2026, 4, 2),
            date(2026, 4, 1),
            "FOOBAR CAFE ATLANTA GA",
            -1275,
            Section.PURCHASES,
            card_last4="1111",
            external_ref="1191",
        ),
        StatementLine(
            date(2026, 4, 11),
            date(2026, 4, 10),
            "EXAMPLE AIRLINES 0061234567890 TX",
            -41260,
            Section.PURCHASES,
            card_last4="2222",
            external_ref="5521",
        ),
        StatementLine(
            date(2026, 4, 21),
            date(2026, 4, 20),
            "ACME HARDWARE #88 2026 MARIETTA GA",
            -106550,
            Section.PURCHASES,
            card_last4="1111",
            external_ref="0042",
        ),
        StatementLine(
            date(2026, 4, 15),
            date(2026, 4, 15),
            "LATE FEE FOR PAYMENT DUE 04/10",
            -2900,
            Section.FEES,
        ),
        StatementLine(
            date(2026, 4, 28),
            date(2026, 4, 28),
            "INTEREST CHARGED ON PURCHASES",
            -1234,
            Section.INTEREST,
        ),
    ]


def test_year_end_header_balances_and_totals() -> None:
    statement = parse("year_end")
    assert statement.parser_name == "boa_card"
    assert statement.institution == "Bank of America"
    assert statement.account_type is AccountType.CREDIT_CARD
    assert statement.account_last4 == "3333"
    assert statement.period_start == date(2026, 12, 20)
    assert statement.period_end == date(2027, 1, 19)
    assert statement.opening_balance_cents == 0
    assert statement.closing_balance_cents == -16049
    assert statement.declared_section_totals == {
        Section.PAYMENTS_CREDITS: 0,
        Section.PURCHASES: -16049,
        Section.FEES: 0,
        Section.INTEREST: 0,
    }


def test_year_end_lines() -> None:
    assert parse("year_end").lines == [
        StatementLine(
            date(2026, 12, 20),
            date(2026, 12, 19),
            "ACME TOYS #7 AUSTIN TX",
            -8999,
            Section.PURCHASES,
            card_last4="3333",
            external_ref="2001",
        ),
        StatementLine(
            date(2027, 1, 2),
            date(2026, 12, 31),
            "FOOBAR LIQUOR AUSTIN TX",
            -4550,
            Section.PURCHASES,
            card_last4="3333",
            external_ref="2002",
        ),
        StatementLine(
            date(2027, 1, 16),
            date(2027, 1, 15),
            "ACME GYM 512-555-0100 TX",
            -2500,
            Section.PURCHASES,
            card_last4="3333",
            external_ref="2003",
        ),
    ]


def test_credit_balance_header_balances_and_totals() -> None:
    statement = parse("credit_balance")
    assert statement.parser_name == "boa_card"
    assert statement.institution == "Bank of America"
    assert statement.account_type is AccountType.CREDIT_CARD
    assert statement.account_last4 == "5555"
    assert statement.period_start == date(2026, 6, 1)
    assert statement.period_end == date(2026, 6, 30)
    assert statement.opening_balance_cents == 2000
    assert statement.closing_balance_cents == 2775
    assert statement.declared_section_totals == {
        Section.PAYMENTS_CREDITS: 1500,
        Section.PURCHASES: -725,
        Section.FEES: 0,
        Section.INTEREST: 0,
    }


def test_credit_balance_lines() -> None:
    assert parse("credit_balance").lines == [
        StatementLine(
            date(2026, 6, 13),
            date(2026, 6, 12),
            "ACME OUTLET REFUND DALLAS TX",
            1500,
            Section.PAYMENTS_CREDITS,
            card_last4="5555",
            external_ref="9100",
        ),
        StatementLine(
            date(2026, 6, 21),
            date(2026, 6, 20),
            "FOOBAR SNACKS DALLAS TX",
            -725,
            Section.PURCHASES,
            card_last4="5555",
            external_ref="9101",
        ),
    ]


@pytest.mark.parametrize(
    "first_page",
    [
        "",
        "www.bankofamerica.com",
        "Account# 4400 0000 0000 1111",
        "WWW.BANKOFAMERICA.COM\nACCOUNT# 4400 0000 0000 1111",
        "Bank of America\nAccount number 4400 0000 0000 1111",
    ],
)
def test_detect_needs_both_markers(first_page: str) -> None:
    assert BoaCardParser().detect(first_page) is False


def test_detect_with_both_markers() -> None:
    assert BoaCardParser().detect("see bankofamerica.com\nAccount# 4400 0000 0000 1111") is True


def test_spaces_inside_a_description_are_collapsed() -> None:
    text = pages("credit_balance")[0].replace(
        "FOOBAR SNACKS DALLAS TX", "FOOBAR   SNACKS  DALLAS TX"
    )
    assert BoaCardParser().parse([text]).lines[1].description == "FOOBAR SNACKS DALLAS TX"
```

`tests/unit/test_citi_parser.py` does the same for Citi.

```python
from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers import detect_parser, registered_parsers
from finances.ingest.parsers.citi import CitiCardParser
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementLine

FIXTURES = Path(__file__).parent.parent / "fixtures" / "statements"
STATEMENTS = ["two_cardholders", "year_end"]
OTHER_BANKS = [
    ("capital_one", "single_card"),
    ("capital_one", "multi_card"),
    ("capital_one", "other_bank"),
    ("boa", "two_pages"),
    ("boa", "year_end"),
    ("boa", "credit_balance"),
]


def pages(name: str, bank: str = "citi") -> list[str]:
    return (FIXTURES / bank / f"{name}.txt").read_text(encoding="utf-8").split("\f")


def parse(name: str) -> ParsedStatement:
    return CitiCardParser().parse(pages(name))


def test_the_parser_is_registered_once_under_its_name() -> None:
    names = [parser.name for parser in registered_parsers()]
    assert names.count("citi_card") == 1
    assert CitiCardParser.name == "citi_card"


@pytest.mark.parametrize("name", STATEMENTS)
def test_detects_its_own_fixtures(name: str) -> None:
    assert CitiCardParser().detect(pages(name)[0]) is True
    assert detect_parser(pages(name)).name == "citi_card"


@pytest.mark.parametrize(("bank", "name"), OTHER_BANKS)
def test_does_not_detect_another_banks_statement(bank: str, name: str) -> None:
    assert CitiCardParser().detect(pages(name, bank)[0]) is False


@pytest.mark.parametrize("name", STATEMENTS)
def test_every_fixture_reconciles(name: str) -> None:
    result = reconcile(parse(name))
    assert result.difference_cents == 0
    assert result.section_mismatches == {}
    assert result.ok is True


@pytest.mark.parametrize("name", STATEMENTS)
def test_parsing_twice_gives_the_same_statement(name: str) -> None:
    assert parse(name) == parse(name)


@pytest.mark.parametrize("name", STATEMENTS)
def test_the_page_breaks_do_not_matter(name: str) -> None:
    joined = ["\n".join(pages(name))]
    assert CitiCardParser().parse(joined) == parse(name)


def test_two_cardholders_header_balances_and_totals() -> None:
    statement = parse("two_cardholders")
    assert statement.parser_name == "citi_card"
    assert statement.institution == "Citi"
    assert statement.account_type is AccountType.CREDIT_CARD
    assert statement.account_last4 == "1111"
    assert statement.period_start == date(2026, 8, 13)
    assert statement.period_end == date(2026, 9, 10)
    assert statement.opening_balance_cents == 0
    assert statement.closing_balance_cents == -71594
    assert statement.declared_section_totals == {
        Section.PAYMENTS_CREDITS: 4328,
        Section.PURCHASES: -75922,
        Section.FEES: 0,
        Section.INTEREST: 0,
    }


def test_two_cardholders_lines() -> None:
    assert parse("two_cardholders").lines == [
        StatementLine(
            date(2026, 9, 3),
            date(2026, 9, 3),
            "ACME WHSE #1234 ALLEN TX",
            4328,
            Section.PAYMENTS_CREDITS,
        ),
        StatementLine(
            date(2026, 9, 1),
            date(2026, 9, 1),
            "ACME GAS #1234 ALLEN TX",
            -2896,
            Section.PURCHASES,
            card_last4="1111",
            cardholder="JOHN DOE",
        ),
        StatementLine(
            date(2026, 9, 6),
            None,
            "EXAMPLE CENTER DALLAS TX",
            -2705,
            Section.PURCHASES,
            card_last4="1111",
            cardholder="JOHN DOE",
        ),
        StatementLine(
            date(2026, 9, 9),
            date(2026, 9, 8),
            "ACME WHSE #1234 ALLEN TX",
            -70321,
            Section.PURCHASES,
            card_last4="1111",
            cardholder="JOHN DOE",
        ),
    ]


def test_year_end_header_balances_and_totals() -> None:
    statement = parse("year_end")
    assert statement.parser_name == "citi_card"
    assert statement.institution == "Citi"
    assert statement.account_type is AccountType.CREDIT_CARD
    assert statement.account_last4 == "4444"
    assert statement.period_start == date(2026, 12, 13)
    assert statement.period_end == date(2027, 1, 12)
    assert statement.opening_balance_cents == -50000
    assert statement.closing_balance_cents == -27713
    assert statement.declared_section_totals == {
        Section.PAYMENTS_CREDITS: 51999,
        Section.PURCHASES: -25625,
        Section.FEES: -2900,
        Section.INTEREST: -1187,
    }


def test_year_end_lines() -> None:
    assert parse("year_end").lines == [
        StatementLine(
            date(2026, 12, 28),
            date(2026, 12, 28),
            "ONLINE PAYMENT, THANK YOU",
            50000,
            Section.PAYMENTS_CREDITS,
        ),
        StatementLine(
            date(2027, 1, 5),
            date(2027, 1, 4),
            "FOOBAR OUTDOORS PLANO TX",
            1999,
            Section.PAYMENTS_CREDITS,
        ),
        StatementLine(
            date(2026, 12, 13),
            date(2026, 12, 12),
            "ACME WHSE #1234 PLANO TX",
            -15075,
            Section.PURCHASES,
            card_last4="4444",
            cardholder="MARIA DE LA CRUZ",
        ),
        StatementLine(
            date(2027, 1, 2),
            date(2026, 12, 31),
            "FOOBAR PIZZA PLANO TX",
            -2350,
            Section.PURCHASES,
            card_last4="4444",
            cardholder="MARIA DE LA CRUZ",
        ),
        StatementLine(
            date(2027, 1, 11),
            date(2027, 1, 10),
            "ACME GAS #1234 PLANO TX",
            -4100,
            Section.PURCHASES,
            card_last4="6666",
            cardholder="LEE O'NEIL",
        ),
        StatementLine(
            date(2027, 1, 11),
            None,
            "ACME GAS #1234 PLANO TX",
            -4100,
            Section.PURCHASES,
            card_last4="6666",
            cardholder="LEE O'NEIL",
        ),
        StatementLine(date(2027, 1, 12), date(2027, 1, 12), "LATE FEE", -2900, Section.FEES),
        StatementLine(
            date(2027, 1, 12),
            date(2027, 1, 12),
            "INTEREST CHARGED TO STANDARD PURCH",
            -1187,
            Section.INTEREST,
        ),
    ]


@pytest.mark.parametrize(
    "first_page",
    [
        "",
        "www.citicards.com",
        "Billing Period: 08/13/26-09/10/26",
        "WWW.CITICARDS.COM\nBILLING PERIOD: 08/13/26-09/10/26",
        "Citi\nBilling Period 08/13/26-09/10/26",
    ],
)
def test_detect_needs_both_markers(first_page: str) -> None:
    assert CitiCardParser().detect(first_page) is False


def test_detect_with_both_markers() -> None:
    assert CitiCardParser().detect("see citicards.com\nBilling Period: 08/13/26-09/10/26") is True


def test_spaces_inside_a_description_are_collapsed() -> None:
    text = pages("two_cardholders")[0].replace(
        "ACME GAS #1234 ALLEN TX", "ACME   GAS  #1234 ALLEN TX"
    )
    assert CitiCardParser().parse([text]).lines[1].description == "ACME GAS #1234 ALLEN TX"


def test_a_row_with_a_zero_amount_is_left_out() -> None:
    text = pages("two_cardholders")[0].replace("$28.96", "$0.00")
    lines = CitiCardParser().parse([text]).lines
    assert [item.amount_cents for item in lines] == [4328, -2705, -70321]
```

`tests/integration/test_boa_citi_import.py` builds real PDFs and imports them through the registry and the import service.

```python
from datetime import date

from sqlalchemy import Engine

from finances.db.engine import session_scope
from finances.db.repositories import create_account, latest_balance, list_transactions
from finances.ingest.service import ImportStatus, StatementImportResult, import_statement

BOA = [
    "Bank of America   www.bankofamerica.com",
    "Account# 4400 0000 0000 7777",
    "May 1 - May 31, 2026",
    "Previous Balance   $50.00",
    "Payments and Other Credits   -$50.00",
    "Purchases and Adjustments   $31.75",
    "Fees Charged   $0.00",
    "Interest Charged   $1.10",
    "New Balance Total   $32.85",
    "Payments and Other Credits",
    "05/10  05/10\tPAYMENT FROM CHK 9999 CONF#M00000000   4733  7777  -50.00",
    "TOTAL PAYMENTS AND OTHER CREDITS FOR THIS PERIOD   -$50.00",
    "Purchases and Adjustments",
    "05/02  05/03\tACME GROCERY #123 DECATUR GA   7838  7777  31.75",
    "TOTAL PURCHASES AND ADJUSTMENTS FOR THIS PERIOD   $31.75",
    "Interest Charged",
    "05/31  05/31\tINTEREST CHARGED ON PURCHASES   1.10",
    "TOTAL INTEREST CHARGED FOR THIS PERIOD   $1.10",
]
CITI = [
    "Citi   www.citicards.com",
    "Account number ending in: 8888",
    "Billing Period: 05/01/26-05/31/26",
    "Previous balance   $20.00",
    "Payments   -$20.00",
    "Credits   -$0.00",
    "Purchases   +$64.40",
    "Fees   +$0.00",
    "Interest   +$0.00",
    "New balance   $64.40",
    "CARDHOLDER SUMMARY",
    "JANE DOE   Card ending in 8888   New Charges   $64.40",
    "Payments, Credits and Adjustments",
    "05/15  05/15\tONLINE PAYMENT, THANK YOU   -$20.00",
    "JANE DOE",
    "Standard Purchases",
    "05/04  05/05\tACME WHSE #1234 ALLEN TX   $60.00",
    "\t05/20   FOOBAR CAFE   $4.40",
    "Fees Charged",
    "TOTAL FEES FOR THIS PERIOD   $0.00",
]


def stored(session) -> list[tuple]:
    rows = sorted(list_transactions(session), key=lambda item: item.id)
    return [
        (r.posted_date, r.transaction_date, r.amount_cents, r.description, r.section) for r in rows
    ]


def test_a_bank_of_america_pdf_is_imported(db_engine: Engine, make_pdf) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Cash Rewards", "Bank of America", "credit_card", last4="7777")
        result = import_statement(session, filename="boa-may.pdf", content=make_pdf([BOA]))
    assert result == StatementImportResult(
        filename="boa-may.pdf",
        status=ImportStatus.IMPORTED,
        message="imported",
        parser_name="boa_card",
        account_name="Test Cash Rewards",
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        lines_parsed=3,
        inserted=3,
        duplicates=0,
    )
    with session_scope(db_engine) as session:
        assert stored(session) == [
            (
                date(2026, 5, 10),
                date(2026, 5, 10),
                5000,
                "PAYMENT FROM CHK 9999 CONF#M00000000",
                "payments_credits",
            ),
            (
                date(2026, 5, 3),
                date(2026, 5, 2),
                -3175,
                "ACME GROCERY #123 DECATUR GA",
                "purchases",
            ),
            (
                date(2026, 5, 31),
                date(2026, 5, 31),
                -110,
                "INTEREST CHARGED ON PURCHASES",
                "interest",
            ),
        ]
        rows = sorted(list_transactions(session), key=lambda item: item.id)
        assert [(r.card_last4, r.external_id, r.cardholder) for r in rows] == [
            ("7777", "4733", None),
            ("7777", "7838", None),
            (None, None, None),
        ]
        assert latest_balance(session, 1).balance_cents == -3285


def test_a_citi_pdf_is_imported(db_engine: Engine, make_pdf) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Costco Visa", "Citi", "credit_card", last4="8888")
        result = import_statement(session, filename="citi-may.pdf", content=make_pdf([CITI]))
    assert result == StatementImportResult(
        filename="citi-may.pdf",
        status=ImportStatus.IMPORTED,
        message="imported",
        parser_name="citi_card",
        account_name="Test Costco Visa",
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        lines_parsed=3,
        inserted=3,
        duplicates=0,
    )
    with session_scope(db_engine) as session:
        assert stored(session) == [
            (
                date(2026, 5, 15),
                date(2026, 5, 15),
                2000,
                "ONLINE PAYMENT, THANK YOU",
                "payments_credits",
            ),
            (date(2026, 5, 5), date(2026, 5, 4), -6000, "ACME WHSE #1234 ALLEN TX", "purchases"),
            (date(2026, 5, 20), None, -440, "FOOBAR CAFE", "purchases"),
        ]
        rows = sorted(list_transactions(session), key=lambda item: item.id)
        assert [(r.card_last4, r.cardholder) for r in rows] == [
            (None, None),
            ("8888", "JANE DOE"),
            ("8888", "JANE DOE"),
        ]
        assert latest_balance(session, 1).balance_cents == -6440


def test_each_statement_goes_to_its_own_bank(db_engine: Engine, make_pdf) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Cash Rewards", "Bank of America", "credit_card", last4="7777")
        create_account(session, "Test Costco Visa", "Citi", "credit_card", last4="8888")
        first = import_statement(session, filename="a.pdf", content=make_pdf([BOA]))
        second = import_statement(session, filename="b.pdf", content=make_pdf([CITI]))
    assert (first.parser_name, first.account_name) == ("boa_card", "Test Cash Rewards")
    assert (second.parser_name, second.account_name) == ("citi_card", "Test Costco Visa")
```

## Tests to write

`tests/unit/test_boa_parser_more.py` and `tests/unit/test_citi_parser_more.py`, with synthetic text only. Build statements as lists of lines in the test, or by editing the text of a fixture as the given tests do. The given tests cover the fixtures; yours cover what the fixtures do not. For each parser:

- each of its four messages, exactly, and the order in which missing pieces are reported when two are missing
- a period with a date that does not exist (`June 31, 2026`; `02/30/26`), and for Bank of America a month name that is not a month
- R27: a row dated outside the period, with the helper's message
- R28: an empty list of pages, and a page of unrelated text
- declared totals when a summary label is missing: the entry is left out and the others stay. For Citi, `Payments` present and `Credits` absent leaves `PAYMENTS_CREDITS` out
- a row before any section heading, and a row after a `TOTAL` line, both ignored
- a credit printed among the purchases (positive, and still in `PURCHASES`)

And for one parser each:

- Bank of America: a four-part row in the purchases section; a six-part row whose description ends in a number; a statement in one year (`March 29 - April 28`) and across a year end
- Citi: three cardholders, one with a name of several words and a hyphen; a cardholder with no activity between two with activity; a cardholder name printed with a different number of spaces in the summary and above the rows; rows without a sale date under two different cardholders

Every line and branch of `boa.py` and `citi.py` must be reached by a test.

## Rules for this phase

- **Money is `int` cents.** Amounts are read with `parse_amount` only. `float` does not appear in `boa.py`, `citi.py`, or the new function.
- **Signs are from the account holder's side** (`AGENTS.md`): purchases, fees, and interest negative; payments and refunds positive; a balance owed negative.
- **Constant messages.** The eight messages in R13 and R25 are the only ones these modules create. Nothing from a statement goes into an exception, and nothing is logged or printed.
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
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, at least N + 106 passed, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_find_labeled_amount.py tests/unit/test_boa_parser.py tests/unit/test_citi_parser.py tests/integration/test_boa_citi_import.py --no-cov` | exactly `106 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| the search below | no output |
| `git diff HEAD --stat -- src/finances/ingest/parsers/capital_one.py tests/fixtures` | no output |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -F -e "strptime" -e "float" -e "print(" -e "logging" -e "\d" -- src/finances/ingest/parsers/boa.py src/finances/ingest/parsers/citi.py`

### Real statements

Then run the check on real statements, if this machine has them:

`.venv/bin/python -m pytest tests/real_samples/check_real_samples.py --no-cov -rA`

- If it reports `no PDF files in data/samples`, say so in your report. That is not a failure of this phase.
- If it runs, each Bank of America and Citi sample must pass. A sample from a bank without a parser shows as `xfail` with `unrecognized statement format`, which is expected.
- If a Bank of America or Citi sample fails, report the summary line the check printed (sample number, parser name, line count, difference in cents, sections that differ) and nothing else. Then find the cause using the synthetic layouts in this spec and in `docs/statement-formats.md`. Do not open the PDF or print its text to find out. If the cause is a layout this spec does not describe, stop and report that: the architect will add a synthetic example of it.
- If a Capital One sample fails, report its summary line and change nothing. That parser belongs to Phase 4.

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 5: the Bank of America and Citi credit card parsers (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N, the final passed count, and the outcome of the real-statement check as counts only (for example "3 passed, 2 xfailed" or "no samples on this machine"). Under "Deviations", list your design choices (private helpers, how each parse is divided) and anything you did that the spec did not ask for, or `None`.

In your final message, give the output line of each acceptance command, and for each of R1 to R29 the name of a test that covers it.
