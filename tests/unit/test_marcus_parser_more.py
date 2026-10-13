from datetime import date

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers.marcus import MarcusSavingsParser
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

ACCOUNT = "Account Number      300100004444"
PERIOD = "Statement Period      05/01/2026 to 05/31/2026"
BEGINNING = "05/01/2026   Beginning Balance        $100.00"
ENDING = "05/31/2026   Ending Balance        $100.00"
HEAD = [
    "Marcus by Goldman Sachs      ONLINE SAVINGS ACCOUNT STATEMENT",
    "Goldman Sachs Bank USA, Member FDIC",
    PERIOD,
    ACCOUNT,
    BEGINNING,
]


def parse(*rows: str) -> ParsedStatement:
    return MarcusSavingsParser().parse(["\n".join([*HEAD, *rows, ENDING])])


def failure(lines: list[str]) -> str:
    with pytest.raises(StatementError) as caught:
        MarcusSavingsParser().parse(["\n".join(lines)])
    return str(caught.value)


def test_header_fields_of_a_minimal_statement() -> None:
    statement = parse()
    assert statement.parser_name == "marcus_savings"
    assert statement.account_type is AccountType.SAVINGS
    assert statement.account_last4 == "4444"
    assert statement.period_start == date(2026, 5, 1)
    assert statement.period_end == date(2026, 5, 31)
    assert statement.opening_balance_cents == 10000
    assert statement.closing_balance_cents == 10000
    assert statement.lines == []
    assert statement.declared_section_totals == {}


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        ([PERIOD, BEGINNING, ENDING], "marcus: account number not found"),
        ([ACCOUNT, BEGINNING, ENDING], "marcus: statement period not found"),
        ([ACCOUNT, PERIOD, ENDING], "marcus: beginning balance not found"),
        ([ACCOUNT, PERIOD, BEGINNING], "marcus: ending balance not found"),
        ([BEGINNING, ENDING], "marcus: account number not found"),
        ([ACCOUNT, ENDING], "marcus: statement period not found"),
        ([ACCOUNT, PERIOD], "marcus: beginning balance not found"),
    ],
)
def test_each_message_and_the_order_of_missing_pieces(lines: list[str], message: str) -> None:
    assert failure(lines) == message


def test_header_messages_come_before_any_row() -> None:
    lines = [ACCOUNT, PERIOD, BEGINNING, "05/40/2026   ACME   $1.00   $101.00"]
    assert failure(lines) == "marcus: ending balance not found"


@pytest.mark.parametrize(
    "period",
    [
        "Statement Period      02/30/2026 to 05/31/2026",
        "Statement Period      05/01/2026 to 13/31/2026",
    ],
)
def test_a_period_with_a_date_that_does_not_exist(period: str) -> None:
    assert failure([ACCOUNT, period, BEGINNING, ENDING]) == "marcus: statement period not found"


def test_any_whitespace_around_to_in_the_period() -> None:
    lines = [ACCOUNT, "Statement Period   05/01/2026to05/31/2026", BEGINNING, ENDING]
    statement = MarcusSavingsParser().parse(["\n".join(lines)])
    assert statement.period_start == date(2026, 5, 1)
    assert statement.period_end == date(2026, 5, 31)


def test_a_short_account_number_is_not_found() -> None:
    lines = ["Account Number      444", PERIOD, BEGINNING, ENDING]
    assert failure(lines) == "marcus: account number not found"


def test_an_impossible_date_on_a_later_row_after_a_zero_row() -> None:
    lines = [
        *HEAD,
        "05/02/2026   ACME DEPOSIT   $5.00   $105.00",
        "05/03/2026   ACME NOTHING   $0.00   $105.00",
        "05/32/2026   ACME LATE   $1.00   $104.00",
        ENDING,
    ]
    assert failure(lines) == "marcus: row 3 has an impossible date"


def test_a_mismatched_later_row_after_a_zero_row() -> None:
    lines = [
        *HEAD,
        "05/02/2026   ACME DEPOSIT   $5.00   $105.00",
        "05/03/2026   ACME NOTHING   $0.00   $105.00",
        "05/04/2026   ACME WRONG   $2.00   $104.00",
        ENDING,
    ]
    assert failure(lines) == "marcus: row 3 does not match its balance"


def test_empty_pages_and_unrelated_text() -> None:
    assert failure([]) == "marcus: account number not found"
    with pytest.raises(StatementError) as caught:
        MarcusSavingsParser().parse(["FOOBAR NEWSLETTER\nnothing to see here", ""])
    assert str(caught.value) == "marcus: account number not found"


def test_a_balance_below_zero_and_back() -> None:
    statement = parse(
        "05/10/2026   ACME WITHDRAWAL   $105.00   -$5.00",
        "05/11/2026   ACME DEPOSIT   $105.00   $100.00",
    )
    assert statement.lines == [
        StatementLine(date(2026, 5, 10), None, "ACME WITHDRAWAL", -10500, Section.WITHDRAWALS),
        StatementLine(date(2026, 5, 11), None, "ACME DEPOSIT", 10500, Section.DEPOSITS),
    ]


def test_negative_opening_and_closing_balances() -> None:
    lines = [ACCOUNT, PERIOD, "05/01/2026   BeginningBalance   -$5.00"]
    lines += ["05/31/2026   EndingBalance   -$7.25"]
    statement = MarcusSavingsParser().parse(["\n".join(lines)])
    assert statement.opening_balance_cents == -500
    assert statement.closing_balance_cents == -725


def test_a_line_with_one_money_that_is_no_balance_label_is_ignored() -> None:
    statement = parse(
        "05/05/2026   Pending Hold   $9.99",
        "05/06/2026   ACME DEPOSIT   $1.00   $101.00",
        "05/07/2026   Ending Balance Soon   $3.00",
    )
    assert statement.lines == [
        StatementLine(date(2026, 5, 6), None, "ACME DEPOSIT", 100, Section.DEPOSITS)
    ]
    assert statement.closing_balance_cents == 10000


def test_a_one_money_line_before_the_beginning_balance_is_not_the_opening() -> None:
    lines = [ACCOUNT, PERIOD, "05/01/2026   Pending Hold   $9.99", BEGINNING, ENDING]
    statement = MarcusSavingsParser().parse(["\n".join(lines)])
    assert statement.opening_balance_cents == 10000


def test_the_first_balance_line_with_a_label_wins() -> None:
    lines = [*HEAD, "05/15/2026   Beginning Balance   $555.00", ENDING]
    statement = MarcusSavingsParser().parse(["\n".join(lines)])
    assert statement.opening_balance_cents == 10000


def test_two_identical_rows_on_the_same_day_are_both_kept() -> None:
    statement = parse(
        "05/20/2026   ACME TRANSFER   $10.00   $90.00",
        "05/20/2026   ACME TRANSFER   $10.00   $80.00",
    )
    row = StatementLine(date(2026, 5, 20), None, "ACME TRANSFER", -1000, Section.WITHDRAWALS)
    assert statement.lines == [row, row]


def test_interest_paid_with_spaces_is_interest() -> None:
    statement = parse("05/31/2026   Interest   Paid   $0.42   $100.42")
    assert statement.lines == [
        StatementLine(date(2026, 5, 31), None, "Interest Paid", 42, Section.INTEREST)
    ]


def test_masked_digit_lines_and_the_interest_summary_are_ignored() -> None:
    statement = parse(
        "05/02/2026   ACMEDeposit   $1.00   $101.00",
        "****************4444",
        "Interest Paid Year to Date      $123.45      $1,000.00",
    )
    assert len(statement.lines) == 1
