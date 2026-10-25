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
