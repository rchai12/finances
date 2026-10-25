from datetime import date
from pathlib import Path

import pytest

from finances.domain.models import AccountType
from finances.ingest.parsers.boa_deposit import BoaDepositParser
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

FIXTURES = Path(__file__).parent.parent / "fixtures" / "statements" / "boa_deposit"


def pages(name: str = "checking") -> list[str]:
    return (FIXTURES / f"{name}.txt").read_text(encoding="utf-8").split("\f")


def parse_text(*lines: str) -> ParsedStatement:
    return BoaDepositParser().parse(["\n".join(lines)])


def failure(*lines: str) -> str:
    with pytest.raises(StatementError) as caught:
        BoaDepositParser().parse(["\n".join(lines)])
    return str(caught.value)


HEAD = [
    "Bank of America, N.A.                                   bankofamerica.com",
    "Your Advantage Plus Banking",
    "for September 1, 2026 to September 30, 2026        Account number: 0000 1234 1111",
    "Beginning balance on September 1, 2026                       $1,500.00",
    "Ending balance on September 30, 2026                         $1,500.00",
]


def test_an_overdrawn_beginning_balance_is_negative() -> None:
    statement = parse_text(
        *HEAD[:-2],
        "Beginning balance on September 1, 2026                      -$25.00",
        HEAD[-1],
    )
    assert statement.opening_balance_cents == -2500


def test_a_reversal_without_a_minus_is_positive() -> None:
    statement = parse_text(
        *HEAD,
        "Other subtractions",
        "09/05/26    EXAMPLE CARD REVERSAL                                             50.00",
        "Total other subtractions                                                 $50.00",
    )
    assert statement.lines == [
        StatementLine(
            date(2026, 9, 5),
            None,
            "EXAMPLE CARD REVERSAL",
            5000,
            Section.WITHDRAWALS,
        )
    ]


def test_a_zero_amount_row_is_skipped() -> None:
    statement = parse_text(
        *HEAD,
        "Deposits and other additions",
        "09/02/26    EXAMPLE ZERO                                                      0.00",
        "09/03/26    EXAMPLE KEEP                                                     10.00",
        "Total deposits and other additions                                       $10.00",
    )
    assert statement.lines == [
        StatementLine(date(2026, 9, 3), None, "EXAMPLE KEEP", 1000, Section.DEPOSITS)
    ]


@pytest.mark.parametrize(
    "period",
    [
        "for September 31, 2026 to September 30, 2026        Account number: 0000 1234 1111",
        "for Flooptember 1, 2026 to September 30, 2026        Account number: 0000 1234 1111",
        "for September 1, 2026 to Flooptember 30, 2026        Account number: 0000 1234 1111",
    ],
)
def test_a_bad_period_date_is_refused(period: str) -> None:
    assert failure(HEAD[0], HEAD[1], period, HEAD[3], HEAD[4]) == (
        "boa_deposit: statement period not found"
    )


def test_three_account_digits_are_refused() -> None:
    line = "for September 1, 2026 to September 30, 2026        Account number: 111"
    assert failure(HEAD[0], HEAD[1], line, HEAD[3], HEAD[4]) == (
        "boa_deposit: account number not found"
    )


def test_a_zero_amount_check_is_skipped() -> None:
    statement = parse_text(
        *HEAD,
        "Checks",
        "09/10/26    1045            0.00",
        "09/14/26    1046         -200.00",
        "Total checks                                                            -$200.00",
    )
    assert statement.lines == [
        StatementLine(
            date(2026, 9, 14), None, "CHECK 1046", -20000, Section.CHECKS, external_ref="1046"
        )
    ]


def test_a_star_before_the_check_number_is_stripped() -> None:
    statement = parse_text(
        *HEAD,
        "Checks",
        "09/10/26    *1045         -125.00",
        "Total checks                                                            -$125.00",
    )
    assert statement.lines == [
        StatementLine(
            date(2026, 9, 10), None, "CHECK 1045", -12500, Section.CHECKS, external_ref="1045"
        )
    ]


def test_an_impossible_check_date_is_refused() -> None:
    assert (
        failure(
            *HEAD,
            "Checks",
            "02/30/26    1045         -125.00",
            "Total checks                                                            -$125.00",
        )
        == "boa_deposit: invalid date"
    )


def test_an_impossible_purchase_day_and_checkcard_later_have_no_purchase_date() -> None:
    statement = parse_text(
        *HEAD,
        "ATM and debit card subtractions",
        "09/03/26    CHECKCARD 1340 ACME COFFEE ANYTOWN GA                              -4.50",
        "09/08/26    ACME MARKET CHECKCARD 0915 ANYTOWN GA                              -8.00",
        "Total ATM and debit card subtractions                                     -$12.50",
    )
    assert [row.transaction_date for row in statement.lines] == [None, None]


def test_a_savings_product_after_the_account_line_stays_checking() -> None:
    statement = parse_text(
        HEAD[0],
        HEAD[1],
        HEAD[2],
        "Your Savings Plus",
        HEAD[3],
        HEAD[4],
    )
    assert statement.account_type is AccountType.CHECKING


def test_a_total_label_without_money_is_passed_over() -> None:
    statement = parse_text(
        *HEAD,
        "Total deposits and other additions",
        "Total deposits and other additions                                    $10.00",
    )
    assert statement.declared_section_totals == {Section.DEPOSITS: 1000}


def test_the_atm_total_alone_is_withdrawals() -> None:
    statement = parse_text(
        *HEAD,
        "ATM and debit card subtractions",
        "09/03/26    CHECKCARD 0902 ACME COFFEE ANYTOWN GA                              -4.50",
        "Total ATM and debit card subtractions                                     -$4.50",
    )
    assert statement.declared_section_totals == {Section.WITHDRAWALS: -450}


def test_a_summary_checks_line_does_not_open_the_checks_section() -> None:
    statement = parse_text(
        *HEAD,
        "Checks  -350.00",
        "09/10/26    1041          -125.00",
    )
    assert statement.lines == []


def test_detect_needs_beginning_balance_on() -> None:
    first = pages()[0].replace("Beginning balance on", "Opening balance on")
    assert BoaDepositParser().detect(first) is False


def test_no_product_line_is_checking() -> None:
    statement = parse_text(HEAD[0], HEAD[2], HEAD[3], HEAD[4])
    assert statement.account_type is AccountType.CHECKING
