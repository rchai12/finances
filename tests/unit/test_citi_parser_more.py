from datetime import date

import pytest

from finances.ingest.parsers.citi import CitiCardParser
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

HEADER = [
    "Citi      www.citicards.com",
    "Costco Anywhere Visa Card by Citi",
    "Account number ending in: 7070",
    "Billing Period: 03/29/26-04/28/26",
    "Previous balance      $40.00",
    "Payments      -$40.00",
    "Credits      -$0.00",
    "Purchases      +$12.00",
    "Fees      +$0.00",
    "Interest      +$0.00",
    "New balance      $12.00",
    "CARDHOLDER SUMMARY",
]
BASE = [
    *HEADER,
    "KIM ROE      Card ending in 7070      New Charges      $12.00",
    "Payments, Credits and Adjustments",
    "04/10   04/10   ONLINE PAYMENT, THANK YOU      -$40.00",
    "KIM ROE",
    "Standard Purchases",
    "04/03   04/04   ACME PRETZELS      $12.00",
    "Fees Charged",
    "TOTAL FEES FOR THIS PERIOD      $0.00",
]
PAYMENT = StatementLine(
    date(2026, 4, 10),
    date(2026, 4, 10),
    "ONLINE PAYMENT, THANK YOU",
    4000,
    Section.PAYMENTS_CREDITS,
)
PRETZELS = StatementLine(
    date(2026, 4, 4),
    date(2026, 4, 3),
    "ACME PRETZELS",
    -1200,
    Section.PURCHASES,
    card_last4="7070",
    cardholder="KIM ROE",
)


def parse(lines: list[str]) -> ParsedStatement:
    return CitiCardParser().parse(["\n".join(lines)])


def error(pages: list[str]) -> str:
    with pytest.raises(StatementError) as caught:
        CitiCardParser().parse(pages)
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


def test_the_base_statement() -> None:
    statement = parse(BASE)
    assert statement.account_last4 == "7070"
    assert (statement.period_start, statement.period_end) == (date(2026, 3, 29), date(2026, 4, 28))
    assert (statement.opening_balance_cents, statement.closing_balance_cents) == (-4000, -1200)
    assert statement.lines == [PAYMENT, PRETZELS]


@pytest.mark.parametrize(
    ("missing", "message"),
    [
        ("Account number ending in: 7070", "citi: account number not found"),
        ("Billing Period: 03/29/26-04/28/26", "citi: billing period not found"),
        ("Previous balance", "citi: previous balance not found"),
        ("New balance", "citi: new balance not found"),
    ],
)
def test_each_missing_piece_has_its_own_message(missing: str, message: str) -> None:
    assert error(["\n".join(without(missing))]) == message


@pytest.mark.parametrize(
    ("missing", "message"),
    [
        (("Account number", "Billing Period"), "citi: account number not found"),
        (("Billing Period", "Previous balance"), "citi: billing period not found"),
        (("Previous balance", "New balance"), "citi: previous balance not found"),
    ],
)
def test_the_first_missing_piece_is_reported(missing: tuple[str, str], message: str) -> None:
    assert error(["\n".join(without(*missing))]) == message


@pytest.mark.parametrize(
    ("old", "new"),
    [("03/29/26-04/28/26", "02/30/26-04/28/26"), ("03/29/26-04/28/26", "03/29/26-13/01/26")],
)
def test_a_period_with_a_date_that_does_not_exist(old: str, new: str) -> None:
    assert error(["\n".join(replaced(old, new))]) == "citi: billing period not found"


def test_a_row_dated_outside_the_period_is_an_error() -> None:
    lines = replaced("04/03   04/04", "09/03   09/04")
    assert error(["\n".join(lines)]) == "date is outside the statement period"


@pytest.mark.parametrize(
    "pages", [[], [""], ["Example Bank\nStatement Period 01/01/2026 to 01/31/2026"]]
)
def test_pages_without_a_statement_raise_a_statement_error(pages: list[str]) -> None:
    assert error(pages) == "citi: account number not found"


def test_payments_without_credits_declare_no_payments_total() -> None:
    lines = [line for line in BASE if line != "Credits      -$0.00"]
    assert parse(lines).declared_section_totals == {
        Section.PURCHASES: -1200,
        Section.FEES: 0,
        Section.INTEREST: 0,
    }


