# Phase 4: the Capital One credit card parser

## Goal

Write the first real bank parser. `CapitalOneCardParser` turns the text of a Capital One credit card statement (Quicksilver, Savor, and other cards in the same layout) into a `ParsedStatement`: the account, the billing period, both balances, every transaction with its cardholder, and the interest and fee lines that make the statement add up.

When this phase is done, `import_statement` from Phase 3c imports a Capital One PDF with no further change, because the parser registers itself.

A parser is only trusted because reconciliation checks it. Every rule below exists so that the lines add up to the printed closing balance, to the cent, and a statement that does not add up is refused by the import, not guessed at.

## Read first

- `AGENTS.md`: "Running commands", "Privacy rules" (rule 6 in particular), "Money and signs"
- `docs/statement-formats.md`: the notes at the top and section 1
- `src/finances/ingest/statement.py`, `src/finances/ingest/parsers/__init__.py`, `src/finances/ingest/parsers/helpers.py`, `src/finances/ingest/reconcile.py`
- `tests/fixtures/statements/capital_one/`: five text files, already in the repository
- `tests/conftest.py`

## Starting state

- Phase 3c is committed. `git status --short` prints nothing.
- `.venv/bin/python -m pytest` ends with `590 passed`.
- No parser is registered: `registered_parsers()` returns `[]`.
- `tests/fixtures/statements/capital_one/` holds `single_card.txt`, `multi_card.txt`, `continuation.txt`, `credit_balance.txt`, and `other_bank.txt`. They are synthetic. A form feed character separates the two pages of `single_card.txt`; the others have one page.
- `tests/real_samples/check_real_samples.py` exists. It is not part of the normal test run.
- `finances.ingest` is at 100% line and branch coverage.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/ingest/parsers/capital_one.py` | new: `CapitalOneCardParser` |
| `src/finances/ingest/parsers/__init__.py` | three lines added at the end (given below) |
| `tests/unit/test_capital_one_parser.py`, `tests/integration/test_capital_one_import.py` | given, do not change |
| `tests/unit/test_capital_one_parser_more.py` | new, written by you |
| `docs/progress.md` | one new entry |

You may add private helpers (names starting with `_`) inside `capital_one.py`. `CapitalOneCardParser` is the module's only public name. Do not create any other production module, and do not change any other production file, any fixture, `tests/real_samples/check_real_samples.py`, or any existing test.

## Out of scope

- Parsers for other banks, and any attempt to make this one "generic".
- New shared helpers in `helpers.py`. If a second parser needs one, Phase 5 will move it there.
- Changes to the import service, reconciliation, fingerprints, or PDF text extraction. If you believe one of them has a bug, stop and report it; do not work around it in the parser.
- Merchant clean-up. Descriptions such as `FOOBAR CHICKEN #123TUCKERGA` stay as printed, apart from collapsed whitespace. Phase 11 normalizes them.
- Reading cash advance rows, rewards, the minimum payment table, or year-to-date totals.
- Reading anything under `data/`. Only `check_real_samples.py` does that.
- New dependencies.

## Dependencies

None new.

## Design

```python
class CapitalOneCardParser:
    name = "capital_one_card"

    def detect(self, first_page: str) -> bool: ...
    def parse(self, pages: list[str]) -> ParsedStatement: ...
```

The parser holds no state between calls. `parse` works on the lines of all pages, in order, each with its outer whitespace removed.

Add exactly these lines at the end of `src/finances/ingest/parsers/__init__.py`, after everything that is there. The import is at the bottom because `capital_one.py` imports from this package.

```python
from finances.ingest.parsers.capital_one import CapitalOneCardParser  # noqa: E402

register(CapitalOneCardParser())
```

### The layout

This is the text `pypdf` produces in layout mode. Columns are separated by runs of spaces whose length varies; never rely on an exact number of spaces. The fixtures show complete statements.

