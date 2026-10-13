from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers import detect_parser, registered_parsers
from finances.ingest.parsers.citi import CitiCardParser
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementLine

FIXTURES = Path(__file__).parent.parent / "fixtures" / "statements"
STATEMENTS = ["two_cardholders", "year_end"]
OTHER_BANKS = [
    ("capital_one", "single_card"),
    ("capital_one", "multi_card"),
    ("capital_one", "other_bank"),
    ("boa", "two_pages"),
    ("boa", "year_end"),
    ("boa", "credit_balance"),
]


def pages(name: str, bank: str = "citi") -> list[str]:
    return (FIXTURES / bank / f"{name}.txt").read_text(encoding="utf-8").split("\f")


def parse(name: str) -> ParsedStatement:
    return CitiCardParser().parse(pages(name))


def test_the_parser_is_registered_once_under_its_name() -> None:
    names = [parser.name for parser in registered_parsers()]
    assert names.count("citi_card") == 1
    assert CitiCardParser.name == "citi_card"


@pytest.mark.parametrize("name", STATEMENTS)
def test_detects_its_own_fixtures(name: str) -> None:
    assert CitiCardParser().detect(pages(name)[0]) is True
    assert detect_parser(pages(name)).name == "citi_card"


@pytest.mark.parametrize(("bank", "name"), OTHER_BANKS)
def test_does_not_detect_another_banks_statement(bank: str, name: str) -> None:
    assert CitiCardParser().detect(pages(name, bank)[0]) is False


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
    assert CitiCardParser().parse(joined) == parse(name)


def test_two_cardholders_header_balances_and_totals() -> None:
    statement = parse("two_cardholders")
    assert statement.parser_name == "citi_card"
    assert statement.institution == "Citi"
    assert statement.account_type is AccountType.CREDIT_CARD
    assert statement.account_last4 == "1111"
    assert statement.period_start == date(2026, 8, 13)
    assert statement.period_end == date(2026, 9, 10)
    assert statement.opening_balance_cents == 0
    assert statement.closing_balance_cents == -71594
    assert statement.declared_section_totals == {
        Section.PAYMENTS_CREDITS: 4328,
        Section.PURCHASES: -75922,
        Section.FEES: 0,
        Section.INTEREST: 0,
    }


def test_two_cardholders_lines() -> None:
    assert parse("two_cardholders").lines == [
        StatementLine(
            date(2026, 9, 3),
            date(2026, 9, 3),
            "ACME WHSE #1234 ALLEN TX",
            4328,
            Section.PAYMENTS_CREDITS,
        ),
        StatementLine(
            date(2026, 9, 1),
            date(2026, 9, 1),
            "ACME GAS #1234 ALLEN TX",
            -2896,
            Section.PURCHASES,
            card_last4="1111",
            cardholder="JOHN DOE",
        ),
        StatementLine(
            date(2026, 9, 6),
            None,
            "EXAMPLE CENTER DALLAS TX",
            -2705,
            Section.PURCHASES,
            card_last4="1111",
            cardholder="JOHN DOE",
        ),
        StatementLine(
            date(2026, 9, 9),
            date(2026, 9, 8),
            "ACME WHSE #1234 ALLEN TX",
            -70321,
            Section.PURCHASES,
            card_last4="1111",
            cardholder="JOHN DOE",
        ),
    ]


def test_year_end_header_balances_and_totals() -> None:
    statement = parse("year_end")
    assert statement.parser_name == "citi_card"
    assert statement.institution == "Citi"
    assert statement.account_type is AccountType.CREDIT_CARD
    assert statement.account_last4 == "4444"
    assert statement.period_start == date(2026, 12, 13)
    assert statement.period_end == date(2027, 1, 12)
    assert statement.opening_balance_cents == -50000
    assert statement.closing_balance_cents == -27713
    assert statement.declared_section_totals == {
        Section.PAYMENTS_CREDITS: 51999,
        Section.PURCHASES: -25625,
        Section.FEES: -2900,
        Section.INTEREST: -1187,
    }


def test_year_end_lines() -> None:
    assert parse("year_end").lines == [
        StatementLine(
            date(2026, 12, 28),
            date(2026, 12, 28),
            "ONLINE PAYMENT, THANK YOU",
            50000,
            Section.PAYMENTS_CREDITS,
        ),
        StatementLine(
            date(2027, 1, 5),
            date(2027, 1, 4),
            "FOOBAR OUTDOORS PLANO TX",
            1999,
            Section.PAYMENTS_CREDITS,
        ),
        StatementLine(
            date(2026, 12, 13),
            date(2026, 12, 12),
            "ACME WHSE #1234 PLANO TX",
            -15075,
            Section.PURCHASES,
            card_last4="4444",
            cardholder="MARIA DE LA CRUZ",
        ),
        StatementLine(
            date(2027, 1, 2),
            date(2026, 12, 31),
            "FOOBAR PIZZA PLANO TX",
            -2350,
            Section.PURCHASES,
            card_last4="4444",
            cardholder="MARIA DE LA CRUZ",
        ),
        StatementLine(
            date(2027, 1, 11),
            date(2027, 1, 10),
            "ACME GAS #1234 PLANO TX",
            -4100,
            Section.PURCHASES,
            card_last4="6666",
            cardholder="LEE O'NEIL",
        ),
        StatementLine(
            date(2027, 1, 11),
            None,
            "ACME GAS #1234 PLANO TX",
            -4100,
            Section.PURCHASES,
            card_last4="6666",
            cardholder="LEE O'NEIL",
        ),
        StatementLine(date(2027, 1, 12), date(2027, 1, 12), "LATE FEE", -2900, Section.FEES),
        StatementLine(
            date(2027, 1, 12),
            date(2027, 1, 12),
            "INTEREST CHARGED TO STANDARD PURCH",
            -1187,
            Section.INTEREST,
        ),
    ]


@pytest.mark.parametrize(
    "first_page",
    [
        "",
        "www.citicards.com",
        "Billing Period: 08/13/26-09/10/26",
        "WWW.CITICARDS.COM\nBILLING PERIOD: 08/13/26-09/10/26",
        "Citi\nBilling Period 08/13/26-09/10/26",
    ],
)
def test_detect_needs_both_markers(first_page: str) -> None:
    assert CitiCardParser().detect(first_page) is False


def test_detect_with_both_markers() -> None:
    assert CitiCardParser().detect("see citicards.com\nBilling Period: 08/13/26-09/10/26") is True


def test_spaces_inside_a_description_are_collapsed() -> None:
    text = pages("two_cardholders")[0].replace(
        "ACME GAS #1234 ALLEN TX", "ACME   GAS  #1234 ALLEN TX"
    )
    assert CitiCardParser().parse([text]).lines[1].description == "ACME GAS #1234 ALLEN TX"


def test_a_row_with_a_zero_amount_is_left_out() -> None:
    text = pages("two_cardholders")[0].replace("$28.96", "$0.00")
    lines = CitiCardParser().parse([text]).lines
    assert [item.amount_cents for item in lines] == [4328, -2705, -70321]
