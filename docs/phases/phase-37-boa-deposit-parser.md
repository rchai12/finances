# Phase 37: Bank of America checking and savings

## Goal

A parser for Bank of America checking and savings statements, with the owner's choices (2026-10-25): one parser for both kinds of account, checks read, and a debit card row dated by the day of purchase. Today such a statement is refused as `unrecognized statement format`. After this phase:

- `fin import statement` and the web upload recognize these statements as `boa_deposit`, parse them, and reconcile them like every other parser's;
- the owner's two real checking statements parse and reconcile in the opt-in real-sample check (`check_real_samples.py` already tries every PDF in `data/samples/`).

The layout below was confirmed on the two real statements by counts only (AGENTS.md rule 6): the header, the balances, the summary, the deposits and other subtractions sections, their rows and totals, and reconciliation. Neither statement has card purchases, checks, service fees, or a savings product, so those parts follow Bank of America's public layout and are guesses; a guess that is wrong makes that statement fail to reconcile and be refused, never imported wrong.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/statement-formats.md`: the notes at the top, section 4 (Truist, the closest layout), and section 8 (this layout, added with this spec). Where that document and this spec differ, this spec is right.
- `src/finances/ingest/parsers/truist.py` (the model to follow), `src/finances/ingest/parsers/helpers.py` (`squeeze`, `parse_amount`, `infer_year`, `MONTHS`), `src/finances/ingest/statement.py`, `src/finances/ingest/parsers/__init__.py`
- `tests/unit/test_parser_fuzz.py`: every registered parser is fed damaged copies of every fixture and must answer with a `ParsedStatement` or a `StatementError`, never another exception

## Starting state

N is `3952` when Phase 20d is the last phase built. Five parsers are registered: `capital_one_card`, `boa_card`, `citi_card`, `truist_deposit`, `marcus_savings`. `boa_card` detects `bankofamerica.com` with `Account#`; these statements print `Account number:` on the first page and `Account #` (with a space) on later pages, so it does not claim them. No migration.

## Scope

| Path | What changes |
|---|---|
| `src/finances/ingest/parsers/boa_deposit.py` | new: `BoaDepositParser` (R1 to R9) |
| `src/finances/ingest/parsers/__init__.py` | register `BoaDepositParser()` after the others (R1) |
| `tests/fixtures/statements/boa_deposit/checking.txt`, `savings.txt`, `year_end.txt` | new: given |
| `tests/unit/test_boa_deposit_parser.py` | new: given |
| `tests/unit/test_boa_deposit_parser_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

`BoaDepositParser` is the only public name of its module.

## Out of scope

- Any change to the other parsers, `describe_layout.py`, `check_real_samples.py`, or the import service.
- A Bank of America CSV export; card numbers on rows (`card_last4` stays None); a cardholder.

## Dependencies

None new.

## Design

```python
# src/finances/ingest/parsers/boa_deposit.py
class BoaDepositParser:
    name = "boa_deposit"
    def detect(self, first_page: str) -> bool: ...
    def parse(self, pages: list[str]) -> ParsedStatement: ...