```
Capital One                                                  capitalone.com
Quicksilver Credit Card      Visa Signature ending in 1111
Dec 24, 2025 - Jan 23, 2026      31 days in Billing Cycle

Payment Information                              Account Summary
Payment Due Date      Feb 20, 2026              Previous Balance      $250.00
New Balance      $242.58                    Payments      - $250.00
Minimum Payment Due      $25.00            Other Credits      - $15.65
                                                 Transactions      + $258.10
                                                 Cash Advances      + $0.00
                                                 Fees Charged      + $0.00
                                                 Interest Charged      + $0.13
                                                 New Balance      = $242.58

JANE DOE #1111: Payments, Credits and Adjustments
Trans Date      Post Date      Description                                  Amount
Jan 11      Jan 12      CAPITAL ONE MOBILE PYMT                       - $250.00

JANE DOE #1111: Transactions
Trans Date      Post Date      Description                                  Amount
Dec 23      Dec 24      ACME VENDING DallasGrapevineTX                $3.00
Apr 12      Apr 13      EXAMPLE AIR0012345678FORT WORTHTX             $412.60
                      TK#: 0012345678 PSGR: POE/MARIA
JANE DOE #1111: Total Transactions                    $258.10

Total Transactions for This Period                    $258.10
Total Fees for This Period                            $0.00
Interest Charge on Purchases                        $0.13
Interest Charge on Cash Advances                        $0.00
Interest Charge on Other Balances                        $0.00
```

A statement can run over several pages. Later pages repeat the first three lines and say `Transactions (Continued)`. An account can have several cards, each with its own cardholder sections.

## Requirements

### Part 1: recognizing a statement

- **R1.** `detect` returns `True` when the first page contains `Capital One` or `capitalone.com`, and also contains `days in Billing Cycle`. The match is on those exact characters, upper and lower case as written. Otherwise it returns `False`.
- **R2.** Importing `finances.ingest.parsers` registers one `CapitalOneCardParser`, through the three lines under Design.

### Part 2: the header

- **R3.** `account_last4` is the four digits after the first `ending in ` in the statement. It is the account's number, even when a later card section carries different digits.
- **R4.** The period is the first text of the form `Mon D, YYYY - Mon D, YYYY`: a three-letter English month with a capital first letter, a one- or two-digit day, a comma, a four-digit year, twice, joined by ` - `. `period_start` and `period_end` are those two dates. Months are read with the `MONTHS` tuple in `helpers.py`. Do not use `datetime.strptime`: its month names depend on the computer's language setting.
- **R5.** `parser_name` is `"capital_one_card"`, `institution` is `"Capital One"`, and `account_type` is `AccountType.CREDIT_CARD`.

### Part 3: the account summary

A **summary amount** is found by its label. The rule is the same for every label in this part and in Part 5:

- the label is at the start of a line, or has at least two whitespace characters before it;
- after the label comes whitespace, then a money token: any number of the signs `-`, `+`, `=`, each optionally followed by spaces, then `$`, digits with optional commas, a point, and two digits;
- the first line of the statement that fits is used, and the money token is read with `parse_amount`.

The rule keeps `Payments      - $250.00` apart from the heading `JANE DOE #1111: Payments, Credits and Adjustments`, `Transactions      + $258.10` apart from `Total Transactions for This Period`, and `Previous Balance      $250.00` apart from a rewards line such as `Previous Balance      1,234`. A label may share its line with other text, as in the layout above.

- **R6.** `opening_balance_cents` is the negative of the amount labeled `Previous Balance`, and `closing_balance_cents` is the negative of the amount labeled `New Balance`. A card balance is money owed, so `$250.00` becomes `-25000`. A credit balance is printed with a minus (`- $50.00`, or `= - $67.50`) and becomes positive.
- **R7.** `declared_section_totals` has these entries, each present only when its labels are found:

  | Section | Value |
  |---|---|
  | `PAYMENTS_CREDITS` | the negative of (`Payments` plus `Other Credits`); both labels must be found |
  | `FEES` | the negative of `Fees Charged` |
  | `INTEREST` | the negative of `Interest Charged` |
  | `PURCHASES` | the negative of `Total Transactions for This Period` |

  With `Payments      - $250.00` and `Other Credits      - $15.65`, the first entry is `26565`. These totals let reconciliation catch a missed or misread row even when the closing balance happens to come out right.

### Part 4: transaction rows

