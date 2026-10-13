from datetime import date

import pytest

from finances.ingest.parsers.boa import BoaCardParser
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

BASE = [
    "Bank of America      www.bankofamerica.com",
    "Customized Cash Rewards Visa Signature",
    "Account# 4400 0000 0000 7070",
    "March 29 - April 28, 2026",
    "Previous Balance      $40.00",
    "Payments and Other Credits      -$40.00",
    "Purchases and Adjustments      $12.00",
    "Fees Charged      $0.00",
    "Interest Charged      $0.00",
    "New Balance Total      $12.00",
    "Payments and Other Credits",
    "04/10   04/11   PAYMENT FROM CHK 0042 CONF#Q00000000      5001   7070   -40.00",
    "TOTAL PAYMENTS AND OTHER CREDITS FOR THIS PERIOD      -$40.00",
    "Purchases and Adjustments",
    "04/03   04/04   ACME PRETZELS KIOSK 2026      5002   7070   12.00",
    "TOTAL PURCHASES AND ADJUSTMENTS FOR THIS PERIOD      $12.00",
]
PAYMENT = StatementLine(
    date(2026, 4, 11),
    date(2026, 4, 10),
    "PAYMENT FROM CHK 0042 CONF#Q00000000",
    4000,
    Section.PAYMENTS_CREDITS,
    card_last4="7070",
    external_ref="5001",
)
PRETZELS = StatementLine(
    date(2026, 4, 4),
    date(2026, 4, 3),
    "ACME PRETZELS KIOSK 2026",
    -1200,
    Section.PURCHASES,
    card_last4="7070",
    external_ref="5002",
)


def parse(lines: list[str]) -> ParsedStatement:
    return BoaCardParser().parse(["\n".join(lines)])


def error(pages: list[str]) -> str:
    with pytest.raises(StatementError) as caught:
        BoaCardParser().parse(pages)
    return str(caught.value)


def replaced(old: str, new: str) -> list[str]:
    return [line.replace(old, new) for line in BASE]


def without(*texts: str) -> list[str]:
    lines = BASE
    for text in texts:
        lines = [line.replace(text, "XXXX") for line in lines]
    return lines


def inserted_after(marker: str, extra: str) -> list[str]:
    index = BASE.index(marker)
    return [*BASE[: index + 1], extra, *BASE[index + 1 :]]


def test_a_statement_within_one_year() -> None:
    statement = parse(BASE)
    assert statement.account_last4 == "7070"
    assert (statement.period_start, statement.period_end) == (date(2026, 3, 29), date(2026, 4, 28))
    assert (statement.opening_balance_cents, statement.closing_balance_cents) == (-4000, -1200)
    assert statement.lines == [PAYMENT, PRETZELS]


def test_a_six_part_row_whose_description_ends_in_a_number() -> None:
    assert parse(BASE).lines[1].description == "ACME PRETZELS KIOSK 2026"
    assert parse(BASE).lines[1].external_ref == "5002"


def test_a_statement_across_a_year_end() -> None:
    lines = [
        line.replace("March 29 - April 28, 2026", "December 20 - January 19, 2027")
        .replace("04/03   04/04", "12/30   01/02")
        .replace("04/10   04/11", "01/05   01/05")
        for line in BASE
    ]
    statement = parse(lines)
    assert (statement.period_start, statement.period_end) == (date(2026, 12, 20), date(2027, 1, 19))
    assert [(item.transaction_date, item.posted_date) for item in statement.lines] == [
        (date(2027, 1, 5), date(2027, 1, 5)),
        (date(2026, 12, 30), date(2027, 1, 2)),
    ]


@pytest.mark.parametrize(
    ("missing", "message"),
    [
        ("Account# 4400 0000 0000 7070", "boa: account number not found"),
        ("March 29 - April 28, 2026", "boa: statement period not found"),
        ("Previous Balance", "boa: previous balance not found"),
        ("New Balance Total", "boa: new balance not found"),
    ],
)
def test_each_missing_piece_has_its_own_message(missing: str, message: str) -> None:
    assert error(["\n".join(without(missing))]) == message