```

`parse` reads every line of every page with outer spaces stripped, as one list, as `TruistDepositParser` does. `institution` is `Bank of America`.

| Part | Rule |
|---|---|
| Detect | the first page contains `bankofamerica.com`, `Account number:`, and `Beginning balance on` |
| Account number | the first line holding `Account number:` followed by digits in groups (`Account number: 0000 1234 1111`); `account_last4` is the last four digits |
| Account type | the product line is the last line **before** that account-number line that starts with `Your `; `SAVINGS` when it holds the word `Savings`, otherwise `CHECKING` (also when there is no such line) |
| Period | the first `for <Month> <D>, <YYYY> to <Month> <D>, <YYYY>` anywhere on a line (it shares its line with the account number); the month is matched by its first three letters, any case, against `MONTHS` |
| Balances | opening from `Beginning balance on <Month> <D>, <YYYY>` followed by money, closing from `Ending balance on …` the same way; money is `$1,234.56` or `-$1,234.56`, read with `parse_amount`; the first line that fits |
| Sections | a line that, with spaces ignored, **equals** one of the headings below opens that section; a line that starts with `Total` (spaces ignored) closes it; the open section stays open across page breaks and every other line |
| Rows | in an open section other than checks, a line that is wholly `MM/DD/YY  description  amount`, the amount `1,234.56` or `-1,234.56` with no `$`; the date is `20YY-MM-DD`; the amount is signed **as printed**; a zero amount is skipped; the description is the text between, with runs of spaces collapsed; lines that do not fit (column headers, wrapped description lines, `continued` notes) are ignored |
| Purchase date | a description that starts with `CHECKCARD ` or `PURCHASE ` followed by four digits `MMDD` gets `transaction_date` from `infer_year(MM, DD, period_start, period_end)`; when that raises `StatementError` the row keeps `transaction_date` None |
| Checks | in the checks section each `MM/DD/YY  number  amount` on a line is one check, one or two per line; the number may carry a `*` before or after it; the line is `CHECK <number>`, `external_ref` the number, the amount signed as printed |
| Declared totals | the first line starting (spaces ignored) with each total label below; its last money on the line, signed as printed; the two withdrawal totals are added together into `WITHDRAWALS` when either is found |

| Heading | Section | Total label |
|---|---|---|
| `Deposits and other additions` | `DEPOSITS` | `Total deposits and other additions` |
| `ATM and debit card subtractions` | `WITHDRAWALS` | `Total ATM and debit card subtractions` |
| `Other subtractions` | `WITHDRAWALS` | `Total other subtractions` |
| `Checks` | `CHECKS` | `Total checks` |
| `Service fees` | `FEES` | `Total service fees` |

`Withdrawals and other subtractions` is a heading that groups the two withdrawal sections; it opens nothing. The summary lines (`Deposits and other additions  3,250.25`) carry an amount, so they never equal a heading.

| Refusal (`StatementError`) | When |
|---|---|
| `boa_deposit: account number not found` | no account-number line with at least four digits |
| `boa_deposit: statement period not found` | no period, or a period date that does not exist (`September 31`, an unknown month) |
| `boa_deposit: beginning balance not found` | no beginning balance |
| `boa_deposit: ending balance not found` | no ending balance |
| `boa_deposit: invalid date` | a row or check whose date does not exist (`02/30/26`) |

The checks are made in the order of that table.

## Requirements

- **R1.** `BoaDepositParser` as designed, registered once in `parsers/__init__.py`.
- **R2.** `detect` as designed. It is false for every other bank's fixture, and no other parser detects this parser's fixtures.
- **R3.** The account number, the account type, and the period as designed.
- **R4.** The opening and closing balances as designed.
- **R5.** Sections open and close as designed; the open section survives a page break.
- **R6.** Rows as designed, signed as printed, wrapped lines ignored.
- **R7.** The purchase date of a card row as designed.
- **R8.** Checks as designed, one or two per line.
- **R9.** Declared totals as designed, the two withdrawal totals added together; the refusals as designed, and no other exception on any input (the fuzz test).

## Given fixtures

Synthetic. Each `----- page break -----` line stands for one form feed character (`\f`): the file holds the text before it, then `\f`, then the text after, and the marker line itself is not in the file. Only `checking.txt` has a page break. Do not change them.

`tests/fixtures/statements/boa_deposit/checking.txt`

```text
Bank of America, N.A.                                   bankofamerica.com
P.O. Box 15284                                          Customer service: 1.800.555.0100
Wilmington, DE 19850

JANE DOE
100 EXAMPLE ST
ANYTOWN, GA 30000

Your Advantage Plus Banking

for September 1, 2026 to September 30, 2026        Account number: 0000 1234 1111

Account summary
Beginning balance on September 1, 2026                       $1,500.00
Deposits and other additions                                  3,250.25
ATM and debit card subtractions                                -186.40
Other subtractions                                           -1,620.00
Checks                                                         -350.00
Service fees                                                    -12.00
Ending balance on September 30, 2026                         $2,581.85

Tip: set up automatic transfers to your Savings account.

Deposits and other additions
Date        Description                                                    Amount
09/02/26    EXAMPLE EMPLOYER DES:PAYROLL ID:XXXXX00001 INDN:DOE,JANE     3,000.00
            CO ID:XXXXX00002 PPD
09/15/26    Zelle payment from JOHN DOE Conf# x0000001                     250.00
09/30/26    Interest Earned                                                  0.25
Total deposits and other additions                                    $3,250.25

Withdrawals and other subtractions

ATM and debit card subtractions
Date        Description                                                    Amount
09/03/26    CHECKCARD 0902 ACME COFFEE ANYTOWN GA 24000000000000000000001   -4.50
09/08/26    PURCHASE 0906 FOOBAR GROCERY ANYTOWN GA                        -81.90
continued on the next page
Page 1 of 2
----- page break -----
Bank of America, N.A.                                   bankofamerica.com
JANE DOE ! Account # 0000 1234 1111 ! September 1, 2026 to September 30, 2026