- **R8.** A **card heading** is a line that starts with a cardholder name, then ` #`, four digits, `: `, and one of `Payments, Credits and Adjustments`, `Transactions`, or `Total Transactions`. The first two open a section (`PAYMENTS_CREDITS` and `PURCHASES`) for that cardholder and card. `Total Transactions` closes the current section. Anything may follow on the line.
- **R9.** The open section stays open across page breaks and across every line that is not a card heading, until the next card heading.
- **R10.** A **row** is a line of this shape, read only while a section is open: a date (`Mon D`), whitespace, a second date, whitespace, the description, whitespace, and at the end of the line an amount that is `$` with digits, optional commas, a point, and two digits, optionally preceded by `- `.
- **R11.** A row becomes a `StatementLine` with:

  | Field | Value |
  |---|---|
  | `transaction_date` | the first date |
  | `posted_date` | the second date |
  | `description` | the description, through `collapse_ws` |
  | `amount_cents` | the negative of `parse_amount` of the amount text: `$3.00` is a purchase and becomes `-300`; `- $250.00` is money back and becomes `25000` |
  | `section` | the open section |
  | `card_last4`, `cardholder` | from the card heading |
  | `external_ref` | `None` |

  Both dates get their year from `parse_month_day` with the statement period, so a December row on a statement that ends in January is dated in the earlier year. The sign comes from the minus alone: a refund printed among the transactions is positive and stays in `PURCHASES`.
- **R12.** Every other line is ignored: column headings, `Transactions (Continued)`, continuation lines under a row (an airline row is followed by lines with a ticket number and a passenger name, which must not reach a description), and rows that appear while no section is open.

### Part 5: interest and fees

These are printed as totals without dates. They become lines dated `period_end`, with no card and no cardholder, so that the statement adds up.

- **R13.** For each of the labels `Interest Charge on Purchases`, `Interest Charge on Cash Advances`, and `Interest Charge on Other Balances`, found at the start of a line and followed by an amount other than zero, add a line with section `INTEREST`, the label in upper case as its description, and the negative of the amount.
- **R14.** When `Total Fees for This Period` is found with an amount other than zero, add a line with section `FEES`, description `TOTAL FEES FOR THIS PERIOD`, and the negative of the amount.
- **R15.** `lines` holds the rows in the order they are printed, then the interest lines in the order they are printed, then the fee line.

### Part 6: what cannot be parsed

- **R16.** A missing piece raises `StatementError` with one of these messages:

  | Missing | Message |
  |---|---|
  | `ending in` with four digits | `capital one: card ending not found` |
  | the period, or a period with a date that does not exist | `capital one: billing period not found` |
  | `Previous Balance` with an amount | `capital one: previous balance not found` |
  | `New Balance` with an amount | `capital one: new balance not found` |

  They are checked in that order. No message contains text from the statement.
- **R17.** A row whose date falls outside the statement period makes `parse_month_day` raise `StatementError`. Let it pass through unchanged: a row the parser cannot date must stop the import.
- **R18.** `parse` raises nothing but `StatementError`, for any list of strings, including an empty list.

## Given tests

Create these two files exactly as shown and do not change them. If one of their tests fails, the parser is wrong.

`tests/unit/test_capital_one_parser.py` checks the parser against the fixtures: every field of every line.

