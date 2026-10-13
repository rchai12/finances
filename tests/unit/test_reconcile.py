import dataclasses
import typing
from datetime import date

import pytest

from finances.domain.models import AccountType
from finances.ingest.reconcile import ReconcileResult, reconcile
from finances.ingest.statement import ParsedStatement, Section, StatementLine


def line(amount_cents: int, section: Section = Section.PURCHASES) -> StatementLine:
    return StatementLine(date(2026, 1, 5), None, "ACME COFFEE", amount_cents, section)


def statement(
    opening: int,
    closing: int,
    lines: list[StatementLine],
    totals: dict[Section, int] | None = None,
) -> ParsedStatement:
    return ParsedStatement(
        parser_name="fake_bank",
        institution="Fake Bank",
        account_type=AccountType.CREDIT_CARD,
        account_last4="1111",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        opening_balance_cents=opening,
        closing_balance_cents=closing,
        lines=lines,
        declared_section_totals=totals or {},
    )


CARD_LINES = [
    line(-450),
    line(-12999),
    line(2500, Section.PAYMENTS_CREDITS),
    line(-13, Section.INTEREST),
]


def test_result_is_a_frozen_dataclass_with_five_fields() -> None:
    assert [field.name for field in dataclasses.fields(ReconcileResult)] == [
        "ok",
        "expected_closing_cents",
        "actual_closing_cents",
        "difference_cents",
        "section_mismatches",
    ]
    assert typing.get_type_hints(ReconcileResult) == {
        "ok": bool,
        "expected_closing_cents": int,
        "actual_closing_cents": int,
        "difference_cents": int,
        "section_mismatches": dict[Section, tuple[int, int]],
    }
    result = reconcile(statement(0, 0, []))
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.ok = False


def test_a_balanced_statement_is_ok() -> None:
    result = reconcile(statement(-10000, -20962, CARD_LINES))
    assert result == ReconcileResult(
        ok=True,
        expected_closing_cents=-20962,
        actual_closing_cents=-20962,
        difference_cents=0,
        section_mismatches={},
    )


def test_a_statement_with_no_lines_is_ok_when_the_balance_did_not_move() -> None:
    assert reconcile(statement(5000, 5000, [])).ok is True
    assert reconcile(statement(0, 0, [])).ok is True


def test_a_statement_with_no_lines_fails_when_the_balance_moved() -> None:
    result = reconcile(statement(5000, 4000, []))
    assert result.ok is False
    assert result.expected_closing_cents == 5000
    assert result.difference_cents == -1000


@pytest.mark.parametrize(
    ("closing", "difference"),
    [(-20961, 1), (-20963, -1), (-20862, 100), (0, 20962), (20962, 41924)],
)
def test_the_difference_is_actual_minus_expected(closing: int, difference: int) -> None:
    result = reconcile(statement(-10000, closing, CARD_LINES))
    assert result.ok is False
    assert result.expected_closing_cents == -20962
    assert result.actual_closing_cents == closing
    assert result.difference_cents == difference
    assert result.section_mismatches == {}


def test_one_cent_is_never_tolerated() -> None:
    lines = [line(-1)] * 3
    assert reconcile(statement(100, 97, lines)).ok is True
    assert reconcile(statement(100, 98, lines)).ok is False
    assert reconcile(statement(100, 96, lines)).ok is False


def test_a_checking_account_with_positive_balances_reconciles() -> None:
    lines = [
        line(250000, Section.DEPOSITS),
        line(-120050, Section.WITHDRAWALS),
        line(-4500, Section.CHECKS),
    ]
    result = reconcile(statement(100000, 225450, lines))
    assert result.ok is True
    assert result.expected_closing_cents == 225450


def test_matching_section_totals_are_ok() -> None:
    totals = {Section.PURCHASES: -13449, Section.PAYMENTS_CREDITS: 2500, Section.INTEREST: -13}
    result = reconcile(statement(-10000, -20962, CARD_LINES, totals))
    assert result.ok is True
    assert result.section_mismatches == {}


def test_a_wrong_section_total_fails_even_when_the_balance_is_right() -> None:
    totals = {Section.PURCHASES: -13450, Section.PAYMENTS_CREDITS: 2500}
    result = reconcile(statement(-10000, -20962, CARD_LINES, totals))
    assert result.ok is False
    assert result.difference_cents == 0
    assert result.section_mismatches == {Section.PURCHASES: (-13450, -13449)}


def test_every_wrong_section_is_reported_as_declared_then_computed() -> None:
    totals = {Section.INTEREST: 0, Section.PURCHASES: -13449, Section.PAYMENTS_CREDITS: 2400}
    result = reconcile(statement(-10000, -20962, CARD_LINES, totals))
    assert result.ok is False
    assert result.section_mismatches == {
        Section.INTEREST: (0, -13),
        Section.PAYMENTS_CREDITS: (2400, 2500),
    }
    assert list(result.section_mismatches) == [Section.INTEREST, Section.PAYMENTS_CREDITS]


def test_a_declared_total_for_a_section_with_no_lines_is_compared_with_zero() -> None:
    assert reconcile(statement(-10000, -20962, CARD_LINES, {Section.FEES: 0})).ok is True
    result = reconcile(statement(-10000, -20962, CARD_LINES, {Section.FEES: -3500}))
    assert result.ok is False
    assert result.section_mismatches == {Section.FEES: (-3500, 0)}


def test_sections_without_a_declared_total_are_not_checked() -> None:
    result = reconcile(statement(-10000, -20962, CARD_LINES, {Section.INTEREST: -13}))
    assert result.ok is True


def test_both_kinds_of_failure_are_reported_together() -> None:
    result = reconcile(statement(-10000, -20000, CARD_LINES, {Section.PURCHASES: -1}))
    assert result.ok is False
    assert result.difference_cents == 962
    assert result.section_mismatches == {Section.PURCHASES: (-1, -13449)}


def test_reconcile_does_not_change_the_statement() -> None:
    totals = {Section.PURCHASES: -1}
    lines = list(CARD_LINES)
    subject = statement(-10000, -20962, lines, totals)
    reconcile(subject)
    assert subject.lines == CARD_LINES
    assert subject.declared_section_totals == {Section.PURCHASES: -1}


def test_large_amounts_stay_exact() -> None:
    big = 9007199254740993
    result = reconcile(statement(0, big + 1, [line(big, Section.DEPOSITS), line(1)]))
    assert result.ok is True
    assert result.expected_closing_cents == 9007199254740994
    assert type(result.expected_closing_cents) is int