ATM and debit card subtractions - continued
Date        Description                                                    Amount
09/20/26    BKOFAMERICA ATM 09/20 #000001 WITHDRWL ANYTOWN GA             -100.00
Total ATM and debit card subtractions                                   -$186.40

Other subtractions
Date        Description                                                    Amount
09/05/26    EXAMPLE CARD DES:ACH PMT ID:00000000001 INDN:JANE DOE CO    -1,200.00
            ID:XXXXX00003 PPD
09/18/26    Online Banking transfer to SAV 2222 Confirmation# 0000000001   -420.00
Total other subtractions                                              -$1,620.00

Checks
Date        Check #        Amount        Date        Check #        Amount
09/10/26    1041          -125.00        09/14/26    1042*         -200.00
09/25/26    1044           -25.00
* There is a gap in the check sequence
Total checks                                                            -$350.00

Service fees
Date        Transaction description                                        Amount
09/30/26    Monthly Maintenance Fee                                        -12.00
Total service fees                                                       -$12.00

Daily ledger balances
Date        Balance ($)        Date        Balance ($)
09/01       1,500.00           09/02       4,500.00
Page 2 of 2
```

`tests/fixtures/statements/boa_deposit/savings.txt`

```text
Bank of America, N.A.                                   bankofamerica.com

JANE DOE
100 EXAMPLE ST
ANYTOWN, GA 30000

Your Bank of America Advantage Savings

for August 1, 2026 to August 31, 2026              Account number: 0000 5678 2222

Account summary
Beginning balance on August 1, 2026                         $10,000.00
Deposits and other additions                                    420.31
ATM and debit card subtractions                                  -0.00
Other subtractions                                             -500.00
Service fees                                                     -0.00
Ending balance on August 31, 2026                            $9,920.31

Deposits and other additions
Date        Description                                                    Amount
08/12/26    Online Banking transfer from CHK 1111 Confirmation# 0000000002  420.00
08/31/26    Interest Earned                                                  0.31
Total deposits and other additions                                      $420.31

Withdrawals and other subtractions

Other subtractions
Date        Description                                                    Amount
08/20/26    Online Banking transfer to CHK 1111 Confirmation# 0000000003   -500.00
Total other subtractions                                                -$500.00
Page 1 of 1
```

`tests/fixtures/statements/boa_deposit/year_end.txt`

```text
Bank of America, N.A.                                   bankofamerica.com

JANE DOE
100 EXAMPLE ST
ANYTOWN, GA 30000

Your Advantage Relationship Checking

for December 15, 2026 to January 14, 2027          Account number: 0000 9012 3333

Account summary
Beginning balance on December 15, 2026                         $250.00
Deposits and other additions                                  1,000.00
ATM and debit card subtractions                                 -75.25
Other subtractions                                               -0.00
Checks                                                           -0.00
Service fees                                                     -0.00
Ending balance on January 14, 2027                           $1,174.75

Deposits and other additions
Date        Description                                                    Amount
01/05/27    EXAMPLE EMPLOYER DES:PAYROLL ID:XXXXX00004 INDN:DOE,JANE     1,000.00
Total deposits and other additions                                    $1,000.00

Withdrawals and other subtractions

ATM and debit card subtractions
Date        Description                                                    Amount
12/21/26    CHECKCARD 1219 FOOBAR BOOKS ANYTOWN GA 24000000000000000000002  -30.00
01/02/27    CHECKCARD 1231 ACME COFFEE ANYTOWN GA 24000000000000000000003   -45.25
Total ATM and debit card subtractions                                    -$75.25
Page 1 of 1
```

## Given tests

26 tests in one file. Do not change them.

`tests/unit/test_boa_deposit_parser.py`

```python
from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers import detect_parser, registered_parsers
from finances.ingest.parsers.boa_deposit import BoaDepositParser
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

FIXTURES = Path(__file__).parent.parent / "fixtures" / "statements"
STATEMENTS = ["checking", "savings", "year_end"]
OTHER_BANKS = [
    ("boa", "two_pages"),
    ("boa", "year_end"),
    ("boa", "credit_balance"),
    ("capital_one", "single_card"),
    ("citi", "two_cardholders"),
    ("truist", "checking"),
    ("marcus", "basic"),
]


def pages(name: str, bank: str = "boa_deposit") -> list[str]:
    return (FIXTURES / bank / f"{name}.txt").read_text(encoding="utf-8").split("\f")


