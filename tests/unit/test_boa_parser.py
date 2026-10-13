from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers import detect_parser, registered_parsers
from finances.ingest.parsers.boa import BoaCardParser
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementLine

FIXTURES = Path(__file__).parent.parent / "fixtures" / "statements"
STATEMENTS = ["two_pages", "year_end", "credit_balance"]
OTHER_BANKS = [
    ("capital_one", "single_card"),
    ("capital_one", "multi_card"),
    ("capital_one", "other_bank"),
    ("citi", "two_cardholders"),
    ("citi", "year_end"),
]


def pages(name: str, bank: str = "boa") -> list[str]:
    return (FIXTURES / bank / f"{name}.txt").read_text(encoding="utf-8").split("\f")


def parse(name: str) -> ParsedStatement:
    return BoaCardParser().parse(pages(name))


def test_the_parser_is_registered_once_under_its_name() -> None:
    names = [parser.name for parser in registered_parsers()]
    assert names.count("boa_card") == 1
    assert BoaCardParser.name == "boa_card"


@pytest.mark.parametrize("name", STATEMENTS)
def test_detects_its_own_fixtures(name: str) -> None:
    assert BoaCardParser().detect(pages(name)[0]) is True
    assert detect_parser(pages(name)).name == "boa_card"


@pytest.mark.parametrize(("bank", "name"), OTHER_BANKS)
def test_does_not_detect_another_banks_statement(bank: str, name: str) -> None:
    assert BoaCardParser().detect(pages(name, bank)[0]) is False


@pytest.mark.parametrize("name", STATEMENTS)
def test_every_fixture_reconciles(name: str) -> None:
    result = reconcile(parse(name))
    assert result.difference_cents == 0
    assert result.section_mismatches == {}
    assert result.ok is True


@pytest.mark.parametrize("name", STATEMENTS)
def test_parsing_twice_gives_the_same_statement(name: str) -> None:
    assert parse(name) == parse(name)


@pytest.mark.parametrize("name", STATEMENTS)
def test_the_page_breaks_do_not_matter(name: str) -> None:
    joined = ["\n".join(pages(name))]
    assert BoaCardParser().parse(joined) == parse(name)


def test_two_pages_header_balances_and_totals() -> None:
    statement = parse("two_pages")
    assert statement.parser_name == "boa_card"
    assert statement.institution == "Bank of America"
    assert statement.account_type is AccountType.CREDIT_CARD
    assert statement.account_last4 == "1111"
    assert statement.period_start == date(2026, 3, 29)
    assert statement.period_end == date(2026, 4, 28)
    assert statement.opening_balance_cents == -155905
    assert statement.closing_balance_cents == -219524
    assert statement.declared_section_totals == {
        Section.PAYMENTS_CREDITS: 94524,
        Section.PURCHASES: -154009,
        Section.FEES: -2900,
        Section.INTEREST: -1234,
    }


def test_two_pages_lines() -> None:
    assert parse("two_pages").lines == [
        StatementLine(
            date(2026, 4, 6),
            date(2026, 4, 3),
            "EXAMPLESOFT*STORE REDMOND WA",
            4319,
            Section.PAYMENTS_CREDITS,
            card_last4="1111",
            external_ref="3012",
        ),
        StatementLine(
            date(2026, 4, 7),
            date(2026, 4, 7),
            "PAYMENT FROM CHK 9999 CONF#M00000000",
            90205,
            Section.PAYMENTS_CREDITS,
            card_last4="1111",
            external_ref="4733",
        ),
        StatementLine(
            date(2026, 3, 30),
            date(2026, 3, 28),
            "ACME GROCERY #123 DECATUR GA",
            -3649,
            Section.PURCHASES,
            card_last4="2222",
            external_ref="7838",
        ),
        StatementLine(
            date(2026, 4, 2),
            date(2026, 4, 1),
            "FOOBAR CAFE ATLANTA GA",
            -1275,
            Section.PURCHASES,
            card_last4="1111",
            external_ref="1190",
        ),
        StatementLine(
            date(2026, 4, 2),
            date(2026, 4, 1),
            "FOOBAR CAFE ATLANTA GA",
            -1275,
            Section.PURCHASES,
            card_last4="1111",
            external_ref="1191",
        ),
        StatementLine(
            date(2026, 4, 11),
            date(2026, 4, 10),
            "EXAMPLE AIRLINES 0061234567890 TX",
            -41260,
            Section.PURCHASES,
            card_last4="2222",
            external_ref="5521",
        ),
        StatementLine(
            date(2026, 4, 21),
            date(2026, 4, 20),
            "ACME HARDWARE #88 2026 MARIETTA GA",
            -106550,
            Section.PURCHASES,
            card_last4="1111",
            external_ref="0042",
        ),
        StatementLine(
            date(2026, 4, 15),
            date(2026, 4, 15),
            "LATE FEE FOR PAYMENT DUE 04/10",
            -2900,
            Section.FEES,
        ),
        StatementLine(
            date(2026, 4, 28),
            date(2026, 4, 28),
            "INTEREST CHARGED ON PURCHASES",
            -1234,
            Section.INTEREST,
        ),
    ]


