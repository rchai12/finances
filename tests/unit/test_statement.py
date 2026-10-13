import dataclasses
import typing
from datetime import date
from enum import StrEnum

import pytest

from finances.domain.models import AccountType
from finances.ingest.statement import ParsedStatement, Section, StatementError, StatementLine

SECTIONS = [
    ("PAYMENTS_CREDITS", "payments_credits"),
    ("PURCHASES", "purchases"),
    ("FEES", "fees"),
    ("INTEREST", "interest"),
    ("DEPOSITS", "deposits"),
    ("WITHDRAWALS", "withdrawals"),
    ("CHECKS", "checks"),
]


def make_line(**changes: object) -> StatementLine:
    values = {
        "posted_date": date(2026, 1, 6),
        "transaction_date": date(2026, 1, 5),
        "description": "ACME COFFEE #12",
        "amount_cents": -450,
        "section": Section.PURCHASES,
    }
    values.update(changes)
    return StatementLine(**values)


def make_statement(**changes: object) -> ParsedStatement:
    values = {
        "parser_name": "fake_bank",
        "institution": "Fake Bank",
        "account_type": AccountType.CREDIT_CARD,
        "account_last4": "1111",
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 31),
        "opening_balance_cents": -10000,
        "closing_balance_cents": -10450,
        "lines": [make_line()],
    }
    values.update(changes)
    return ParsedStatement(**values)


def names(cls: type) -> list[str]:
    return [field.name for field in dataclasses.fields(cls)]


def with_defaults(cls: type) -> list[str]:
    missing = dataclasses.MISSING
    return [
        field.name
        for field in dataclasses.fields(cls)
        if field.default is not missing or field.default_factory is not missing
    ]


def test_statement_error_is_an_exception() -> None:
    assert issubclass(StatementError, Exception)
    assert not issubclass(StatementError, ValueError)


def test_section_is_a_str_enum_with_seven_members_in_order() -> None:
    assert issubclass(Section, StrEnum)
    assert [(member.name, member.value) for member in Section] == SECTIONS


@pytest.mark.parametrize(("name", "value"), SECTIONS)
def test_section_values(name: str, value: str) -> None:
    assert Section[name].value == value
    assert str(Section[name]) == value
    assert Section(value) is Section[name]


def test_statement_line_fields_in_order() -> None:
    assert names(StatementLine) == [
        "posted_date",
        "transaction_date",
        "description",
        "amount_cents",
        "section",
        "card_last4",
        "cardholder",
        "external_ref",
    ]


def test_statement_line_field_types() -> None:
    assert typing.get_type_hints(StatementLine) == {
        "posted_date": date,
        "transaction_date": date | None,
        "description": str,
        "amount_cents": int,
        "section": Section,
        "card_last4": str | None,
        "cardholder": str | None,
        "external_ref": str | None,
    }


def test_only_the_last_three_line_fields_have_a_default() -> None:
    assert with_defaults(StatementLine) == ["card_last4", "cardholder", "external_ref"]


def test_only_the_totals_field_of_a_statement_has_a_default() -> None:
    assert with_defaults(ParsedStatement) == ["declared_section_totals"]


def test_statement_line_optional_fields_default_to_none() -> None:
    line = make_line()
    assert (line.card_last4, line.cardholder, line.external_ref) == (None, None, None)


def test_statement_line_needs_its_first_five_fields() -> None:
    with pytest.raises(TypeError):
        StatementLine(date(2026, 1, 6), None, "ACME COFFEE", -450)


def test_statement_line_keeps_its_values() -> None:
    line = make_line(card_last4="2222", cardholder="JANE DOE", external_ref="7838")
    assert line.posted_date == date(2026, 1, 6)
    assert line.transaction_date == date(2026, 1, 5)
    assert line.description == "ACME COFFEE #12"
    assert line.amount_cents == -450
    assert line.section is Section.PURCHASES
    assert (line.card_last4, line.cardholder, line.external_ref) == ("2222", "JANE DOE", "7838")


def test_statement_line_is_frozen_and_compares_by_value() -> None:
    line = make_line()
    with pytest.raises(dataclasses.FrozenInstanceError):
        line.amount_cents = 0
    assert line == make_line()
    assert line != make_line(amount_cents=-451)
    assert hash(line) == hash(make_line())


def test_parsed_statement_fields_in_order() -> None:
    assert names(ParsedStatement) == [
        "parser_name",
        "institution",
        "account_type",
        "account_last4",
        "period_start",
        "period_end",
        "opening_balance_cents",
        "closing_balance_cents",
        "lines",
        "declared_section_totals",
    ]


def test_parsed_statement_field_types() -> None:
    assert typing.get_type_hints(ParsedStatement) == {
        "parser_name": str,
        "institution": str,
        "account_type": AccountType,
        "account_last4": str,
        "period_start": date,
        "period_end": date,
        "opening_balance_cents": int,
        "closing_balance_cents": int,
        "lines": list[StatementLine],
        "declared_section_totals": dict[Section, int],
    }


def test_parsed_statement_keeps_its_values() -> None:
    statement = make_statement(declared_section_totals={Section.PURCHASES: -450})
    assert statement.parser_name == "fake_bank"
    assert statement.institution == "Fake Bank"
    assert statement.account_type is AccountType.CREDIT_CARD
    assert statement.account_last4 == "1111"
    assert (statement.period_start, statement.period_end) == (date(2026, 1, 1), date(2026, 1, 31))
    assert statement.opening_balance_cents == -10000
    assert statement.closing_balance_cents == -10450
    assert statement.lines == [make_line()]
    assert statement.declared_section_totals == {Section.PURCHASES: -450}


def test_parsed_statement_totals_default_to_an_empty_dict_of_its_own() -> None:
    first = make_statement()
    second = make_statement()
    assert first.declared_section_totals == {}
    assert first.declared_section_totals is not second.declared_section_totals


def test_parsed_statement_needs_its_first_nine_fields() -> None:
    with pytest.raises(TypeError):
        ParsedStatement("fake_bank", "Fake Bank", AccountType.CHECKING, "1111")


def test_parsed_statement_is_frozen() -> None:
    statement = make_statement()
    with pytest.raises(dataclasses.FrozenInstanceError):
        statement.closing_balance_cents = 0