```python
from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers import registered_parsers
from finances.ingest.parsers.capital_one import CapitalOneCardParser
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementLine

FIXTURES = Path(__file__).parent.parent / "fixtures" / "statements" / "capital_one"
STATEMENTS = ["single_card", "multi_card", "continuation", "credit_balance"]
P, C = Section.PURCHASES, Section.PAYMENTS_CREDITS


def pages(name: str) -> list[str]:
    return (FIXTURES / f"{name}.txt").read_text(encoding="utf-8").split("\f")


def parse(name: str) -> ParsedStatement:
    return CapitalOneCardParser().parse(pages(name))


def row(posted, transacted, text, cents, section, card, holder) -> StatementLine:
    return StatementLine(
        posted, transacted, text, cents, section, card_last4=card, cardholder=holder
    )


def jane(posted, transacted, text, cents, section=P) -> StatementLine:
    return row(posted, transacted, text, cents, section, "1111", "JANE DOE")


def test_the_parser_is_registered_once_under_its_name() -> None:
    names = [parser.name for parser in registered_parsers()]
    assert names.count("capital_one_card") == 1
    assert CapitalOneCardParser.name == "capital_one_card"


@pytest.mark.parametrize("name", STATEMENTS)
def test_detects_every_capital_one_fixture(name: str) -> None:
    assert CapitalOneCardParser().detect(pages(name)[0]) is True


@pytest.mark.parametrize(
    "first_page",
    [
        "",
        "Capital One",
        "31 days in Billing Cycle",
        "capital one   31 days in billing cycle",
        "Example Bank   capitalone.com is not our site   30 days in Statement Cycle",
    ],
)
def test_does_not_detect_other_text(first_page: str) -> None:
    assert CapitalOneCardParser().detect(first_page) is False


def test_does_not_detect_another_bank() -> None:
    assert CapitalOneCardParser().detect(pages("other_bank")[0]) is False


@pytest.mark.parametrize(
    "first_page",
    ["Capital One   31 days in Billing Cycle", "see capitalone.com\n28 days in Billing Cycle"],
)
def test_detects_either_brand_text_with_the_billing_cycle_line(first_page: str) -> None:
    assert CapitalOneCardParser().detect(first_page) is True


@pytest.mark.parametrize(
    ("name", "last4", "start", "end", "opening", "closing", "count"),
    [
        ("single_card", "1111", date(2025, 12, 24), date(2026, 1, 23), -25000, -24258, 11),
        ("multi_card", "1111", date(2026, 3, 5), date(2026, 4, 4), -30000, -19674, 8),
        ("continuation", "4444", date(2026, 4, 1), date(2026, 4, 30), 0, -51260, 2),
        ("credit_balance", "5555", date(2026, 5, 1), date(2026, 5, 31), 5000, 6750, 2),
    ],
)
def test_header_and_balances(name, last4, start, end, opening, closing, count) -> None:
    statement = parse(name)
    assert statement.parser_name == "capital_one_card"
    assert statement.institution == "Capital One"
    assert statement.account_type is AccountType.CREDIT_CARD
    assert statement.account_last4 == last4
    assert (statement.period_start, statement.period_end) == (start, end)
    assert statement.opening_balance_cents == opening
    assert statement.closing_balance_cents == closing
    assert len(statement.lines) == count


@pytest.mark.parametrize("name", STATEMENTS)
def test_every_fixture_reconciles(name: str) -> None:
    result = reconcile(parse(name))
    assert result.difference_cents == 0
    assert result.section_mismatches == {}
    assert result.ok is True


@pytest.mark.parametrize(
    ("name", "totals"),
    [
        ("single_card", {C: 26565, Section.FEES: 0, Section.INTEREST: -13, P: -25810}),
        ("multi_card", {C: 32000, Section.FEES: -3500, Section.INTEREST: 0, P: -18174}),
        ("continuation", {C: 0, Section.FEES: 0, Section.INTEREST: 0, P: -51260}),
        ("credit_balance", {C: 3000, Section.FEES: 0, Section.INTEREST: 0, P: -1250}),
    ],
)
def test_declared_section_totals(name: str, totals: dict[Section, int]) -> None:
    assert parse(name).declared_section_totals == totals


def test_single_card_lines_across_two_pages_and_a_year_end() -> None:
    assert parse("single_card").lines == [
        jane(date(2026, 1, 12), date(2026, 1, 11), "CAPITAL ONE MOBILE PYMT", 25000, C),
        jane(date(2026, 1, 16), date(2026, 1, 15), "ACME STORE REFUND", 1565, C),
        jane(date(2025, 12, 24), date(2025, 12, 23), "ACME VENDING DallasGrapevineTX", -300),
        jane(date(2026, 1, 6), date(2026, 1, 5), "FOOBAR CHICKEN #123TUCKERGA", -3896),
        jane(date(2026, 1, 8), date(2026, 1, 7), "ACME COFFEE", -450),
        jane(date(2026, 1, 11), date(2026, 1, 10), "FOOBAR GROCERY #45", -12780),
        jane(date(2026, 1, 15), date(2026, 1, 14), "EXAMPLESTREAM.COM", -1599),
        jane(date(2026, 1, 21), date(2026, 1, 20), "ACME GAS #9", -4125),
        jane(date(2026, 1, 23), date(2026, 1, 22), "FOOBAR BOOKS", -2210),
        jane(date(2026, 1, 23), date(2026, 1, 22), "ACME COFFEE", -450),
        StatementLine(
            date(2026, 1, 23), None, "INTEREST CHARGE ON PURCHASES", -13, Section.INTEREST
        ),
    ]


def test_multi_card_lines_carry_their_cardholder_and_card() -> None:
    assert parse("multi_card").lines == [
        jane(date(2026, 3, 20), date(2026, 3, 20), "CAPITAL ONE AUTOPAY PYMT", 30000, C),
        jane(date(2026, 3, 7), date(2026, 3, 6), "ACME COFFEE", -525),
        jane(date(2026, 4, 1), date(2026, 3, 30), "FOOBAR GROCERY", -8000),
        row(date(2026, 3, 11), date(2026, 3, 10), "ACME HARDWARE", -4510, P, "2222", "JOHN DOE"),
        row(date(2026, 4, 3), date(2026, 4, 2), "FOOBAR DINER", -3140, P, "2222", "JOHN DOE"),
        row(date(2026, 3, 26), date(2026, 3, 25), "ACME STORE RETURN", 2000, C, "3333", "ALEX ROE"),
        row(date(2026, 3, 13), date(2026, 3, 12), "EXAMPLE TOYS", -1999, P, "3333", "ALEX ROE"),
        StatementLine(date(2026, 4, 4), None, "TOTAL FEES FOR THIS PERIOD", -3500, Section.FEES),
    ]


def test_continuation_lines_are_ignored() -> None:
    lines = parse("continuation").lines
    assert lines == [
        row(
            date(2026, 4, 13),
            date(2026, 4, 12),
            "EXAMPLE AIR0012345678FORT WORTHTX",
            -41260,
            P,
            "4444",
            "MARIA POE",
        ),
        row(
            date(2026, 4, 15),
            date(2026, 4, 14),
            "ACME HOTEL SEATTLEWA",
            -10000,
            P,
            "4444",
            "MARIA POE",
        ),
    ]
    text = " ".join(line.description for line in lines)
    assert "PSGR" not in text
    assert "FOLIO" not in text
    assert "CHECK-IN" not in text


def test_a_credit_balance_is_positive_from_the_holder_side() -> None:
    statement = parse("credit_balance")
    assert statement.opening_balance_cents == 5000
    assert statement.closing_balance_cents == 6750
    assert statement.lines == [
        row(
            date(2026, 5, 11), date(2026, 5, 10), "FOOBAR OUTLET REFUND", 3000, C, "5555", "SAM LEE"
        ),
        row(date(2026, 5, 21), date(2026, 5, 20), "ACME SNACKS", -1250, P, "5555", "SAM LEE"),
    ]


@pytest.mark.parametrize("name", STATEMENTS)
def test_parsing_twice_gives_the_same_statement(name: str) -> None:
    parser = CapitalOneCardParser()
    assert parser.parse(pages(name)) == parser.parse(pages(name))
    assert CapitalOneCardParser().parse(pages(name)) == parser.parse(pages(name))


def test_the_page_break_does_not_matter() -> None:
    joined = ["\n".join(pages("single_card"))]
    assert CapitalOneCardParser().parse(joined) == parse("single_card")


def credit_balance_lines() -> list[str]:
    return pages("credit_balance")[0].split("\n")


def parse_lines(lines: list[str]) -> ParsedStatement:
    return CapitalOneCardParser().parse(["\n".join(lines)])


def test_a_row_before_any_card_section_is_ignored() -> None:
    lines = credit_balance_lines()
    lines.insert(3, "May 2      May 3      ACME STRAY ROW                      $9.99")
    assert parse_lines(lines).lines == parse("credit_balance").lines


def test_a_row_after_a_cards_total_line_is_ignored() -> None:
    lines = credit_balance_lines()
    total = next(i for i, line in enumerate(lines) if line.startswith("SAM LEE #5555: Total"))
    lines.insert(total + 1, "May 22      May 23      ACME AFTER TOTAL                    $1.00")
    assert parse_lines(lines).lines == parse("credit_balance").lines


def test_spaces_inside_a_description_are_collapsed() -> None:
    lines = [line.replace("ACME SNACKS", "ACME   SNACKS") for line in credit_balance_lines()]
    assert parse_lines(lines).lines[1].description == "ACME SNACKS"


def test_the_minus_sign_decides_the_sign_not_the_section() -> None:
    lines = credit_balance_lines()
    index = next(i for i, line in enumerate(lines) if "ACME SNACKS" in line)
    lines[index] = lines[index].replace("$12.50", "- $12.50")
    refund = parse_lines(lines).lines[1]
    assert refund.amount_cents == 1250
    assert refund.section is Section.PURCHASES


def test_a_label_followed_by_a_number_that_is_not_money_is_skipped() -> None:
    trap = "Rewards      Previous Balance      9,999      New Balance      8,888"
    statement = parse_lines([trap, *credit_balance_lines()])
    assert statement.opening_balance_cents == 5000
    assert statement.closing_balance_cents == 6750
```