def parse(name: str) -> ParsedStatement:
    return BoaDepositParser().parse(pages(name))


def without(name: str, text: str) -> list[str]:
    """The fixture's pages with text taken out wherever it is printed."""
    return [page.replace(text, "") for page in pages(name)]


def test_the_parser_is_registered_once_under_its_name() -> None:
    names = [parser.name for parser in registered_parsers()]
    assert names.count("boa_deposit") == 1
    assert BoaDepositParser.name == "boa_deposit"


@pytest.mark.parametrize("name", STATEMENTS)
def test_detects_its_own_fixtures(name: str) -> None:
    assert BoaDepositParser().detect(pages(name)[0]) is True
    assert detect_parser(pages(name)).name == "boa_deposit"


@pytest.mark.parametrize(("bank", "name"), OTHER_BANKS)
def test_does_not_detect_another_statement(bank: str, name: str) -> None:
    assert BoaDepositParser().detect(pages(name, bank)[0]) is False


@pytest.mark.parametrize("name", STATEMENTS)
def test_every_fixture_reconciles(name: str) -> None:
    result = reconcile(parse(name))
    assert (result.ok, result.difference_cents, result.section_mismatches) == (True, 0, {})


@pytest.mark.parametrize("name", STATEMENTS)
def test_the_page_breaks_do_not_matter(name: str) -> None:
    assert BoaDepositParser().parse(["\n".join(pages(name))]) == parse(name)


def test_checking_header_balances_and_totals() -> None:
    statement = parse("checking")
    assert statement.parser_name == "boa_deposit"
    assert statement.institution == "Bank of America"
    assert statement.account_type is AccountType.CHECKING
    assert statement.account_last4 == "1111"
    assert statement.period_start == date(2026, 9, 1)
    assert statement.period_end == date(2026, 9, 30)
    assert statement.opening_balance_cents == 150000
    assert statement.closing_balance_cents == 258185
    assert statement.declared_section_totals == {
        Section.DEPOSITS: 325025,
        Section.WITHDRAWALS: -180640,
        Section.CHECKS: -35000,
        Section.FEES: -1200,
    }


def test_checking_lines() -> None:
    assert parse("checking").lines == [
        StatementLine(
            date(2026, 9, 2),
            None,
            "EXAMPLE EMPLOYER DES:PAYROLL ID:XXXXX00001 INDN:DOE,JANE",
            300000,
            Section.DEPOSITS,
        ),
        StatementLine(
            date(2026, 9, 15),
            None,
            "Zelle payment from JOHN DOE Conf# x0000001",
            25000,
            Section.DEPOSITS,
        ),
        StatementLine(date(2026, 9, 30), None, "Interest Earned", 25, Section.DEPOSITS),
        StatementLine(
            date(2026, 9, 3),
            date(2026, 9, 2),
            "CHECKCARD 0902 ACME COFFEE ANYTOWN GA 24000000000000000000001",
            -450,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2026, 9, 8),
            date(2026, 9, 6),
            "PURCHASE 0906 FOOBAR GROCERY ANYTOWN GA",
            -8190,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2026, 9, 20),
            None,
            "BKOFAMERICA ATM 09/20 #000001 WITHDRWL ANYTOWN GA",
            -10000,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2026, 9, 5),
            None,
            "EXAMPLE CARD DES:ACH PMT ID:00000000001 INDN:JANE DOE CO",
            -120000,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2026, 9, 18),
            None,
            "Online Banking transfer to SAV 2222 Confirmation# 0000000001",
            -42000,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2026, 9, 10), None, "CHECK 1041", -12500, Section.CHECKS, external_ref="1041"
        ),
        StatementLine(
            date(2026, 9, 14), None, "CHECK 1042", -20000, Section.CHECKS, external_ref="1042"
        ),
        StatementLine(
            date(2026, 9, 25), None, "CHECK 1044", -2500, Section.CHECKS, external_ref="1044"
        ),
        StatementLine(date(2026, 9, 30), None, "Monthly Maintenance Fee", -1200, Section.FEES),
    ]


