from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers import detect_parser, registered_parsers
from finances.ingest.parsers.truist import TruistDepositParser
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

FIXTURES = Path(__file__).parent.parent / "fixtures" / "statements"
STATEMENTS = ["checking", "savings_no_activity", "year_end"]
OTHER_BANKS = [
    ("capital_one", "single_card"),
    ("capital_one", "multi_card"),
    ("capital_one", "other_bank"),
    ("boa", "two_pages"),
    ("boa", "year_end"),
    ("citi", "two_cardholders"),
    ("citi", "year_end"),
    ("marcus", "basic"),
    ("marcus", "interest_only"),
]


def pages(name: str, bank: str = "truist") -> list[str]:
    return (FIXTURES / bank / f"{name}.txt").read_text(encoding="utf-8").split("\f")


def parse(name: str) -> ParsedStatement:
    return TruistDepositParser().parse(pages(name))


def test_the_parser_is_registered_once_under_its_name() -> None:
    names = [parser.name for parser in registered_parsers()]
    assert names.count("truist_deposit") == 1
    assert TruistDepositParser.name == "truist_deposit"


@pytest.mark.parametrize("name", STATEMENTS)
def test_detects_its_own_fixtures(name: str) -> None:
    assert TruistDepositParser().detect(pages(name)[0]) is True
    assert detect_parser(pages(name)).name == "truist_deposit"


@pytest.mark.parametrize(("bank", "name"), OTHER_BANKS)
def test_does_not_detect_another_banks_statement(bank: str, name: str) -> None:
    assert TruistDepositParser().detect(pages(name, bank)[0]) is False


@pytest.mark.parametrize("name", STATEMENTS)
def test_every_fixture_reconciles(name: str) -> None:
    result = reconcile(parse(name))
    assert result.ok is True
    assert result.difference_cents == 0
    assert result.section_mismatches == {}


@pytest.mark.parametrize("name", STATEMENTS)
def test_parsing_twice_gives_the_same_statement(name: str) -> None:
    assert parse(name) == parse(name)


@pytest.mark.parametrize("name", STATEMENTS)
def test_the_page_breaks_do_not_matter(name: str) -> None:
    joined = ["\n".join(pages(name))]
    assert TruistDepositParser().parse(joined) == parse(name)


def test_checking_header_balances_and_totals() -> None:
    statement = parse("checking")
    assert statement.parser_name == "truist_deposit"
    assert statement.institution == "Truist"
    assert statement.account_type is AccountType.CHECKING
    assert statement.account_last4 == "1111"
    assert statement.period_start == date(2026, 8, 13)
    assert statement.period_end == date(2026, 9, 11)
    assert statement.opening_balance_cents == 255223
    assert statement.closing_balance_cents == 204809
    assert statement.declared_section_totals == {
        Section.CHECKS: -47550,
        Section.WITHDRAWALS: -1343439,
        Section.DEPOSITS: 1340575,
    }
    assert len(statement.lines) == 12


def test_checking_lines() -> None:
    assert parse("checking").lines == [
        StatementLine(
            date(2026, 8, 20), None, "CHECK 1041", -12500, Section.CHECKS, external_ref="1041"
        ),
        StatementLine(
            date(2026, 8, 27), None, "CHECK 1042", -4000, Section.CHECKS, external_ref="1042"
        ),
        StatementLine(
            date(2026, 9, 3), None, "CHECK 1045", -31050, Section.CHECKS, external_ref="1045"
        ),
        StatementLine(
            date(2026, 8, 17),
            date(2026, 8, 15),
            "DEBIT CARD PURCHASE ACME*TERMINAL3 08-15 DALLAS TX 2979",
            -20000,
            Section.WITHDRAWALS,
            card_last4="2979",
        ),
        StatementLine(
            date(2026, 8, 17),
            None,
            "INTERNET PAYMENT TRANSFER EXAMPLE SAVINGS BA 000300000001111",
            -1100000,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2026, 8, 20),
            date(2026, 8, 19),
            "DEBIT CARD RECURRING PYMT STREAMCO.COM 08-19 866-555-0100 CA 2979",
            -999,
            Section.WITHDRAWALS,
            card_last4="2979",
        ),
        StatementLine(
            date(2026, 9, 1),
            None,
            "ACH CORP DEBIT PAYMENT EXAMPLE CARD CUSTOMER ID 4400000000009999",
            -215000,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2026, 9, 4),
            date(2026, 9, 3),
            "DEBIT CARD PURCHASE FOOBAR GROCERY 24-7 09-03 PLANO TX 3141",
            -6240,
            Section.WITHDRAWALS,
            card_last4="3141",
        ),
        StatementLine(date(2026, 9, 10), None, "MAINTENANCE FEE", -1200, Section.WITHDRAWALS),
        StatementLine(
            date(2026, 8, 14),
            None,
            "INCOMING WIRE TRANSFER WIRE REF# 20260814-00000000",
            1300000,
            Section.DEPOSITS,
        ),
        StatementLine(
            date(2026, 8, 28),
            None,
            "ACH CORP CREDIT PAYROLL EXAMPLE EMPLOYER INC",
            39000,
            Section.DEPOSITS,
        ),
        StatementLine(
            date(2026, 9, 8),
            date(2026, 9, 6),
            "DEBIT CARD PURCHASE RETURN ACME OUTLET 09-06 DALLAS TX 2979",
            1575,
            Section.DEPOSITS,
            card_last4="2979",
        ),
    ]