`tests/integration/test_capital_one_import.py` builds a real PDF and imports it through the registry and the import service.

```python
from datetime import date

from sqlalchemy import Engine

from finances.db.engine import session_scope
from finances.db.repositories import (
    create_account,
    latest_balance,
    list_statements,
    list_transactions,
)
from finances.ingest.service import ImportStatus, StatementImportResult, import_statement

FEBRUARY = [
    "Capital One\tcapitalone.com",
    "Quicksilver Credit Card\tVisa Signature ending in 1111",
    "Feb 1, 2026 - Feb 28, 2026\t28 days in Billing Cycle",
    "Previous Balance\t$100.00",
    "Payments\t- $100.00",
    "Other Credits\t- $0.00",
    "Transactions\t+ $42.50",
    "Fees Charged\t+ $0.00",
    "Interest Charged\t+ $0.00",
    "New Balance\t= $42.50",
    "JANE DOE #1111: Payments, Credits and Adjustments",
    "Feb 10  Feb 11\tCAPITAL ONE MOBILE PYMT\t- $100.00",
    "JANE DOE #1111: Transactions",
    "Feb 3  Feb 4\tACME COFFEE\t$4.50",
    "Feb 14  Feb 15\tFOOBAR GROCERY #45\t$38.00",
    "JANE DOE #1111: Total Transactions\t$42.50",
    "Total Transactions for This Period\t$42.50",
]


def test_a_capital_one_pdf_is_imported_through_the_real_registry(
    db_engine: Engine, make_pdf
) -> None:
    content = make_pdf([FEBRUARY])
    with session_scope(db_engine) as session:
        create_account(session, "Test Quicksilver", "Capital One", "credit_card", last4="1111")
        result = import_statement(session, filename="february.pdf", content=content)
    assert result == StatementImportResult(
        filename="february.pdf",
        status=ImportStatus.IMPORTED,
        message="imported",
        parser_name="capital_one_card",
        account_name="Test Quicksilver",
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 28),
        lines_parsed=3,
        inserted=3,
        duplicates=0,
    )
    with session_scope(db_engine) as session:
        rows = sorted(list_transactions(session), key=lambda item: item.id)
        found = [
            (r.posted_date, r.amount_cents, r.description, r.section, r.cardholder) for r in rows
        ]
        assert found == [
            (date(2026, 2, 11), 10000, "CAPITAL ONE MOBILE PYMT", "payments_credits", "JANE DOE"),
            (date(2026, 2, 4), -450, "ACME COFFEE", "purchases", "JANE DOE"),
            (date(2026, 2, 15), -3800, "FOOBAR GROCERY #45", "purchases", "JANE DOE"),
        ]
        assert [r.card_last4 for r in rows] == ["1111", "1111", "1111"]
        statement = list_statements(session)[0]
        assert (statement.opening_balance_cents, statement.closing_balance_cents) == (-10000, -4250)
        assert latest_balance(session, 1).balance_cents == -4250


def test_the_same_capital_one_pdf_is_not_imported_twice(db_engine: Engine, make_pdf) -> None:
    content = make_pdf([FEBRUARY])
    with session_scope(db_engine) as session:
        create_account(session, "Test Quicksilver", "Capital One", "credit_card", last4="1111")
        import_statement(session, filename="february.pdf", content=content)
    with session_scope(db_engine) as session:
        again = import_statement(session, filename="february.pdf", content=content)
        assert again.status is ImportStatus.ALREADY_IMPORTED
        assert len(list_transactions(session)) == 3


def test_a_capital_one_pdf_that_does_not_add_up_is_refused(db_engine: Engine, make_pdf) -> None:
    lines = [line.replace("= $42.50", "= $43.50") for line in FEBRUARY]
    with session_scope(db_engine) as session:
        create_account(session, "Test Quicksilver", "Capital One", "credit_card", last4="1111")
        result = import_statement(session, filename="february.pdf", content=make_pdf([lines]))
        assert result.status is ImportStatus.FAILED
        assert result.message == "statement does not reconcile: off by -100 cents"
        assert list_transactions(session) == []
```

