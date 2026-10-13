from datetime import date

import pytest

from finances.ingest.parsers.capital_one import CapitalOneCardParser
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

HEADER = [
    "Capital One      capitalone.com",
    "Quicksilver Credit Card      Visa Signature ending in 7070",
    "Jun 1, 2026 - Jun 30, 2026      30 days in Billing Cycle",
]
SUMMARY = [
    "Payment Due Date      Jul 25, 2026      Previous Balance      $40.00",
    "New Balance      $12.00      Payments      - $40.00",
    "Other Credits      - $0.00",
    "Transactions      + $12.00",
    "Fees Charged      + $0.00",
    "Interest Charged      + $0.00",
    "New Balance      = $12.00",
]
CARD = [
    "KIM ROE #7070: Payments, Credits and Adjustments",
    "Trans Date      Post Date      Description      Amount",
    "Jun 10      Jun 11      CAPITAL ONE MOBILE PYMT      - $40.00",
    "KIM ROE #7070: Transactions",
    "Trans Date      Post Date      Description      Amount",
    "Jun 3      Jun 4      ACME PRETZELS      $12.00",
    "KIM ROE #7070: Total Transactions      $12.00",
    "Total Transactions for This Period      $12.00",
]
END = date(2026, 6, 30)


def base() -> list[str]:
    return [*HEADER, *SUMMARY, *CARD]


def parse(lines: list[str]) -> ParsedStatement:
    return CapitalOneCardParser().parse(["\n".join(lines)])


def error(pages: list[str]) -> str:
    with pytest.raises(StatementError) as caught:
        CapitalOneCardParser().parse(pages)
    return str(caught.value)


def replaced(old: str, new: str) -> list[str]:
    return [line.replace(old, new) for line in base()]


def without(*texts: str) -> list[str]:
    lines = base()
    for text in texts:
        lines = [line.replace(text, "XXXX") for line in lines]
    return lines


def kim(posted: date, transacted: date, text: str, cents: int, section: Section) -> StatementLine:
    return StatementLine(
        posted, transacted, text, cents, section, card_last4="7070", cardholder="KIM ROE"
    )


BASE_ROWS = [
    kim(
        date(2026, 6, 11),
        date(2026, 6, 10),
        "CAPITAL ONE MOBILE PYMT",
        4000,
        Section.PAYMENTS_CREDITS,
    ),
    kim(date(2026, 6, 4), date(2026, 6, 3), "ACME PRETZELS", -1200, Section.PURCHASES),
]


def test_the_base_statement_parses() -> None:
    statement = parse(base())
    assert statement.account_last4 == "7070"
    assert (statement.period_start, statement.period_end) == (date(2026, 6, 1), END)
    assert (statement.opening_balance_cents, statement.closing_balance_cents) == (-4000, -1200)
    assert statement.lines == BASE_ROWS


@pytest.mark.parametrize(
    ("missing", "message"),
    [
        ("ending in 7070", "capital one: card ending not found"),
        ("Jun 1, 2026 - Jun 30, 2026", "capital one: billing period not found"),
        ("Previous Balance", "capital one: previous balance not found"),
        ("New Balance", "capital one: new balance not found"),
    ],
)
def test_each_missing_piece_has_its_own_message(missing: str, message: str) -> None:
    assert error(["\n".join(without(missing))]) == message


@pytest.mark.parametrize(
    ("old", "new"),
    [("Jun 30, 2026", "Feb 30, 2026"), ("Jun 1, 2026", "Jux 1, 2026")],
)
def test_a_period_with_a_date_that_does_not_exist_is_not_a_period(old: str, new: str) -> None:
    assert error(["\n".join(replaced(old, new))]) == "capital one: billing period not found"


@pytest.mark.parametrize(
    ("missing", "message"),
    [
        (("ending in 7070", "Jun 1, 2026"), "capital one: card ending not found"),
        (("Jun 1, 2026", "Previous Balance"), "capital one: billing period not found"),
        (("Previous Balance", "New Balance"), "capital one: previous balance not found"),
    ],
)
def test_the_first_missing_piece_is_reported(missing: tuple[str, str], message: str) -> None:
    assert error(["\n".join(without(*missing))]) == message


def test_a_row_dated_outside_the_period_is_an_error() -> None:
    lines = replaced("Jun 3      Jun 4", "Sep 3      Sep 4")
    assert error(["\n".join(lines)]) == "date is outside the statement period"


@pytest.mark.parametrize(
    "pages", [[], ["Example Bank\nStatement Period 01/01/2026 to 01/31/2026"], ["", ""]]
)
def test_pages_without_a_statement_raise_a_statement_error(pages: list[str]) -> None:
    assert error(pages) == "capital one: card ending not found"


def test_a_label_may_share_its_line_with_another_label() -> None:
    lines = [*HEADER, "Previous Balance      $40.00      New Balance      = $12.00", *CARD]
    statement = parse(lines)
    assert (statement.opening_balance_cents, statement.closing_balance_cents) == (-4000, -1200)


def test_an_amount_with_two_signs() -> None:
    lines = [*HEADER, "Previous Balance      = - $67.50", "New Balance      + $1.00"]
    statement = parse(lines)
    assert (statement.opening_balance_cents, statement.closing_balance_cents) == (6750, -100)


