# Phase 6a: repairs from the first run on real statements

## Goal

The parsers were run on real statements for the first time. Four of eight passed. This phase repairs the three faults behind the other four, so that every statement the owner has imports.

Nobody read a statement to find these faults. An opt-in report (`tests/real_samples/describe_layout.py`) answered yes-or-no and how-many questions about the layout, and each fault below was then reproduced with synthetic data. What the report showed:

| Fault | What happens | Where the repair goes |
|---|---|---|
| A page with no content | Two Capital One statements end with a blank page. `pypdf` raises `KeyError` for such a page in layout mode, so the whole file was refused as `could not read PDF`. Plain mode reads the same page as an empty string. | `pdf_text.py` |
| Very wide gaps | Layout mode pads columns with spaces. One statement came out as 1.09 million characters, of which about 19 thousand are text. Some row patterns take minutes on lines like that. | `pdf_text.py` |
| Uneven spacing inside Truist labels | Layout mode prints some Truist labels with wider gaps between words (`Other  withdrawals,`) and with spaces inside words (`ser vice`), and one date as `12/31/20 26`. The headings and one total were not recognized, and one balance was not found. A balance line can also carry a second, unrelated amount after the balance. | `parsers/truist.py` |

With both repairs to PDF reading applied, the report showed all six statements from the other banks reconciling, the slow one in 0.2 seconds.

## Read first

- `AGENTS.md`: "Running commands", "Privacy rules" (rule 6), "Money and signs"
- `docs/phases/phase-06-deposit-parsers.md`: Part 1, which this phase amends
- `docs/statement-formats.md`: the notes at the top and section 4
- `src/finances/ingest/pdf_text.py`, `src/finances/ingest/parsers/truist.py`, `src/finances/ingest/parsers/helpers.py`
- `tests/unit/test_pdf_text.py`, `tests/unit/test_truist_parser.py`
- `tests/fixtures/statements/truist/spaced_labels.txt` and `shared_balance_line.txt`: two new synthetic fixtures, already in the repository

## Starting state

- `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `1038` when Phase 6 is the last phase built. This phase does not depend on Phase 17a and can be built before or after it.
- `extract_pages` reads every page in layout mode, and one page that fails makes the whole file `could not read PDF`.
- One existing test, `test_layout_mode_keeps_wide_gaps_between_columns` in `tests/unit/test_pdf_text.py`, was changed by the architect to ask for at least two spaces between columns where it asked for at least five. It passes before and after this phase.
- With today's parser, `spaced_labels.txt` gives no lines and does not reconcile, and `shared_balance_line.txt` raises `truist: previous balance not found`. These are the two real failures, reproduced.
- `finances.ingest` is at 100% line and branch coverage.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/ingest/pdf_text.py` | `extract_pages` reads a failing page in plain mode and narrows wide gaps |
| `src/finances/ingest/parsers/truist.py` | labels are matched with spaces ignored; the balance is the first money after its date |
| `tests/unit/test_pdf_text_repairs.py`, `tests/unit/test_truist_parser_spacing.py` | given, do not change |
| `docs/progress.md` | one new entry |

You may add private helpers to both modules. `extract_pages` and `TruistDepositParser` stay the only public names. Do not change any other production file, any fixture, any existing test, or anything under `tests/real_samples/`.

## Out of scope

- The other four parsers and `helpers.py`. They pass on real statements once PDF reading is repaired. Do not "harden" their patterns.
- Rewriting row patterns for speed. The narrowed gaps remove the cause.
- Rotated text, which `pypdf` leaves out in layout mode. The statements reconcile without it.
- The rows of the Truist `Checks` section. No real statement with checks has been seen yet; the Phase 6 rule stays.
- New dependencies, and a different PDF library.
- Reading anything under `data/`. Only the two opt-in tools in `tests/real_samples/` do that.

## Design

No signature changes.

```python
def extract_pages(content: bytes) -> list[str]: ...
```

Two terms are used for the Truist rules.

