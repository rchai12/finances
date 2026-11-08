from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers import detect_parser
from finances.ingest.parsers.marcus import MarcusSavingsParser
from finances.ingest.reconcile import reconcile
from finances.ingest.statement import Section, StatementLine

CD = Path(__file__).parent.parent / "fixtures" / "statements" / "marcus" / "cd.txt"


def pages() -> list[str]:
    return CD.read_text(encoding="utf-8").split("\f")


def test_a_cd_statement_is_detected() -> None:
    assert MarcusSavingsParser().detect(pages()[0]) is True
    assert detect_parser(pages()).name == "marcus_savings"


def test_a_cd_statement_parses_as_savings() -> None:
    statement = MarcusSavingsParser().parse(pages())
    assert (
        statement.parser_name,
        statement.institution,
        statement.account_type,
        statement.account_last4,
        statement.period_start,
        statement.period_end,
        statement.opening_balance_cents,
        statement.closing_balance_cents,
    ) == (
        "marcus_savings",
        "Marcus by Goldman Sachs",
        AccountType.SAVINGS,
        "7777",
        date(2026, 7, 1),
        date(2026, 9, 30),
        500000,
        505461,
    )
    assert statement.lines == [
        StatementLine(date(2026, 9, 30), None, "Interest Paid", 5461, Section.INTEREST)
    ]
    assert reconcile(statement).ok


@pytest.mark.parametrize(
    "first_page",
    [
        "CD ACCOUNT STATEMENT",
        "Marcus by Goldman Sachs\nCD ACCOUNT STATEMENT",
        "Goldman Sachs Bank USA\nCd Account Statement",
        "Goldman Sachs Bank USA\nCD STATEMENT",
    ],
)
def test_a_cd_heading_alone_or_misspelt_is_not_detected(first_page: str) -> None:
    assert MarcusSavingsParser().detect(first_page) is False


def test_both_headings_with_the_bank_are_detected() -> None:
    for heading in ("ONLINE SAVINGS ACCOUNT STATEMENT", "CD ACCOUNT STATEMENT"):
        assert MarcusSavingsParser().detect(f"{heading}\nGoldman Sachs Bank USA, Member FDIC")