def test_year_end_header_balances_and_totals() -> None:
    statement = parse("year_end")
    assert statement.parser_name == "boa_card"
    assert statement.institution == "Bank of America"
    assert statement.account_type is AccountType.CREDIT_CARD
    assert statement.account_last4 == "3333"
    assert statement.period_start == date(2026, 12, 20)
    assert statement.period_end == date(2027, 1, 19)
    assert statement.opening_balance_cents == 0
    assert statement.closing_balance_cents == -16049
    assert statement.declared_section_totals == {
        Section.PAYMENTS_CREDITS: 0,
        Section.PURCHASES: -16049,
        Section.FEES: 0,
        Section.INTEREST: 0,
    }


def test_year_end_lines() -> None:
    assert parse("year_end").lines == [
        StatementLine(
            date(2026, 12, 20),
            date(2026, 12, 19),
            "ACME TOYS #7 AUSTIN TX",
            -8999,
            Section.PURCHASES,
            card_last4="3333",
            external_ref="2001",
        ),
        StatementLine(
            date(2027, 1, 2),
            date(2026, 12, 31),
            "FOOBAR LIQUOR AUSTIN TX",
            -4550,
            Section.PURCHASES,
            card_last4="3333",
            external_ref="2002",
        ),
        StatementLine(
            date(2027, 1, 16),
            date(2027, 1, 15),
            "ACME GYM 512-555-0100 TX",
            -2500,
            Section.PURCHASES,
            card_last4="3333",
            external_ref="2003",
        ),
    ]


def test_credit_balance_header_balances_and_totals() -> None:
    statement = parse("credit_balance")
    assert statement.parser_name == "boa_card"
    assert statement.institution == "Bank of America"
    assert statement.account_type is AccountType.CREDIT_CARD
    assert statement.account_last4 == "5555"
    assert statement.period_start == date(2026, 6, 1)
    assert statement.period_end == date(2026, 6, 30)
    assert statement.opening_balance_cents == 2000
    assert statement.closing_balance_cents == 2775
    assert statement.declared_section_totals == {
        Section.PAYMENTS_CREDITS: 1500,
        Section.PURCHASES: -725,
        Section.FEES: 0,
        Section.INTEREST: 0,
    }


def test_credit_balance_lines() -> None:
    assert parse("credit_balance").lines == [
        StatementLine(
            date(2026, 6, 13),
            date(2026, 6, 12),
            "ACME OUTLET REFUND DALLAS TX",
            1500,
            Section.PAYMENTS_CREDITS,
            card_last4="5555",
            external_ref="9100",
        ),
        StatementLine(
            date(2026, 6, 21),
            date(2026, 6, 20),
            "FOOBAR SNACKS DALLAS TX",
            -725,
            Section.PURCHASES,
            card_last4="5555",
            external_ref="9101",
        ),
    ]


@pytest.mark.parametrize(
    "first_page",
    [
        "",
        "www.bankofamerica.com",
        "Account# 4400 0000 0000 1111",
        "WWW.BANKOFAMERICA.COM\nACCOUNT# 4400 0000 0000 1111",
        "Bank of America\nAccount number 4400 0000 0000 1111",
    ],
)
def test_detect_needs_both_markers(first_page: str) -> None:
    assert BoaCardParser().detect(first_page) is False


def test_detect_with_both_markers() -> None:
    assert BoaCardParser().detect("see bankofamerica.com\nAccount# 4400 0000 0000 1111") is True


def test_spaces_inside_a_description_are_collapsed() -> None:
    text = pages("credit_balance")[0].replace(
        "FOOBAR SNACKS DALLAS TX", "FOOBAR   SNACKS  DALLAS TX"
    )
    assert BoaCardParser().parse([text]).lines[1].description == "FOOBAR SNACKS DALLAS TX"