- Two texts are **equal with spaces ignored** when they are equal after every whitespace character is removed from both. `Deposits, cr edits and  interest` equals `Deposits, credits and interest` with spaces ignored.
- A label is found **loosely** where its characters, without its spaces, appear in order with any amount of whitespace, or none, between any two of them.

### What the real layout looks like

This is `tests/fixtures/statements/truist/spaced_labels.txt`, a synthetic statement with the spacing faults of the real one. Its third page is blank. Gaps are already two spaces wide, as `extract_pages` will deliver them.

```
T r u  i s  t .c  o  m
Truist Bank, Member FDIC  Your account statement
For 03/11/2027
TRUIST ONE CHECKING - LEVEL 1 1000000004444

Account summary
Your previous balance as of 02/10/2027  $1,800.00
Checks  - 0.00
Other withdr awals, debits and service charges  - 1,252.11
Deposits, credits and interest  + 2,145.00
Your new balance as of 03/11/2027  = $2,692.89

Other  withdrawals, debits and  service charges
DATE  DESCRIPTION  AMOUNT($)
02/12  DEBIT CARD PURCHASE ACME GROCERY 02-11 DECATUR GA 2979  84.12
02/16  INTERNET PAYMENT TRANSFER EXAMPLE SAVINGS BA 000300000001111  500.00
02/20  DEBIT CARD RECURRING PYMT STREAMCO.COM 02-19 866-555-0100 CA 2979  15.99
continued
PAGE 1 OF 2
----- page break -----
T r u  i s  t .c  o  m
Truist Bank, Member FDIC  Your account statement
For 03/11/2027
TRUIST ONE CHECKING - LEVEL 1 1000000004444

Other withdrawals, debits and service charges (continued)
DATE  DESCRIPTION  AMOUNT($)
03/01  ACH CORP DEBIT PAYMENT EXAMPLE CARD CUSTOMER ID 4400000000009999  640.00
03/09  MAINTENANCE FEE  12.00
Total other withdrawals, debits and ser vice char ges  = $1,252.11

Deposits, cr edits and inter est
DATE  DESCRIPTION  AMOUNT($)
02/26  ACH CORP CREDIT PAYROLL EXAMPLE EMPLOYER INC  2,100.00
03/05  MOBILE DEPOSIT  45.00
Total deposits, credits and interest  = $2,145.00

----- page break -----

----- page break -----
Important: questions about your statement
10/01  Call the number on your card by this date  1.00
```

And `shared_balance_line.txt`, a statement with no activity whose balance line carries a second amount:

```
Truist Bank, Member FDIC  Your account statement
For 03/31/2027
TRUIST ONE SAVINGS 4110000006666

Account summary
Your previous balance as of 12/31/20 26  $8,250.00  Interest paid year to date  $41.07
Checks  - 0.00  Interest earned this statement period  $0.00
Other withdrawals, debits and ser vice charges  - 0.00  Annual percentage yield earned  0.01%
Deposits, cr edits and interest  + 0.00  Interest paid this statement period  $0.00
Your new balance as of 03/31/2027  = $8,250.00

Important: questions about your statement
Total deposit account balances are insured up to the limit
Call the number on your card (continued)
```

## Requirements

### Part 1: reading the PDF

- **R1.** `extract_pages` reads each page in layout mode, as now. When layout mode raises any exception for a page, that page alone is read again in plain mode, which is `page.extract_text()` with no arguments. The other pages are still read in layout mode. Plain mode is not called for a page that layout mode read.
- **R2.** A mode that returns `None` gives an empty string for that page.
- **R3.** When plain mode raises too, `extract_pages` raises `StatementError("could not read PDF")`, with no cause attached, exactly as it does today for bytes that are not a PDF. The message never contains text from the library or the page.
- **R4.** In the text of every page, however it was read, each run of three or more space characters becomes exactly two spaces. Nothing else changes: single spaces, pairs of spaces, tab characters, and line breaks stay as they are, and lines are not stripped.
- **R5.** Everything else about `extract_pages` is unchanged: one string per page in order, an empty list for a file with no pages, the two existing messages, the empty user password, and the silenced `pypdf` logger.

### Part 2: the Truist parser

