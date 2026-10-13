from datetime import date

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers.truist import TruistDepositParser
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

HEAD = [
    "Truist Bank, Member FDIC      Your account statement",
    "TRUIST SIMPLE SAVINGS 4100000005555",
]
PREVIOUS = "Your previous balance as of 03/31/2026      $100.00"
NEW = "Your new balance as of 04/30/2026      = $90.00"


def parse(*body: str, head: list[str] | None = None) -> ParsedStatement:
    lines = HEAD if head is None else head
    return TruistDepositParser().parse(["\n".join([*lines, PREVIOUS, NEW, *body])])


def failure(lines: list[str]) -> str:
    with pytest.raises(StatementError) as caught:
        TruistDepositParser().parse(["\n".join(lines)])
    return str(caught.value)


def test_header_fields_of_a_minimal_statement() -> None:
    statement = parse()
    assert statement.account_type is AccountType.SAVINGS
    assert statement.account_last4 == "5555"
    assert statement.period_start == date(2026, 4, 1)
    assert statement.period_end == date(2026, 4, 30)
    assert statement.opening_balance_cents == 10000
    assert statement.closing_balance_cents == 9000
    assert statement.lines == []
    assert statement.declared_section_totals == {}


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        ([PREVIOUS, NEW], "truist: account line not found"),
        ([*HEAD, NEW], "truist: previous balance not found"),
        ([*HEAD, PREVIOUS], "truist: new balance not found"),
        ([PREVIOUS], "truist: account line not found"),
        ([HEAD[1]], "truist: previous balance not found"),
        ([], "truist: account line not found"),
    ],
)
def test_each_message_and_which_is_reported_first(lines: list[str], message: str) -> None:
    assert failure(lines) == message


@pytest.mark.parametrize(
    "line",
    [
        "Your previous balance as of 08/32/2026      $100.00",
        "Your previous balance as of 03/31/2026      100.00",
        "Your previous balance as of 03/31/26      $100.00",
    ],
)
def test_a_previous_balance_line_that_does_not_fit_is_passed_over(line: str) -> None:
    assert failure([*HEAD, line, NEW]) == "truist: previous balance not found"
    assert parse(head=[*HEAD, line]).opening_balance_cents == 10000


@pytest.mark.parametrize(
    "line",
    [
        "Your new balance as of 02/30/2026      = $90.00",
        "Your new balance as of 04/30/2026      = 90.00",
    ],
)
def test_a_new_balance_line_that_does_not_fit_is_passed_over(line: str) -> None:
    assert failure([*HEAD, PREVIOUS, line]) == "truist: new balance not found"


def test_a_previous_balance_on_the_last_possible_day_has_no_period_start() -> None:
    lines = [*HEAD, "Your previous balance as of 12/31/9999   $1.00", NEW]
    assert failure(lines) == "truist: previous balance not found"


@pytest.mark.parametrize(
    "line",
    [
        "TRUIST SIMPLE SAVINGS 410",
        "TRUIST SIMPLE SAVINGS4100000005555",
        "Truist Simple Savings 4100000005555",
        "TRUIST MONEY MARKET 4100000005555",
        "TRUIST SIMPLE SAVINGS 4100000005555 PAGE 1",
    ],
)
def test_a_line_that_is_not_an_account_line(line: str) -> None:
    lines = ["Truist Bank, Member FDIC      Your account statement", line, PREVIOUS, NEW]
    assert failure(lines) == "truist: account line not found"


def test_the_first_word_decides_the_type_and_the_whole_number_gives_last4() -> None:
    statement = parse(head=["TRUIST SAVINGS FOR CHECKING CLIENTS   9876543210"])
    assert statement.account_type is AccountType.SAVINGS
    assert statement.account_last4 == "3210"
    statement = parse(head=["CHECKING AND SAVINGS 1234"])
    assert statement.account_type is AccountType.CHECKING
    assert statement.account_last4 == "1234"


def test_an_overdrawn_opening_balance_is_negative() -> None:
    lines = [*HEAD, "Your previous balance as of 03/31/2026   -$12.50", NEW]
    statement = TruistDepositParser().parse(["\n".join(lines)])
    assert statement.opening_balance_cents == -1250


def test_a_missing_total_line_leaves_only_that_entry_out() -> None:
    statement = parse(
        "Total checks      = $5.00",
        "Total deposits, credits and interest      = $7.25",
    )
    assert statement.declared_section_totals == {Section.CHECKS: -500, Section.DEPOSITS: 725}


def test_a_summary_line_without_dollar_sign_is_not_a_total() -> None:
    statement = parse("Total checks      - 5.00")
    assert statement.declared_section_totals == {}


def test_a_row_outside_the_period_raises_the_helper_message() -> None:
    with pytest.raises(StatementError) as caught:
        parse("Deposits, credits and interest", "06/15   ACME PAYROLL   10.00")
    assert str(caught.value) == "date is outside the statement period"


def test_a_check_outside_the_period_raises_the_helper_message() -> None:
    with pytest.raises(StatementError) as caught:
        parse("Checks", "06/15   1001   10.00")
    assert str(caught.value) == "date is outside the statement period"


def test_an_empty_list_of_pages_and_unrelated_text() -> None:
    assert failure([]) == "truist: account line not found"
    with pytest.raises(StatementError) as caught:
        TruistDepositParser().parse(["FOOBAR NEWSLETTER\nnothing to see here"])
    assert str(caught.value) == "truist: account line not found"