def test_credits_without_payments_declare_no_payments_total() -> None:
    lines = [line for line in BASE if line != "Payments      -$40.00"]
    assert Section.PAYMENTS_CREDITS not in parse(lines).declared_section_totals


def test_a_missing_summary_label_leaves_out_only_its_total() -> None:
    lines = [line for line in BASE if line != "Fees      +$0.00"]
    assert parse(lines).declared_section_totals == {
        Section.PAYMENTS_CREDITS: 4000,
        Section.PURCHASES: -1200,
        Section.INTEREST: 0,
    }


def test_no_summary_labels_declare_nothing() -> None:
    lines = [*HEADER[:4], "Previous balance      $1.00", "New balance      $1.00"]
    statement = parse(lines)
    assert statement.declared_section_totals == {}
    assert statement.lines == []


def test_a_row_before_any_section_is_ignored() -> None:
    lines = inserted_after("CARDHOLDER SUMMARY", "04/01   04/02   ACME STRAY      $9.99")
    assert parse(lines).lines == [PAYMENT, PRETZELS]


def test_a_row_after_a_total_line_is_ignored() -> None:
    lines = [*BASE, "04/12   04/13   ACME AFTER TOTAL      $1.00"]
    assert parse(lines).lines == [PAYMENT, PRETZELS]


def test_a_credit_among_the_purchases_is_positive_and_stays_a_purchase() -> None:
    lines = inserted_after("Standard Purchases", "04/05   04/06   ACME RETURN      -$3.00")
    assert parse(lines).lines[1] == StatementLine(
        date(2026, 4, 6),
        date(2026, 4, 5),
        "ACME RETURN",
        300,
        Section.PURCHASES,
        card_last4="7070",
        cardholder="KIM ROE",
    )


def test_three_cardholders_with_one_between_them_without_activity() -> None:
    lines = [
        *HEADER,
        "KIM ROE      Card ending in 7070      New Charges      $13.00",
        "PAT NOLAN      Card ending in 7171      New Charges      $0.00",
        "ANNA-LISE  VAN DER   BERG      Card ending in 7272      New Charges      $1,004.00",
        "Payments, Credits and Adjustments",
        "04/10   04/10   ONLINE PAYMENT, THANK YOU      -$40.00",
        "KIM ROE",
        "Standard Purchases",
        "04/03   04/04   ACME PRETZELS      $12.00",
        "        04/06   ACME NO SALE DATE      $1.00",
        "PAT NOLAN",
        "No Activity",
        "ANNA-LISE VAN   DER BERG",
        "Standard Purchases",
        "        04/07   FOOBAR KITES      $1,004.00",
        "Fees Charged",
        "TOTAL FEES FOR THIS PERIOD      $0.00",
    ]
    anna = "ANNA-LISE VAN DER BERG"
    assert parse(lines).lines == [
        PAYMENT,
        PRETZELS,
        StatementLine(
            date(2026, 4, 6),
            None,
            "ACME NO SALE DATE",
            -100,
            Section.PURCHASES,
            card_last4="7070",
            cardholder="KIM ROE",
        ),
        StatementLine(
            date(2026, 4, 7),
            None,
            "FOOBAR KITES",
            -100400,
            Section.PURCHASES,
            card_last4="7272",
            cardholder=anna,
        ),
    ]


def test_fee_and_interest_rows_have_no_cardholder() -> None:
    lines = [
        *BASE[:-1],
        "04/28   04/28   LATE FEE      $29.00",
        "TOTAL FEES FOR THIS PERIOD      $29.00",
        "Interest Charged",
        "04/28   04/28   INTEREST CHARGED TO STANDARD PURCH      $1.10",
        "TOTAL INTEREST FOR THIS PERIOD      $1.10",
    ]
    assert parse(lines).lines[2:] == [
        StatementLine(date(2026, 4, 28), date(2026, 4, 28), "LATE FEE", -2900, Section.FEES),
        StatementLine(
            date(2026, 4, 28),
            date(2026, 4, 28),
            "INTEREST CHARGED TO STANDARD PURCH",
            -110,
            Section.INTEREST,
        ),
    ]