These replace R4, R6, and R7 of Phase 6. Every other requirement of Phase 6 stands: the account line, the rows, the checks, the debit card details, the three messages and their order, and the registration.

- **R6.** A line opens a section when it equals one of the three headings **with spaces ignored**: `Checks`, `Other withdrawals, debits and service charges`, `Deposits, credits and interest`. A line with anything more on it, such as the summary line `Checks  - 475.50` or `Checks paid`, opens nothing.
- **R7.** A line closes the open section when, with its whitespace removed, it starts with `Total`.
- **R8.** A balance is read from the first line that **fits**. A line fits when all of these hold:
  - the label (`Your previous balance as of`, or `Your new balance as of`) is found loosely, at the start of the line or with at least two whitespace characters directly before it;
  - after the label, with optional whitespace between, comes a date: two digits, `/`, two digits, `/`, four digits, with any amount of whitespace allowed between any two of those ten characters;
  - after the date comes at least one whitespace character, and then directly a money token as `find_labeled_amount` defines it: any number of the signs `-`, `+`, `=`, each optionally followed by spaces, then `$`, digits (plain, or grouped in threes with commas), a point, and exactly two digits, not followed by another digit;
  - the date exists, and `parse_amount` accepts the money token.

  The balance is that money token. Whatever follows it on the line, including other amounts, is ignored. A line that does not fit is passed over, and a later line may fit. The dates give the period as in Phase 6: `period_start` is the day after the previous balance's date, `period_end` is the new balance's date.
- **R9.** A declared total is read from the first line that fits, for each of `Total checks`, `Total other withdrawals, debits and service charges`, and `Total deposits, credits and interest`. A line fits when the label is found loosely, at the start of the line or with at least two whitespace characters directly before it, followed by at least one whitespace character and then directly a money token that `parse_amount` accepts. Signs and sections are as in Phase 6. A label with no fitting line gives no entry.
- **R10.** Every statement that parsed before this phase parses to the same result. All existing tests pass without being edited.

## Given tests

Create these two files exactly as shown and do not change them. If one of their tests fails, the production code is wrong. Together with the existing tests they reach every line and branch of both modules, so this phase has no tests for you to write. If your implementation has a branch they do not reach, the branch is not needed.

`tests/unit/test_pdf_text_repairs.py`