@pytest.mark.parametrize(
    ("missing", "message"),
    [
        (("Account# 4400", "March 29"), "boa: account number not found"),
        (("March 29", "Previous Balance"), "boa: statement period not found"),
        (("Previous Balance", "New Balance Total"), "boa: previous balance not found"),
    ],
)
def test_the_first_missing_piece_is_reported(missing: tuple[str, str], message: str) -> None:
    assert error(["\n".join(without(*missing))]) == message


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("March 29 - April 28, 2026", "March 29 - June 31, 2026"),
        ("March 29 - April 28, 2026", "February 30 - April 28, 2026"),
        ("March 29 - April 28, 2026", "Smarch 29 - April 28, 2026"),
        ("March 29 - April 28, 2026", "March 29 - Brumaire 28, 2026"),
    ],
)
def test_a_period_that_is_not_a_real_date_is_not_a_period(old: str, new: str) -> None:
    assert error(["\n".join(replaced(old, new))]) == "boa: statement period not found"


def test_an_account_number_needs_four_groups_of_four_digits() -> None:
    lines = replaced("Account# 4400 0000 0000 7070", "Account# 4400 0000 7070")
    assert error(["\n".join(lines)]) == "boa: account number not found"


def test_a_row_dated_outside_the_period_is_an_error() -> None:
    lines = replaced("04/03   04/04", "09/03   09/04")
    assert error(["\n".join(lines)]) == "date is outside the statement period"


@pytest.mark.parametrize(
    "pages", [[], [""], ["Example Bank\nStatement Period 01/01/2026 to 01/31/2026"]]
)
def test_pages_without_a_statement_raise_a_statement_error(pages: list[str]) -> None:
    assert error(pages) == "boa: account number not found"


def test_a_missing_summary_label_leaves_out_only_its_total() -> None:
    lines = [line for line in BASE if line != "Fees Charged      $0.00"]
    assert parse(lines).declared_section_totals == {
        Section.PAYMENTS_CREDITS: 4000,
        Section.PURCHASES: -1200,
        Section.INTEREST: 0,
    }


def test_no_summary_labels_declare_nothing() -> None:
    lines = [*BASE[:4], "Previous Balance      $1.00", "New Balance Total      $1.00"]
    statement = parse(lines)
    assert statement.declared_section_totals == {}
    assert statement.lines == []


def test_a_row_before_any_section_is_ignored() -> None:
    lines = inserted_after(
        "Account# 4400 0000 0000 7070", "04/01   04/02   ACME STRAY   5009   7070   9.99"
    )
    assert parse(lines).lines == [PAYMENT, PRETZELS]


def test_a_row_after_a_total_line_is_ignored() -> None:
    marker = "TOTAL PAYMENTS AND OTHER CREDITS FOR THIS PERIOD      -$40.00"
    lines = inserted_after(marker, "04/12   04/13   ACME AFTER TOTAL   5010   7070   1.00")
    assert parse(lines).lines == [PAYMENT, PRETZELS]


def test_a_credit_among_the_purchases_is_positive_and_stays_a_purchase() -> None:
    lines = inserted_after(
        "Purchases and Adjustments", "04/05   04/06   ACME RETURN   5003   7070   -3.00"
    )
    assert parse(lines).lines[1] == StatementLine(
        date(2026, 4, 6),
        date(2026, 4, 5),
        "ACME RETURN",
        300,
        Section.PURCHASES,
        card_last4="7070",
        external_ref="5003",
    )


def test_a_four_part_row_in_the_purchases_section() -> None:
    lines = inserted_after(
        "Purchases and Adjustments", "04/07   04/08   FOOBAR KITES 12   1,004.50"
    )
    assert parse(lines).lines[1] == StatementLine(
        date(2026, 4, 8), date(2026, 4, 7), "FOOBAR KITES 12", -100450, Section.PURCHASES
    )


def test_a_row_with_a_zero_amount_is_left_out() -> None:
    lines = inserted_after(
        "Purchases and Adjustments", "04/07   04/08   ACME FREEBIE   5004   7070   0.00"
    )
    assert parse(lines).lines == [PAYMENT, PRETZELS]
