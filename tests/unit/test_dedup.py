import re
from datetime import date

import pytest

from finances.ingest.dedup import fingerprint_lines
from finances.ingest.statement import Section, StatementLine

COFFEE = StatementLine(date(2026, 1, 5), None, "ACME COFFEE #12", -450, Section.PURCHASES)
GROCERY = StatementLine(
    date(2026, 1, 6),
    date(2026, 1, 4),
    "FOOBAR GROCERY",
    -2599,
    Section.PURCHASES,
    card_last4="2222",
    cardholder="JANE DOE",
    external_ref="7838",
)
COFFEE_FIRST = "8308861cce52605968528ac9ec9df4dc7e93fc406fae8ceed2c1fc905d98324b"
COFFEE_SECOND = "dc7320935e980c403d9e15b3d99e1e558129fd1f692624bb1cffb7e7cf8bde95"
GROCERY_FIRST = "d753f7f504babf6834269807c6d163b18bff87556393f29f56f77f027469ac89"
UNICODE_FIRST = "5eebeb35c6fcaf97ac1f556500cc7d24fd5c338fd5237f4b2c7e09a01459f995"


def changed(line: StatementLine, **changes: object) -> StatementLine:
    values = {
        "posted_date": line.posted_date,
        "transaction_date": line.transaction_date,
        "description": line.description,
        "amount_cents": line.amount_cents,
        "section": line.section,
        "card_last4": line.card_last4,
        "cardholder": line.cardholder,
        "external_ref": line.external_ref,
    }
    values.update(changes)
    return StatementLine(**values)


def one(account_id: int, line: StatementLine) -> str:
    return fingerprint_lines(account_id, [line])[0]


def test_no_lines_gives_no_fingerprints() -> None:
    assert fingerprint_lines(7, []) == []


def test_one_fingerprint_per_line_in_order() -> None:
    result = fingerprint_lines(7, [COFFEE, GROCERY, COFFEE])
    assert type(result) is list
    assert result == [COFFEE_FIRST, GROCERY_FIRST, COFFEE_SECOND]


def test_a_fingerprint_is_64_lower_case_hex_characters() -> None:
    for fingerprint in fingerprint_lines(7, [COFFEE, GROCERY]):
        assert type(fingerprint) is str
        assert re.fullmatch(r"[0-9a-f]{64}", fingerprint)


def test_the_exact_values_never_change() -> None:
    assert one(7, COFFEE) == COFFEE_FIRST
    assert one(7, GROCERY) == GROCERY_FIRST
    unicode_line = changed(
        COFFEE, posted_date=date(2026, 1, 7), description="Café Zürich Straße", amount_cents=1500
    )
    assert one(7, unicode_line) == UNICODE_FIRST


def test_the_same_statement_twice_gives_the_same_fingerprints() -> None:
    lines = [COFFEE, GROCERY, COFFEE, COFFEE]
    assert fingerprint_lines(7, lines) == fingerprint_lines(7, list(lines))


def test_identical_lines_get_different_fingerprints() -> None:
    result = fingerprint_lines(7, [COFFEE, COFFEE, COFFEE, GROCERY, GROCERY])
    assert len(set(result)) == 5
    assert result[:2] == [COFFEE_FIRST, COFFEE_SECOND]


def test_repeats_are_counted_per_line_not_per_position() -> None:
    assert fingerprint_lines(7, [GROCERY, COFFEE, GROCERY, COFFEE]) == [
        GROCERY_FIRST,
        COFFEE_FIRST,
        fingerprint_lines(7, [GROCERY, GROCERY])[1],
        COFFEE_SECOND,
    ]


def test_each_call_counts_repeats_from_zero() -> None:
    fingerprint_lines(7, [COFFEE, COFFEE])
    assert fingerprint_lines(7, [COFFEE]) == [COFFEE_FIRST]


@pytest.mark.parametrize(
    "description",
    ["acme coffee #12", "  ACME COFFEE #12  ", "ACME   COFFEE\t#12", "Acme\nCoffee #12"],
)
def test_case_and_spacing_of_the_description_do_not_matter(description: str) -> None:
    assert one(7, changed(COFFEE, description=description)) == COFFEE_FIRST


@pytest.mark.parametrize(
    "changes",
    [
        {"posted_date": date(2026, 1, 6)},
        {"amount_cents": -451},
        {"amount_cents": 450},
        {"description": "ACME COFFEE #13"},
        {"description": "ACMECOFFEE #12"},
        {"card_last4": "2222"},
        {"external_ref": "7838"},
    ],
)
def test_each_identifying_field_changes_the_fingerprint(changes: dict) -> None:
    assert one(7, changed(COFFEE, **changes)) != COFFEE_FIRST


@pytest.mark.parametrize(
    "changes",
    [
        {"transaction_date": date(2026, 1, 3)},
        {"section": Section.FEES},
        {"cardholder": "JOHN DOE"},
    ],
)
def test_other_fields_do_not_change_the_fingerprint(changes: dict) -> None:
    assert one(7, changed(COFFEE, **changes)) == COFFEE_FIRST


def test_lines_that_differ_only_in_other_fields_count_as_repeats() -> None:
    result = fingerprint_lines(7, [COFFEE, changed(COFFEE, section=Section.FEES)])
    assert result == [COFFEE_FIRST, COFFEE_SECOND]


def test_the_account_changes_the_fingerprint() -> None:
    assert one(8, COFFEE) != COFFEE_FIRST
    assert one(70, COFFEE) != one(7, COFFEE)


def test_a_value_cannot_slide_between_fields() -> None:
    with_card = changed(COFFEE, card_last4="1234", external_ref=None)
    with_ref = changed(COFFEE, card_last4=None, external_ref="1234")
    assert one(7, with_card) != one(7, with_ref)
    assert one(7, changed(COFFEE, description="A", external_ref="B")) != one(
        7, changed(COFFEE, description="A B", external_ref=None)
    )


def test_the_lines_are_not_changed() -> None:
    lines = [COFFEE, GROCERY]
    fingerprint_lines(7, lines)
    assert lines == [COFFEE, GROCERY]