def test_a_label_first_seen_without_money_is_found_on_a_later_line() -> None:
    lines = ["Previous Balance", "New Balance      see below      $3.00", *base()]
    statement = parse(lines)
    assert (statement.opening_balance_cents, statement.closing_balance_cents) == (-4000, -1200)


def test_a_label_needs_the_start_of_a_line_or_two_spaces_before_it() -> None:
    lines = ["Card Previous Balance      $77.00", "Old New Balance      $66.00", *base()]
    statement = parse(lines)
    assert (statement.opening_balance_cents, statement.closing_balance_cents) == (-4000, -1200)


def test_money_text_that_cannot_be_read_does_not_count() -> None:
    lines = ["Previous Balance      = = $9.00", "New Balance      - - $8.00", *base()]
    statement = parse(lines)
    assert (statement.opening_balance_cents, statement.closing_balance_cents) == (-4000, -1200)


def test_declared_totals_of_the_base_statement() -> None:
    assert parse(base()).declared_section_totals == {
        Section.PAYMENTS_CREDITS: 4000,
        Section.FEES: 0,
        Section.INTEREST: 0,
        Section.PURCHASES: -1200,
    }


def test_payments_without_other_credits_declare_no_payments_total() -> None:
    totals = parse(without("Other Credits")).declared_section_totals
    assert totals == {Section.FEES: 0, Section.INTEREST: 0, Section.PURCHASES: -1200}


def test_other_credits_without_payments_declare_no_payments_total() -> None:
    lines = [line for line in base() if "Payments      -" not in line]
    lines.append("New Balance      $12.00")
    totals = parse(lines).declared_section_totals
    assert Section.PAYMENTS_CREDITS not in totals


def test_no_summary_labels_declare_nothing() -> None:
    lines = [*HEADER, "Previous Balance      $1.00", "New Balance      $1.00"]
    assert parse(lines).declared_section_totals == {}
    assert parse(lines).lines == []


def interest_line(label: str, cents: int) -> StatementLine:
    return StatementLine(END, None, label, cents, Section.INTEREST)


CASH = "INTEREST CHARGE ON CASH ADVANCES"
OTHER = "INTEREST CHARGE ON OTHER BALANCES"
PURCHASES = "INTEREST CHARGE ON PURCHASES"


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        (["Interest Charge on Cash Advances      $1.10"], [interest_line(CASH, -110)]),
        (["Interest Charge on Other Balances      $0.40"], [interest_line(OTHER, -40)]),
        (
            [
                "Interest Charge on Purchases      $0.00",
                "Interest Charge on Other Balances      $0.40",
                "Interest Charge on Cash Advances      $1,001.10",
            ],
            [interest_line(OTHER, -40), interest_line(CASH, -100110)],
        ),
        (
            [
                "Interest Charge on Cash Advances      $0.00",
                "See  Interest Charge on Purchases      $2.00",
            ],
            [],
        ),
    ],
)
def test_interest_lines(printed: list[str], expected: list[StatementLine]) -> None:
    assert parse([*base(), *printed]).lines == [*BASE_ROWS, *expected]


def test_rows_then_interest_then_the_fee() -> None:
    printed = [
        "Fees",
        "Total Fees for This Period      $39.00",
        "Interest Charged",
        "Interest Charge on Purchases      $2.25",
        "Interest Charge on Cash Advances      $0.75",
        "Interest Charge on Other Balances      $0.00",
        "Total Interest for This Period      $3.00",
    ]
    assert parse([*base(), *printed]).lines == [
        *BASE_ROWS,
        interest_line(PURCHASES, -225),
        interest_line(CASH, -75),
        StatementLine(END, None, "TOTAL FEES FOR THIS PERIOD", -3900, Section.FEES),
    ]


def test_a_zero_fee_total_adds_no_line() -> None:
    assert parse([*base(), "Total Fees for This Period      $0.00"]).lines == BASE_ROWS


def test_a_total_line_closes_the_section_and_the_next_card_opens_its_own() -> None:
    second = [
        "Jun 20      Jun 21      ACME BETWEEN CARDS      $1.00",
        "ANNA-LISE VAN DER BERG #8181: Transactions",
        "Jun 22      Jun 23      FOOBAR KITES      $8.00",
        "ANNA-LISE VAN DER BERG #8181: Payments, Credits and Adjustments",
        "Jun 24      Jun 25      FOOBAR KITES RETURN      - $8.00",
        "ANNA-LISE VAN DER BERG #8181: Total Transactions      $8.00",
        "Jun 26      Jun 27      ACME AFTER THE LAST CARD      $1.00",
    ]
    statement = parse([*base(), *second])
    holder = "ANNA-LISE VAN DER BERG"
    assert statement.account_last4 == "7070"
    assert statement.lines == [
        *BASE_ROWS,
        StatementLine(
            date(2026, 6, 23),
            date(2026, 6, 22),
            "FOOBAR KITES",
            -800,
            Section.PURCHASES,
            card_last4="8181",
            cardholder=holder,
        ),
        StatementLine(
            date(2026, 6, 25),
            date(2026, 6, 24),
            "FOOBAR KITES RETURN",
            800,
            Section.PAYMENTS_CREDITS,
            card_last4="8181",
            cardholder=holder,
        ),
    ]