def test_savings_no_activity_header_balances_and_totals() -> None:
    statement = parse("savings_no_activity")
    assert statement.parser_name == "truist_deposit"
    assert statement.institution == "Truist"
    assert statement.account_type is AccountType.SAVINGS
    assert statement.account_last4 == "2222"
    assert statement.period_start == date(2026, 7, 1)
    assert statement.period_end == date(2026, 9, 30)
    assert statement.opening_balance_cents == 1250000
    assert statement.closing_balance_cents == 1250000
    assert statement.declared_section_totals == {}
    assert len(statement.lines) == 0


def test_savings_no_activity_has_no_lines() -> None:
    assert parse("savings_no_activity").lines == []


def test_year_end_header_balances_and_totals() -> None:
    statement = parse("year_end")
    assert statement.parser_name == "truist_deposit"
    assert statement.institution == "Truist"
    assert statement.account_type is AccountType.SAVINGS
    assert statement.account_last4 == "3333"
    assert statement.period_start == date(2026, 12, 12)
    assert statement.period_end == date(2027, 1, 12)
    assert statement.opening_balance_cents == 50000
    assert statement.closing_balance_cents == 62505
    assert statement.declared_section_totals == {
        Section.WITHDRAWALS: -12599,
        Section.DEPOSITS: 25104,
    }
    assert len(statement.lines) == 4


def test_year_end_lines() -> None:
    assert parse("year_end").lines == [
        StatementLine(
            date(2026, 12, 15),
            None,
            "INTERNET PAYMENT TRANSFER TO EXAMPLE CHECKING 1000000001111",
            -10000,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2027, 1, 4),
            date(2026, 12, 30),
            "DEBIT CARD PURCHASE ACME TOYS 12-30 AUSTIN TX 2979",
            -2599,
            Section.WITHDRAWALS,
            card_last4="2979",
        ),
        StatementLine(date(2026, 12, 31), None, "INTEREST PAYMENT", 104, Section.DEPOSITS),
        StatementLine(date(2027, 1, 8), None, "MOBILE DEPOSIT", 25000, Section.DEPOSITS),
    ]


@pytest.mark.parametrize(
    "first_page",
    [
        "",
        "Truist Bank, Member FDIC",
        "Your account statement",
        "TRUIST BANK\nYOUR ACCOUNT STATEMENT",
        "T r u i s t\nYour account statement",
    ],
)
def test_detect_needs_both_markers(first_page: str) -> None:
    assert TruistDepositParser().detect(first_page) is False


def test_detect_with_both_markers() -> None:
    assert TruistDepositParser().detect("Your account statement\nTruist.com") is True


def edited(name: str, old: str, new: str) -> ParsedStatement:
    text = "\f".join(pages(name))
    assert old in text
    return TruistDepositParser().parse(text.replace(old, new).split("\f"))


def test_spaces_inside_a_description_are_collapsed() -> None:
    statement = edited("checking", "MAINTENANCE FEE", "MAINTENANCE     FEE")
    assert statement == parse("checking")