```python
import io
import re

import pypdf
import pytest
from pypdf import PdfReader, PdfWriter

from finances.ingest.pdf_text import extract_pages
from finances.ingest.statement import StatementError


def with_blank_pages(content: bytes, before: int = 0, after: int = 1) -> bytes:
    """Return the PDF with pages that have no content stream at all, as some banks add."""
    writer = PdfWriter()
    for _ in range(before):
        writer.add_blank_page(612, 792)
    for page in PdfReader(io.BytesIO(content)).pages:
        writer.add_page(page)
    for _ in range(after):
        writer.add_blank_page(612, 792)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def test_the_blank_page_is_one_that_layout_mode_cannot_read(make_pdf) -> None:
    content = with_blank_pages(make_pdf([["ACME COFFEE"]]))
    page = PdfReader(io.BytesIO(content)).pages[1]
    with pytest.raises(KeyError):
        page.extract_text(extraction_mode="layout")
    assert page.extract_text() == ""


def test_a_page_without_content_is_an_empty_string(make_pdf) -> None:
    content = with_blank_pages(make_pdf([["ACME COFFEE"], ["FOOBAR GROCERY"]]))
    assert extract_pages(content) == ["ACME COFFEE", "FOOBAR GROCERY", ""]


def test_pages_without_content_anywhere_in_the_file(make_pdf) -> None:
    content = with_blank_pages(make_pdf([["ACME COFFEE"]]), before=2, after=1)
    assert extract_pages(content) == ["", "", "ACME COFFEE", ""]


def test_a_file_of_blank_pages_only(make_pdf) -> None:
    assert extract_pages(with_blank_pages(make_pdf([]), after=2)) == ["", ""]


def test_the_other_pages_are_still_read_in_layout_mode(make_pdf) -> None:
    content = with_blank_pages(make_pdf([["03/04\tACME COFFEE\t4.50", "03/05\tFOOBAR\t12.00"]]))
    assert extract_pages(content)[0] == "03/04  ACME COFFEE  4.50\n03/05  FOOBAR  12.00"


def test_wide_gaps_become_two_spaces(make_pdf) -> None:
    content = make_pdf([["03/04\tACME COFFEE\t4.50", "\tFOOBAR GROCERY", "A B\t\tC"]])
    page = extract_pages(content)[0]
    assert page.split("\n") == ["03/04  ACME COFFEE  4.50", "  FOOBAR GROCERY", "A B  C"]
    assert not re.search(r"[ \t]{3,}", page)


def test_single_spaces_and_line_breaks_are_kept(make_pdf) -> None:
    content = make_pdf([["ACME COFFEE #12 DALLAS TX", "", "FOOBAR"], ["SECOND PAGE"]])
    pages = extract_pages(content)
    assert pages[0].split("\n")[0] == "ACME COFFEE #12 DALLAS TX"
    assert pages[0].split("\n")[-1] == "FOOBAR"
    assert pages[1] == "SECOND PAGE"


@pytest.mark.parametrize("error", [KeyError("/Contents"), RuntimeError("boom"), ValueError("bad")])
def test_any_failure_of_layout_mode_falls_back_to_plain_mode(
    make_pdf, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    calls = []

    def fake(self, *args, **kwargs):
        calls.append(kwargs.get("extraction_mode", "plain"))
        if kwargs.get("extraction_mode") == "layout":
            raise error
        return "PLAIN     TEXT\nOF THE PAGE"

    monkeypatch.setattr(pypdf.PageObject, "extract_text", fake)
    assert extract_pages(make_pdf([["x"], ["y"]])) == ["PLAIN  TEXT\nOF THE PAGE"] * 2
    assert calls == ["layout", "plain", "layout", "plain"]


def test_plain_mode_is_not_used_when_layout_mode_works(
    make_pdf, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def fake(self, *args, **kwargs):
        calls.append(kwargs.get("extraction_mode", "plain"))
        return None

    monkeypatch.setattr(pypdf.PageObject, "extract_text", fake)
    assert extract_pages(make_pdf([["x"]])) == [""]
    assert calls == ["layout"]


def test_a_page_that_neither_mode_can_read_is_an_unreadable_pdf(
    make_pdf, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(self, *args, **kwargs):
        raise KeyError("SECRET TEXT FROM THE PAGE")

    monkeypatch.setattr(pypdf.PageObject, "extract_text", fake)
    with pytest.raises(StatementError) as caught:
        extract_pages(make_pdf([["x"]]))
    assert str(caught.value) == "could not read PDF"
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


def test_plain_mode_returning_nothing_is_an_empty_page(
    make_pdf, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(self, *args, **kwargs):
        if kwargs.get("extraction_mode") == "layout":
            raise KeyError("/Contents")
        return None

    monkeypatch.setattr(pypdf.PageObject, "extract_text", fake)
    assert extract_pages(make_pdf([["x"]])) == [""]


def test_a_password_protected_pdf_is_still_refused(make_pdf, encrypt_pdf) -> None:
    content = encrypt_pdf(with_blank_pages(make_pdf([["ACME COFFEE"]])), "secret-pass")
    with pytest.raises(StatementError) as caught:
        extract_pages(content)
    assert str(caught.value) == "PDF is password protected"


def test_runs_of_three_or_more_spaces_and_nothing_else(
    make_pdf, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(self, *args, **kwargs):
        return "A B  C   D    E" + " " * 5000 + "F\n\n\n   G\n \n  H   "

    monkeypatch.setattr(pypdf.PageObject, "extract_text", fake)
    assert extract_pages(make_pdf([["x"]])) == ["A B  C  D  E  F\n\n\n  G\n \n  H  "]
```

`tests/unit/test_truist_parser_spacing.py`