def test_savings() -> None:
    statement = parse("savings")
    assert statement.account_type is AccountType.SAVINGS
    assert statement.account_last4 == "2222"
    assert (statement.period_start, statement.period_end) == (date(2026, 8, 1), date(2026, 8, 31))
    assert (statement.opening_balance_cents, statement.closing_balance_cents) == (1000000, 992031)
    assert statement.declared_section_totals == {
        Section.DEPOSITS: 42031,
        Section.WITHDRAWALS: -50000,
    }
    assert statement.lines == [
        StatementLine(
            date(2026, 8, 12),
            None,
            "Online Banking transfer from CHK 1111 Confirmation# 0000000002",
            42000,
            Section.DEPOSITS,
        ),
        StatementLine(date(2026, 8, 31), None, "Interest Earned", 31, Section.DEPOSITS),
        StatementLine(
            date(2026, 8, 20),
            None,
            "Online Banking transfer to CHK 1111 Confirmation# 0000000003",
            -50000,
            Section.WITHDRAWALS,
        ),
    ]


def test_year_end() -> None:
    statement = parse("year_end")
    assert statement.account_type is AccountType.CHECKING
    assert statement.account_last4 == "3333"
    assert (statement.period_start, statement.period_end) == (date(2026, 12, 15), date(2027, 1, 14))
    assert (statement.opening_balance_cents, statement.closing_balance_cents) == (25000, 117475)
    assert statement.declared_section_totals == {
        Section.DEPOSITS: 100000,
        Section.WITHDRAWALS: -7525,
    }
    assert statement.lines == [
        StatementLine(
            date(2027, 1, 5),
            None,
            "EXAMPLE EMPLOYER DES:PAYROLL ID:XXXXX00004 INDN:DOE,JANE",
            100000,
            Section.DEPOSITS,
        ),
        StatementLine(
            date(2026, 12, 21),
            date(2026, 12, 19),
            "CHECKCARD 1219 FOOBAR BOOKS ANYTOWN GA 24000000000000000000002",
            -3000,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2027, 1, 2),
            date(2026, 12, 31),
            "CHECKCARD 1231 ACME COFFEE ANYTOWN GA 24000000000000000000003",
            -4525,
            Section.WITHDRAWALS,
        ),
    ]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("Account number:", "boa_deposit: account number not found"),
        ("for August 1, 2026 to August 31, 2026", "boa_deposit: statement period not found"),
        ("Beginning balance on", "boa_deposit: beginning balance not found"),
        ("Ending balance on", "boa_deposit: ending balance not found"),
    ],
)
def test_a_missing_part_is_refused(text: str, message: str) -> None:
    with pytest.raises(StatementError) as error:
        BoaDepositParser().parse(without("savings", text))
    assert str(error.value) == message


def test_an_impossible_row_date_is_refused() -> None:
    broken = [page.replace("08/20/26", "02/30/26") for page in pages("savings")]
    with pytest.raises(StatementError) as error:
        BoaDepositParser().parse(broken)
    assert str(error.value) == "boa_deposit: invalid date"
```

## Tests to write

Each case names the input that decides it; the test must use that input or one that decides the same way.

`tests/unit/test_boa_deposit_parser_more.py`:

- a beginning balance printed `-$25.00` (overdrawn) gives `-2500`;
- a row in `Other subtractions` printed without a minus (a reversal) is positive: the sign is the row's, not the section's;
- a row with amount `0.00` is skipped;
- a period with `September 31` and one with an unknown month name are refused with `boa_deposit: statement period not found`;
- an account-number line with only three digits is refused with `boa_deposit: account number not found`;
- a check line with `*1045` (the star before) reads check `1045`; a check with an impossible date is refused with `boa_deposit: invalid date`;
- `CHECKCARD 1340 …` (no such day) keeps `transaction_date` None; a description with `CHECKCARD` later in the text, not at the start, keeps it None;
- a product line `Your Savings Plus` placed **after** the account-number line does not make a checking statement savings;
- `Total ATM and debit card subtractions` alone (no other subtractions section) gives that total as `WITHDRAWALS`;
- a summary line `Checks  -350.00` does not open the checks section: a dated line right after it is not read as a check.

## Rules for this phase

- Do not open, print, or quote anything under `data/samples/`. Run the real-sample check only as `.venv/bin/python -m pytest tests/real_samples/check_real_samples.py --no-cov -rA`, and report only its pass or fail lines (sample numbers, parser names, counts, cents).
- Earlier tests stay unchanged.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test file above, 26 tests; at least N + 26 passed in all;
- `git diff --stat HEAD -- tests` prints nothing (earlier tests and fixtures unchanged; the new files are untracked);
- the coverage command: `.venv/bin/python -m pytest tests/unit -o addopts="" --import-mode=importlib --cov=finances.ingest.parsers.boa_deposit --cov-branch --cov-report=term-missing --cov-fail-under=100`.

The real-sample check is the owner's to run after verification; report its lines if you ran it.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 37: Bank of America checking and savings (YYYY-MM-DD)`.