## Tests to write

`tests/unit/test_capital_one_parser_more.py`, with synthetic text only. Build statements as lists of lines in the test, or by editing the lines of a fixture as the given tests do. The given tests cover the fixtures; yours cover what the fixtures do not:

- each message in R16, exactly, including a period with an impossible date such as `Feb 30, 2026`, and the order in which missing pieces are reported when two are missing
- R17: a row dated outside the period, with the helper's message
- R18: an empty list of pages, and a page of unrelated text
- the summary rule in Part 3: a label that shares its line with another label; an amount with two signs (`= - $67.50`); a label that appears first in a line that has no money after it; a statement where `Payments` is present and `Other Credits` is absent, which must leave `PAYMENTS_CREDITS` out of the declared totals
- R13 with interest on cash advances and on other balances, alone and together, and the order of the resulting lines
- R14 and R15 together: a statement with rows, two interest lines, and a fee, in the required order
- R8: `Total Transactions` closing a section, followed by a new card's section
- a cardholder name with several words and a hyphen

Every line of `capital_one.py` must be reached by a test.

## Rules for this phase

- **Money is `int` cents.** Amounts are read with `parse_amount` only. `float` does not appear in `capital_one.py`.
- **Signs are from the account holder's side** (`AGENTS.md`): purchases, fees, and interest negative; payments and refunds positive; a balance owed negative.
- **Constant messages.** The four messages in R16 are the only ones this module creates. Nothing from a statement goes into an exception, and nothing is logged or printed.
- **ASCII digits.** Patterns use `[0-9]`, not `\d`.
- **Synthetic data only** in tests and fixtures: invented names, merchants, and numbers.
- **Real statements.** Do not open, print, copy, or quote anything under `data/samples/`. The only permitted use is running `check_real_samples.py`, whose output is limited to sample numbers, the parser name, counts, and differences in cents (`AGENTS.md` privacy rule 6).
- **No shipped code changes** beyond the three lines in `parsers/__init__.py`.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, at least `632 passed`, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_capital_one_parser.py tests/integration/test_capital_one_import.py --no-cov` | exactly `42 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| the search below | no output |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -F -e "strptime" -e "float" -e "print(" -e "logging" -e "\d" -- src/finances/ingest/parsers/capital_one.py`

### Real statements

Then run the check on real statements, if this machine has them:

`.venv/bin/python -m pytest tests/real_samples/check_real_samples.py --no-cov -rA`

- If it reports `no PDF files in data/samples`, say so in your report. That is not a failure of this phase.
- If it runs, each Capital One sample must pass. A sample from another bank shows as `xfail` with `unrecognized statement format`, which is expected until that bank's parser exists.
- If a Capital One sample fails, report the summary line the check printed (sample number, line count, difference in cents, sections that differ) and nothing else. Then find the cause using the synthetic layout in this spec and in `docs/statement-formats.md`. Do not open the PDF or print its text to find out. If the cause is a layout this spec does not describe, stop and report that: the architect will add a synthetic example of it.

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 4: the Capital One credit card parser (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give the final passed count and the outcome of the real-statement check as counts only (for example "2 passed, 3 xfailed" or "no samples on this machine"). Under "Deviations", list your design choices (private helpers, how the parse is divided) and anything you did that the spec did not ask for, or `None`.

In your final message, give the output line of each acceptance command, and for each of R1 to R18 the name of a test that covers it.