```python
from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers import detect_parser
from finances.ingest.parsers.truist import TruistDepositParser
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

FIXTURES = Path(__file__).parent.parent / "fixtures" / "statements" / "truist"
WITHDRAWALS = "Other withdrawals, debits and service charges"
DEPOSITS = "Deposits, credits and interest"


def text_of(name: str) -> str:
    return (FIXTURES / f"{name}.txt").read_text(encoding="utf-8")


def parse_text(text: str) -> ParsedStatement:
    return TruistDepositParser().parse(text.split("\f"))


def parse(name: str) -> ParsedStatement:
    return parse_text(text_of(name))


def edited(name: str, old: str, new: str, count: int = 1) -> ParsedStatement:
    text = text_of(name)
    assert text.count(old) == count, text.count(old)
    return parse_text(text.replace(old, new))


def spread(text: str, step: int) -> str:
    """Return text with a space put in after every step-th character that is not a space."""
    out = []
    seen = 0
    for character in text:
        out.append(character)
        if not character.isspace():
            seen += 1
            if seen % step == 0:
                out.append(" ")
    return "".join(out).strip()


def test_spaced_labels_header_balances_and_totals() -> None:
    statement = parse("spaced_labels")
    assert detect_parser(text_of("spaced_labels").split("\f")).name == "truist_deposit"
    assert statement.account_type is AccountType.CHECKING
    assert statement.account_last4 == "4444"
    assert statement.period_start == date(2027, 2, 11)
    assert statement.period_end == date(2027, 3, 11)
    assert statement.opening_balance_cents == 180000
    assert statement.closing_balance_cents == 269289
    assert statement.declared_section_totals == {
        Section.WITHDRAWALS: -125211,
        Section.DEPOSITS: 214500,
    }
    assert reconcile(statement).ok is True


def test_spaced_labels_lines() -> None:
    assert parse("spaced_labels").lines == [
        StatementLine(
            date(2027, 2, 12),
            date(2027, 2, 11),
            "DEBIT CARD PURCHASE ACME GROCERY 02-11 DECATUR GA 2979",
            -8412,
            Section.WITHDRAWALS,
            card_last4="2979",
        ),
        StatementLine(
            date(2027, 2, 16),
            None,
            "INTERNET PAYMENT TRANSFER EXAMPLE SAVINGS BA 000300000001111",
            -50000,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2027, 2, 20),
            date(2027, 2, 19),
            "DEBIT CARD RECURRING PYMT STREAMCO.COM 02-19 866-555-0100 CA 2979",
            -1599,
            Section.WITHDRAWALS,
            card_last4="2979",
        ),
        StatementLine(
            date(2027, 3, 1),
            None,
            "ACH CORP DEBIT PAYMENT EXAMPLE CARD CUSTOMER ID 4400000000009999",
            -64000,
            Section.WITHDRAWALS,
        ),
        StatementLine(date(2027, 3, 9), None, "MAINTENANCE FEE", -1200, Section.WITHDRAWALS),
        StatementLine(
            date(2027, 2, 26),
            None,
            "ACH CORP CREDIT PAYROLL EXAMPLE EMPLOYER INC",
            210000,
            Section.DEPOSITS,
        ),
        StatementLine(date(2027, 3, 5), None, "MOBILE DEPOSIT", 4500, Section.DEPOSITS),
    ]


def test_spaced_labels_has_a_blank_page_and_page_breaks_do_not_matter() -> None:
    pages = text_of("spaced_labels").split("\f")
    assert len(pages) == 4
    assert pages[2] == ""
    assert TruistDepositParser().parse(["\n".join(pages)]) == parse("spaced_labels")


def test_a_balance_line_shared_with_other_money() -> None:
    statement = parse("shared_balance_line")
    assert statement.account_type is AccountType.SAVINGS
    assert statement.account_last4 == "6666"
    assert statement.period_start == date(2027, 1, 1)
    assert statement.period_end == date(2027, 3, 31)
    assert statement.opening_balance_cents == 825000
    assert statement.closing_balance_cents == 825000
    assert statement.lines == []
    assert statement.declared_section_totals == {}
    assert reconcile(statement).ok is True


@pytest.mark.parametrize("step", [1, 2, 3, 5, 7])
@pytest.mark.parametrize(
    "label",
    [
        "Checks",
        WITHDRAWALS,
        DEPOSITS,
        "Total checks",
        "Total other withdrawals, debits and service charges",
        "Total deposits, credits and interest",
        "Your previous balance as of 08/12/2026",
        "Your new balance as of 09/11/2026",
    ],
)
def test_spaces_inside_a_label_change_nothing(label: str, step: int) -> None:
    text = text_of("checking")
    lines = text.split("\n")
    changed = 0
    for index, line in enumerate(lines):
        if line.startswith(label) and (
            line == label or not label.startswith(("Checks", "Other", "Dep"))
        ):
            lines[index] = spread(label, step) + line[len(label) :]
            changed += 1
    assert changed == 1
    assert parse_text("\n".join(lines)) == parse("checking")


@pytest.mark.parametrize(
    ("label", "printed"),
    [
        ("Checks", "  Checks  "),
        ("Checks", "\tChecks"),
        (WITHDRAWALS, "Other  withdrawals,  debits  and  service  charges"),
        (WITHDRAWALS, "Other withdrawals, debits and\tservice charges"),
        (DEPOSITS, "Deposits,  credits and  interest"),
    ],
)
def test_wider_gaps_between_the_words_of_a_heading_change_nothing(label: str, printed: str) -> None:
    text = text_of("checking")
    assert text.count(f"\n{label}\nDATE") == 1
    assert parse_text(text.replace(f"\n{label}\nDATE", f"\n{printed}\nDATE")) == parse("checking")


@pytest.mark.parametrize(
    "heading",
    [
        "Checks paid",
        "Checks  - 475.50",
        "Checks and other withdrawals",
        "Other withdrawals, debits and service charges this period",
        "All deposits, credits and interest",
        "Deposits, credits and interest  + 13,405.75",
    ],
)
def test_a_line_with_more_than_the_heading_opens_no_section(heading: str) -> None:
    text = text_of("year_end").replace(f"\n{WITHDRAWALS}\nDATE", f"\n{heading}\nDATE")
    statement = parse_text(text)
    assert [line.section for line in statement.lines] == [Section.DEPOSITS, Section.DEPOSITS]


@pytest.mark.parametrize(
    "total", ["Total", "T otal", "Total:", "Totals for this period", "Totalother"]
)
def test_any_line_that_starts_with_total_closes_the_section(total: str) -> None:
    old = "Total other withdrawals, debits and service charges     = $125.99"
    statement = edited("year_end", old, f"{total}\n01/05   ACME STRAY ROW     9.99")
    assert len(statement.lines) == 4
    assert Section.WITHDRAWALS not in statement.declared_section_totals


def test_a_total_whose_label_is_inside_other_text_is_not_declared() -> None:
    old = "Total other withdrawals, debits and service charges     = $125.99"
    statement = edited("year_end", old, f"Sub{old}")
    assert Section.WITHDRAWALS not in statement.declared_section_totals
    statement = edited("year_end", old, f"x  {old}")
    assert statement.declared_section_totals[Section.WITHDRAWALS] == -12599


@pytest.mark.parametrize(
    ("after_label", "expected"),
    [
        ("12/11/2026  $500.00", 50000),
        ("12/11/2026 $500.00", 50000),
        ("1 2 / 1 1 / 2 0 2 6   $500.00", 50000),
        ("12/11/20 26  $500.00  Interest paid year to date  $41.07", 50000),
        ("12/11/2026  -$500.00", -50000),
        ("12/11/2026  - $500.00", -50000),
        ("12/11/2026  = $500.00", 50000),
    ],
)
def test_the_previous_balance_is_the_first_money_after_the_date(
    after_label: str, expected: int
) -> None:
    old = "Your previous balance as of 12/11/2026                    $500.00"
    statement = edited("year_end", old, f"Your previous balance as of {after_label}")
    assert statement.opening_balance_cents == expected
    assert statement.period_start == date(2026, 12, 12)


@pytest.mark.parametrize(
    "line",
    [
        "Your previous balance as of 12/11/2026",
        "Your previous balance as of 12/11/2026  500.00",
        "Your previous balance as of 12/11/2026 was  $500.00",
        "Your previous balance as of 12/11/26  $500.00",
        "Your previous balance as of 2/11/2026  $500.00",
        "Your previous balance as of 12/32/2026  $500.00",
        "Your previous balance as of 12/11/2026$500.00",
        "Your previous balance  $500.00",
        "See Your previous balance as of 12/11/2026  $500.00",
        "Your previous balance as of 12/11/2026  = = $500.00",
    ],
)
def test_lines_that_are_not_a_previous_balance(line: str) -> None:
    old = "Your previous balance as of 12/11/2026                    $500.00"
    with pytest.raises(StatementError) as caught:
        edited("year_end", old, line)
    assert str(caught.value) == "truist: previous balance not found"


def test_a_balance_label_after_two_spaces_is_found() -> None:
    old = "Your new balance as of 01/12/2027                         = $625.05"
    statement = edited("year_end", old, "Summary  Your new balance as of 01/12/2027  = $625.05")
    assert statement.closing_balance_cents == 62505
    assert statement.period_end == date(2027, 1, 12)


def test_a_line_that_does_not_fit_is_passed_over_for_a_later_one() -> None:
    old = "Your previous balance as of 12/11/2026                    $500.00"
    new = "Your previous balance as of 13/45/2026  $1.00\n" + old
    assert edited("year_end", old, new).opening_balance_cents == 50000
    old = "Total deposits, credits and interest                    = $251.04"
    new = "Total deposits, credits and interest  = = $9.00\n" + old
    assert edited("year_end", old, new).declared_section_totals[Section.DEPOSITS] == 25104
```