def test_the_last_month_day_token_is_the_purchase_date() -> None:
    statement = edited("checking", "ACME*TERMINAL3 08-15 DALLAS", "ACME 07-04 SALE 08-16 DALLAS")
    line = statement.lines[3]
    assert line.description == "DEBIT CARD PURCHASE ACME 07-04 SALE 08-16 DALLAS TX 2979"
    assert line.transaction_date == date(2026, 8, 16)
    assert line.posted_date == date(2026, 8, 17)


def test_a_purchase_date_that_cannot_be_dated_is_left_out() -> None:
    statement = edited("checking", "ACME*TERMINAL3 08-15 DALLAS", "ACME*TERMINAL3 02-30 DALLAS")
    assert statement.lines[3].transaction_date is None
    assert statement.lines[3].card_last4 == "2979"
    statement = edited("checking", "ACME*TERMINAL3 08-15 DALLAS", "ACME*TERMINAL3 03-15 DALLAS")
    assert statement.lines[3].transaction_date is None


def test_only_debit_card_rows_get_a_card_and_a_purchase_date() -> None:
    statement = edited("checking", "MAINTENANCE FEE", "TRANSFER 09-09 REF 2979")
    line = statement.lines[8]
    assert line.description == "TRANSFER 09-09 REF 2979"
    assert (line.transaction_date, line.card_last4) == (None, None)


def test_a_debit_card_row_that_does_not_end_in_four_digits_has_no_card() -> None:
    statement = edited(
        "checking", "DALLAS TX 2979               200.00", "DALLAS TX 29790              200.00"
    )
    assert statement.lines[3].card_last4 is None
    assert statement.lines[3].transaction_date == date(2026, 8, 15)


def test_a_row_with_a_zero_amount_is_left_out() -> None:
    statement = edited(
        "checking",
        "MAINTENANCE FEE                                                       12.00",
        "MAINTENANCE FEE     0.00",
    )
    assert [item.description for item in statement.lines if "FEE" in item.description] == []
    assert len(statement.lines) == 11


def test_an_overdrawn_balance_is_negative() -> None:
    statement = edited("savings_no_activity", "$12,500.00", "-$12.50")
    assert (statement.opening_balance_cents, statement.closing_balance_cents) == (-1250, -1250)


def test_the_account_type_comes_from_the_account_line() -> None:
    old = "TRUIST ONE SAVINGS 4110000002222"
    statement = edited("savings_no_activity", old, "TRUIST DIMENSION CHECKING - LEVEL 2   90210")
    assert (statement.account_type, statement.account_last4) == (AccountType.CHECKING, "0210")
    statement = edited(
        "savings_no_activity", old, "TRUIST SAVINGS FOR CHECKING CLIENTS 4110000002222"
    )
    assert statement.account_type is AccountType.SAVINGS


@pytest.mark.parametrize(
    "line",
    [
        "TRUIST ONE SAVINGS 411",
        "TRUIST ONE SAVINGS",
        "TRUIST ONE Savings 4110000002222",
        "TRUIST ONE MONEY MARKET 4110000002222",
        "TRUIST ONE SAVINGS4110000002222",
        "TRUIST ONE SAVINGS 4110000002222 (continued)",
    ],
)
def test_lines_that_are_not_an_account_line(line: str) -> None:
    with pytest.raises(StatementError) as caught:
        edited("savings_no_activity", "TRUIST ONE SAVINGS 4110000002222", line)
    assert str(caught.value) == "truist: account line not found"


def test_a_check_with_a_zero_amount_is_left_out() -> None:
    statement = edited("checking", "08/27     1042     40.00", "08/27     1042     0.00")
    assert [item.external_ref for item in statement.lines[:2]] == ["1041", "1045"]
    assert len(statement.lines) == 11


def test_three_checks_on_one_line() -> None:
    old = "08/20     1041     125.00      08/27     1042     40.00"
    new = "08/20  1041  125.00  08/27 *1042 40.00  08/31 * 77 1,000.01"
    statement = edited("checking", old, new)
    found = [
        (item.posted_date, item.external_ref, item.amount_cents) for item in statement.lines[:4]
    ]
    assert found == [
        (date(2026, 8, 20), "1041", -12500),
        (date(2026, 8, 27), "1042", -4000),
        (date(2026, 8, 31), "77", -100001),
        (date(2026, 9, 3), "1045", -31050),
    ]
    assert statement.lines[2].description == "CHECK 77"
