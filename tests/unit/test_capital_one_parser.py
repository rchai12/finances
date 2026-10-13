from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers import registered_parsers
from finances.ingest.parsers.capital_one import CapitalOneCardParser
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementLine

FIXTURES = Path(__file__).parent.parent / "fixtures" / "statements" / "capital_one"
STATEMENTS = ["single_card", "multi_card", "continuation", "credit_balance"]
P, C = Section.PURCHASES, Section.PAYMENTS_CREDITS


def pages(name: str) -> list[str]:
    return (FIXTURES / f"{name}.txt").read_text(encoding="utf-8").split("\f")


def parse(name: str) -> ParsedStatement:
    return CapitalOneCardParser().parse(pages(name))


def row(posted, transacted, text, cents, section, card, holder) -> StatementLine:
    return StatementLine(
        posted, transacted, text, cents, section, card_last4=card, cardholder=holder
    )


def jane(posted, transacted, text, cents, section=P) -> StatementLine:
    return row(posted, transacted, text, cents, section, "1111", "JANE DOE")


def test_the_parser_is_registered_once_under_its_name() -> None:
    names = [parser.name for parser in registered_parsers()]
    assert names.count("capital_one_card") == 1
    assert CapitalOneCardParser.name == "capital_one_card"


@pytest.mark.parametrize("name", STATEMENTS)
def test_detects_every_capital_one_fixture(name: str) -> None:
    assert CapitalOneCardParser().detect(pages(name)[0]) is True


@pytest.mark.parametrize(
    "first_page",
    [
        "",
        "Capital One",
        "31 days in Billing Cycle",
        "capital one   31 days in billing cycle",
        "Example Bank   capitalone.com is not our site   30 days in Statement Cycle",
    ],
)
def test_does_not_detect_other_text(first_page: str) -> None:
    assert CapitalOneCardParser().detect(first_page) is False


def test_does_not_detect_another_bank() -> None:
    assert CapitalOneCardParser().detect(pages("other_bank")[0]) is False


@pytest.mark.parametrize(
    "first_page",
    ["Capital One   31 days in Billing Cycle", "see capitalone.com\n28 days in Billing Cycle"],
)
def test_detects_either_brand_text_with_the_billing_cycle_line(first_page: str) -> None:
    assert CapitalOneCardParser().detect(first_page) is True


@pytest.mark.parametrize(
    ("name", "last4", "start", "end", "opening", "closing", "count"),
    [
        ("single_card", "1111", date(2025, 12, 24), date(2026, 1, 23), -25000, -24258, 11),
        ("multi_card", "1111", date(2026, 3, 5), date(2026, 4, 4), -30000, -19674, 8),
        ("continuation", "4444", date(2026, 4, 1), date(2026, 4, 30), 0, -51260, 2),
        ("credit_balance", "5555", date(2026, 5, 1), date(2026, 5, 31), 5000, 6750, 2),
    ],
)
def test_header_and_balances(name, last4, start, end, opening, closing, count) -> None:
    statement = parse(name)
    assert statement.parser_name == "capital_one_card"
    assert statement.institution == "Capital One"
    assert statement.account_type is AccountType.CREDIT_CARD
    assert statement.account_last4 == last4
    assert (statement.period_start, statement.period_end) == (start, end)
    assert statement.opening_balance_cents == opening
    assert statement.closing_balance_cents == closing
    assert len(statement.lines) == count


@pytest.mark.parametrize("name", STATEMENTS)
def test_every_fixture_reconciles(name: str) -> None:
    result = reconcile(parse(name))
    assert result.difference_cents == 0
    assert result.section_mismatches == {}
    assert result.ok is True


@pytest.mark.parametrize(
    ("name", "totals"),
    [
        ("single_card", {C: 26565, Section.FEES: 0, Section.INTEREST: -13, P: -25810}),
        ("multi_card", {C: 32000, Section.FEES: -3500, Section.INTEREST: 0, P: -18174}),
        ("continuation", {C: 0, Section.FEES: 0, Section.INTEREST: 0, P: -51260}),
        ("credit_balance", {C: 3000, Section.FEES: 0, Section.INTEREST: 0, P: -1250}),
    ],
)
def test_declared_section_totals(name: str, totals: dict[Section, int]) -> None:
    assert parse(name).declared_section_totals == totals


def test_single_card_lines_across_two_pages_and_a_year_end() -> None:
    assert parse("single_card").lines == [
        jane(date(2026, 1, 12), date(2026, 1, 11), "CAPITAL ONE MOBILE PYMT", 25000, C),
        jane(date(2026, 1, 16), date(2026, 1, 15), "ACME STORE REFUND", 1565, C),
        jane(date(2025, 12, 24), date(2025, 12, 23), "ACME VENDING DallasGrapevineTX", -300),
        jane(date(2026, 1, 6), date(2026, 1, 5), "FOOBAR CHICKEN #123TUCKERGA", -3896),
        jane(date(2026, 1, 8), date(2026, 1, 7), "ACME COFFEE", -450),
        jane(date(2026, 1, 11), date(2026, 1, 10), "FOOBAR GROCERY #45", -12780),
        jane(date(2026, 1, 15), date(2026, 1, 14), "EXAMPLESTREAM.COM", -1599),
        jane(date(2026, 1, 21), date(2026, 1, 20), "ACME GAS #9", -4125),
        jane(date(2026, 1, 23), date(2026, 1, 22), "FOOBAR BOOKS", -2210),
        jane(date(2026, 1, 23), date(2026, 1, 22), "ACME COFFEE", -450),
        StatementLine(
            date(2026, 1, 23), None, "INTEREST CHARGE ON PURCHASES", -13, Section.INTEREST
        ),
    ]