def test_rows_before_a_section_and_after_a_total_are_ignored() -> None:
    statement = parse(
        "04/02   STRAY ROW BEFORE   3.00",
        "Deposits, credits and interest",
        "04/03   ACME REBATE   4.00",
        "Total deposits, credits and interest      = $4.00",
        "04/04   STRAY ROW AFTER   5.00",
    )
    assert statement.lines == [
        StatementLine(date(2026, 4, 3), None, "ACME REBATE", 400, Section.DEPOSITS)
    ]


def test_lines_inside_a_section_that_are_not_rows_are_ignored() -> None:
    statement = parse(
        "Other withdrawals, debits and service charges",
        "DATE    DESCRIPTION    AMOUNT($)",
        "04/05   NO AMOUNT HERE",
        "04/05   SIGNED AMOUNT   -6.00",
        "04/05   DOLLAR AMOUNT   $6.00",
        "04/06   ACME FEE   6.00",
    )
    assert [line.description for line in statement.lines] == ["ACME FEE"]
    assert statement.lines[0].amount_cents == -600


def test_zero_rows_and_zero_checks_are_left_out() -> None:
    statement = parse(
        "Checks",
        "04/07   1001   0.00      04/08   1002   2.50",
        "Other withdrawals, debits and service charges",
        "04/09   ACME ADJUSTMENT   0.00",
    )
    assert statement.lines == [
        StatementLine(
            date(2026, 4, 8), None, "CHECK 1002", -250, Section.CHECKS, external_ref="1002"
        )
    ]


def test_a_debit_card_row_with_no_month_day_word() -> None:
    statement = parse(
        "Other withdrawals, debits and service charges",
        "04/10   DEBIT CARD PURCHASE ACME COFFEE DALLAS TX 4242   3.75",
    )
    assert statement.lines[0].transaction_date is None
    assert statement.lines[0].card_last4 == "4242"


@pytest.mark.parametrize("word", ["13-45", "02-30", "01-15"])
def test_a_month_day_word_that_does_not_give_a_date(word: str) -> None:
    statement = parse(
        "Other withdrawals, debits and service charges",
        f"04/10   DEBIT CARD PURCHASE ACME COFFEE {word} DALLAS TX 4242   3.75",
    )
    assert statement.lines[0].transaction_date is None
    assert statement.lines[0].card_last4 == "4242"
    assert statement.lines[0].amount_cents == -375


def test_the_last_month_day_word_is_used_and_a_long_last_word_is_no_card() -> None:
    statement = parse(
        "Other withdrawals, debits and service charges",
        "04/12   DEBIT CARD PURCHASE ACME 03-29 SHOP 04-11 DALLAS TX 42420   8.00",
    )
    assert statement.lines[0].transaction_date == date(2026, 4, 11)
    assert statement.lines[0].card_last4 is None


def test_a_debit_card_refund_in_deposits_is_positive_with_card_and_date() -> None:
    statement = parse(
        "Deposits, credits and interest",
        "04/14   DEBIT CARD PURCHASE RETURN FOOBAR OUTLET 04-12 AUSTIN TX 7777   15.75",
    )
    assert statement.lines == [
        StatementLine(
            date(2026, 4, 14),
            date(2026, 4, 12),
            "DEBIT CARD PURCHASE RETURN FOOBAR OUTLET 04-12 AUSTIN TX 7777",
            1575,
            Section.DEPOSITS,
            card_last4="7777",
        )
    ]


def test_a_description_that_only_mentions_debit_card_gets_no_details() -> None:
    statement = parse(
        "Other withdrawals, debits and service charges",
        "04/15   REFUND DEBIT CARD FEE 04-14 4242   1.00",
    )
    assert statement.lines[0].transaction_date is None
    assert statement.lines[0].card_last4 is None


def test_a_statement_with_only_a_checks_section() -> None:
    statement = parse(
        "Checks",
        "DATE     CHECK #     AMOUNT($)",
        "04/02   501   10.00      04/03   *   503   1,234.56",
        "* indicates a skip in sequential check numbers above this item",
        "04/20   *504   0.01",
        "Total checks      = $1,244.57",
    )
    assert statement.lines == [
        StatementLine(
            date(2026, 4, 2), None, "CHECK 501", -1000, Section.CHECKS, external_ref="501"
        ),
        StatementLine(
            date(2026, 4, 3), None, "CHECK 503", -123456, Section.CHECKS, external_ref="503"
        ),
        StatementLine(date(2026, 4, 20), None, "CHECK 504", -1, Section.CHECKS, external_ref="504"),
    ]
    assert statement.declared_section_totals == {Section.CHECKS: -124457}


def test_a_section_heading_with_more_text_does_not_open_a_section() -> None:
    statement = parse(
        "Deposits, credits and interest (continued)",
        "04/03   ACME REBATE   4.00",
    )
    assert statement.lines == []


def test_a_section_stays_open_across_pages() -> None:
    first = "\n".join([*HEAD, PREVIOUS, NEW, "Deposits, credits and interest", "04/03   A   1.00"])
    second = "\n".join(["PAGE 2", "Deposits, credits and interest (continued)", "04/04   B   2.00"])
    statement = TruistDepositParser().parse([first, second])
    assert [line.amount_cents for line in statement.lines] == [100, 200]
