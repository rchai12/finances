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