def test_multi_card_lines_carry_their_cardholder_and_card() -> None:
    assert parse("multi_card").lines == [
        jane(date(2026, 3, 20), date(2026, 3, 20), "CAPITAL ONE AUTOPAY PYMT", 30000, C),
        jane(date(2026, 3, 7), date(2026, 3, 6), "ACME COFFEE", -525),
        jane(date(2026, 4, 1), date(2026, 3, 30), "FOOBAR GROCERY", -8000),
        row(date(2026, 3, 11), date(2026, 3, 10), "ACME HARDWARE", -4510, P, "2222", "JOHN DOE"),
        row(date(2026, 4, 3), date(2026, 4, 2), "FOOBAR DINER", -3140, P, "2222", "JOHN DOE"),
        row(date(2026, 3, 26), date(2026, 3, 25), "ACME STORE RETURN", 2000, C, "3333", "ALEX ROE"),
        row(date(2026, 3, 13), date(2026, 3, 12), "EXAMPLE TOYS", -1999, P, "3333", "ALEX ROE"),
        StatementLine(date(2026, 4, 4), None, "TOTAL FEES FOR THIS PERIOD", -3500, Section.FEES),
    ]


def test_continuation_lines_are_ignored() -> None:
    lines = parse("continuation").lines
    assert lines == [
        row(
            date(2026, 4, 13),
            date(2026, 4, 12),
            "EXAMPLE AIR0012345678FORT WORTHTX",
            -41260,
            P,
            "4444",
            "MARIA POE",
        ),
        row(
            date(2026, 4, 15),
            date(2026, 4, 14),
            "ACME HOTEL SEATTLEWA",
            -10000,
            P,
            "4444",
            "MARIA POE",
        ),
    ]
    text = " ".join(line.description for line in lines)
    assert "PSGR" not in text
    assert "FOLIO" not in text
    assert "CHECK-IN" not in text


def test_a_credit_balance_is_positive_from_the_holder_side() -> None:
    statement = parse("credit_balance")
    assert statement.opening_balance_cents == 5000
    assert statement.closing_balance_cents == 6750
    assert statement.lines == [
        row(
            date(2026, 5, 11), date(2026, 5, 10), "FOOBAR OUTLET REFUND", 3000, C, "5555", "SAM LEE"
        ),
        row(date(2026, 5, 21), date(2026, 5, 20), "ACME SNACKS", -1250, P, "5555", "SAM LEE"),
    ]


@pytest.mark.parametrize("name", STATEMENTS)
def test_parsing_twice_gives_the_same_statement(name: str) -> None:
    parser = CapitalOneCardParser()
    assert parser.parse(pages(name)) == parser.parse(pages(name))
    assert CapitalOneCardParser().parse(pages(name)) == parser.parse(pages(name))


def test_the_page_break_does_not_matter() -> None:
    joined = ["\n".join(pages("single_card"))]
    assert CapitalOneCardParser().parse(joined) == parse("single_card")


def credit_balance_lines() -> list[str]:
    return pages("credit_balance")[0].split("\n")


def parse_lines(lines: list[str]) -> ParsedStatement:
    return CapitalOneCardParser().parse(["\n".join(lines)])


def test_a_row_before_any_card_section_is_ignored() -> None:
    lines = credit_balance_lines()
    lines.insert(3, "May 2      May 3      ACME STRAY ROW                      $9.99")
    assert parse_lines(lines).lines == parse("credit_balance").lines


def test_a_row_after_a_cards_total_line_is_ignored() -> None:
    lines = credit_balance_lines()
    total = next(i for i, line in enumerate(lines) if line.startswith("SAM LEE #5555: Total"))
    lines.insert(total + 1, "May 22      May 23      ACME AFTER TOTAL                    $1.00")
    assert parse_lines(lines).lines == parse("credit_balance").lines


def test_spaces_inside_a_description_are_collapsed() -> None:
    lines = [line.replace("ACME SNACKS", "ACME   SNACKS") for line in credit_balance_lines()]
    assert parse_lines(lines).lines[1].description == "ACME SNACKS"


def test_the_minus_sign_decides_the_sign_not_the_section() -> None:
    lines = credit_balance_lines()
    index = next(i for i, line in enumerate(lines) if "ACME SNACKS" in line)
    lines[index] = lines[index].replace("$12.50", "- $12.50")
    refund = parse_lines(lines).lines[1]
    assert refund.amount_cents == 1250
    assert refund.section is Section.PURCHASES


def test_a_label_followed_by_a_number_that_is_not_money_is_skipped() -> None:
    trap = "Rewards      Previous Balance      9,999      New Balance      8,888"
    statement = parse_lines([trap, *credit_balance_lines()])
    assert statement.opening_balance_cents == 5000
    assert statement.closing_balance_cents == 6750