## Rules for this phase

- **Money is `int` cents**, read with `parse_amount`. No `float`.
- **Constant messages.** This phase adds no message. Nothing from a statement or from `pypdf` goes into an exception, and nothing is logged or printed.
- **ASCII digits.** Patterns use `[0-9]`, not `\d`.
- **Real statements.** Do not open, print, copy, or quote anything under `data/samples/`. The permitted uses are the two commands under "Real statements" below, whose output is limited to sample numbers, parser names, counts, yes-or-no answers, seconds, and differences in cents (`AGENTS.md` privacy rule 6).
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, at least N + 95 passed, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_pdf_text_repairs.py tests/unit/test_truist_parser_spacing.py --no-cov` | exactly `95 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| the search below | no output |
| `git diff HEAD --stat -- tests/fixtures tests/real_samples tests/conftest.py tests/unit/test_pdf_text.py tests/unit/test_truist_parser.py tests/unit/test_truist_parser_more.py src/finances/ingest/parsers/helpers.py src/finances/ingest/parsers/boa.py src/finances/ingest/parsers/citi.py src/finances/ingest/parsers/capital_one.py src/finances/ingest/parsers/marcus.py` | no output |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.ingest --cov-branch --cov-report=term-missing --cov-fail-under=100`

`git grep -n --untracked -F -e "strptime" -e "float" -e "print(" -e "\d" -- src/finances/ingest/parsers/truist.py src/finances/ingest/pdf_text.py`

### Real statements

Then run the check on real statements, if this machine has them:

`.venv/bin/python -m pytest tests/real_samples/check_real_samples.py --no-cov -rA`

- If it reports `no PDF files in data/samples`, say so in your report. That is not a failure of this phase.
- If it runs, every sample should pass, none should show as `xfail`, and the whole run should take seconds, not minutes. Report the counts on its last line and the time.
- If a sample fails, report the summary line the check printed and nothing else. Then run the layout report and include its lines for that sample in your report:

  `.venv/bin/python tests/real_samples/describe_layout.py`

  Do not open the PDF or print its text. If the cause is not visible from the report and the synthetic layouts, stop and say so.

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 6a: repairs from the first run on real statements (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N, the final passed count, and the outcome of the real-statement check as counts and seconds only. Under "Deviations", list your design choices (private helpers, how labels are matched) and anything you did that the spec did not ask for, or `None`. Under "Follow-ups", write that the Truist `Checks` rows are still unconfirmed.

In your final message, give the output line of each acceptance command.
