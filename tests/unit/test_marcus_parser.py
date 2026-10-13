from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers import detect_parser, registered_parsers
from finances.ingest.parsers.marcus import MarcusSavingsParser
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

FIXTURES = Path(__file__).parent.parent / "fixtures" / "statements"
STATEMENTS = ["basic", "interest_only"]
OTHER_BANKS = [
    ("capital_one", "single_card"),
    ("capital_one", "multi_card"),
    ("capital_one", "other_bank"),
    ("boa", "two_pages"),
    ("boa", "year_end"),
    ("citi", "two_cardholders"),
    ("citi", "year_end"),
    ("truist", "checking"),
    ("truist", "savings_no_activity"),
]


def pages(name: str, bank: str = "marcus") -> list[str]:
    return (FIXTURES / bank / f"{name}.txt").read_text(encoding="utf-8").split("\f")


def parse(name: str) -> ParsedStatement:
    return MarcusSavingsParser().parse(pages(name))


def test_the_parser_is_registered_once_under_its_name() -> None:
    names = [parser.name for parser in registered_parsers()]
    assert names.count("marcus_savings") == 1
    assert MarcusSavingsParser.name == "marcus_savings"


@pytest.mark.parametrize("name", STATEMENTS)
def test_detects_its_own_fixtures(name: str) -> None:
    assert MarcusSavingsParser().detect(pages(name)[0]) is True
    assert detect_parser(pages(name)).name == "marcus_savings"


@pytest.mark.parametrize(("bank", "name"), OTHER_BANKS)
def test_does_not_detect_another_banks_statement(bank: str, name: str) -> None:
    assert MarcusSavingsParser().detect(pages(name, bank)[0]) is False


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
    assert MarcusSavingsParser().parse(joined) == parse(name)


def test_basic_header_balances_and_totals() -> None:
    statement = parse("basic")
    assert statement.parser_name == "marcus_savings"
    assert statement.institution == "Marcus by Goldman Sachs"
    assert statement.account_type is AccountType.SAVINGS
    assert statement.account_last4 == "1111"
    assert statement.period_start == date(2026, 9, 1)
    assert statement.period_end == date(2026, 9, 30)
    assert statement.opening_balance_cents == 1464612
    assert statement.closing_balance_cents == 1243575
    assert statement.declared_section_totals == {}
    assert len(statement.lines) == 4


def test_basic_lines() -> None:
    assert parse("basic").lines == [
        StatementLine(
            date(2026, 9, 1),
            None,
            "ACHDepositInternettransferfromEXAMPLE BANKDDAaccount",
            300000,
            Section.DEPOSITS,
        ),
        StatementLine(
            date(2026, 9, 17),
            None,
            "ACHWithdrawalInternettransfertoEXAMPLE BANK,N.A.",
            -500000,
            Section.WITHDRAWALS,
        ),
        StatementLine(
            date(2026, 9, 22),
            None,
            "ACHWithdrawalInternettransfertoEXAMPLE BANK,N.A.",
            -25050,
            Section.WITHDRAWALS,
        ),
        StatementLine(date(2026, 9, 30), None, "InterestPaid", 4013, Section.INTEREST),
    ]


def test_interest_only_header_balances_and_totals() -> None:
    statement = parse("interest_only")
    assert statement.parser_name == "marcus_savings"
    assert statement.institution == "Marcus by Goldman Sachs"
    assert statement.account_type is AccountType.SAVINGS
    assert statement.account_last4 == "4444"
    assert statement.period_start == date(2026, 12, 1)
    assert statement.period_end == date(2026, 12, 31)
    assert statement.opening_balance_cents == 100000
    assert statement.closing_balance_cents == 100354
    assert statement.declared_section_totals == {}
    assert len(statement.lines) == 1


def test_interest_only_lines() -> None:
    assert parse("interest_only").lines == [
        StatementLine(date(2026, 12, 31), None, "Interest Paid", 354, Section.INTEREST),
    ]


def test_amount_mismatch_is_refused() -> None:
    assert MarcusSavingsParser().detect(pages("amount_mismatch")[0]) is True
    with pytest.raises(StatementError) as caught:
        parse("amount_mismatch")
    assert str(caught.value) == "marcus: row 2 does not match its balance"


@pytest.mark.parametrize(
    "first_page",
    [
        "",
        "Goldman Sachs Bank USA",
        "ONLINE SAVINGS ACCOUNT STATEMENT",
        "Marcus by Goldman Sachs\nONLINE SAVINGS ACCOUNT STATEMENT",
        "GOLDMAN SACHS BANK USA\nOnline Savings Account Statement",
    ],
)
def test_detect_needs_both_markers(first_page: str) -> None:
    assert MarcusSavingsParser().detect(first_page) is False


def test_detect_with_both_markers() -> None:
    page = "ONLINE SAVINGS ACCOUNT STATEMENT\nGoldman Sachs Bank USA, Member FDIC"
    assert MarcusSavingsParser().detect(page) is True


def edited(name: str, old: str, new: str) -> ParsedStatement:
    text = "\f".join(pages(name))
    assert old in text
    return MarcusSavingsParser().parse(text.replace(old, new).split("\f"))


def test_spaces_inside_a_description_are_collapsed() -> None:
    statement = edited("basic", "EXAMPLE BANKDDAaccount", "EXAMPLE    BANKDDAaccount")
    assert statement == parse("basic")


def test_the_sign_comes_from_the_balance_not_the_column() -> None:
    moved = "$250.50" + " " * 30 + "$12,395.62"
    assert edited("basic", "$250.50  $12,395.62", moved) == parse("basic")


@pytest.mark.parametrize("label", ["Beginning Balance", "BeginningBalance", "Beginning  Balance"])
def test_the_beginning_balance_label_with_or_without_spaces(label: str) -> None:
    assert edited("basic", "Beginning Balance", label) == parse("basic")


@pytest.mark.parametrize("label", ["Ending Balance", "EndingBalance"])
def test_the_ending_balance_label_with_or_without_spaces(label: str) -> None:
    assert edited("basic", "EndingBalance", label) == parse("basic")


@pytest.mark.parametrize("text", ["InterestPaid", "Interest Paid"])
def test_interest_has_its_own_section(text: str) -> None:
    line = edited("basic", "InterestPaid", text).lines[3]
    assert (line.description, line.section, line.amount_cents) == (text, Section.INTEREST, 4013)


def test_a_withdrawal_called_interest_something_else_is_a_withdrawal() -> None:
    line = edited(
        "basic",
        "InterestPaid                                            $40.13              $12,435.75",
        "InterestPaidBack   $40.13   $12,355.49",
    ).lines[3]
    assert (line.section, line.amount_cents) == (Section.WITHDRAWALS, -4013)


def test_a_row_that_leaves_the_balance_unchanged_is_left_out() -> None:
    statement = edited(
        "basic",
        "InterestPaid                                            $40.13              $12,435.75",
        "InterestPaid   $0.00   $12,395.62",
    )
    assert len(statement.lines) == 3
    assert statement.closing_balance_cents == 1243575
