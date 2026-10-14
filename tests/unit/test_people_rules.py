import pytest

from finances.domain.people import (
    JOINT,
    NAME_LIMIT,
    RESERVED_NAMES,
    normalize_cardholder,
    person_for,
    validate_person_name,
)

ALIASES = {"SAM DOE": "Sam", "ALEX Q DOE": "Alex"}


def test_the_constants() -> None:
    assert (JOINT, RESERVED_NAMES, NAME_LIMIT) == ("Joint", ("joint", "unassigned"), 100)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sam Doe", "SAM DOE"),
        ("  sam   doe ", "SAM DOE"),
        ("SAM\tDOE", "SAM DOE"),
        ("o'neil-smith", "O'NEIL-SMITH"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalize_cardholder(text: str, expected: str) -> None:
    assert normalize_cardholder(text) == expected


@pytest.mark.parametrize(
    ("name", "expected"), [("Alex", "Alex"), ("  Sam Doe ", "Sam Doe"), ("x" * 100, "x" * 100)]
)
def test_usable_person_names(name: str, expected: str) -> None:
    assert validate_person_name(name) == expected


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("", "a person's name must be 1 to 100 characters"),
        ("   ", "a person's name must be 1 to 100 characters"),
        ("x" * 101, "a person's name must be 1 to 100 characters"),
        ("joint", "joint and unassigned are reserved names"),
        (" JOINT ", "joint and unassigned are reserved names"),
        ("Unassigned", "joint and unassigned are reserved names"),
    ],
)
def test_unusable_person_names(name: str, message: str) -> None:
    with pytest.raises(ValueError) as caught:
        validate_person_name(name)
    assert str(caught.value) == message


@pytest.mark.parametrize(
    ("cardholder", "owner", "expected"),
    [
        ("SAM DOE", "Alex", "Sam"),
        ("sam  doe", JOINT, "Sam"),
        ("SAM DOE", None, "Sam"),
        ("PAT DOE", "Alex", "Alex"),
        ("PAT DOE", JOINT, JOINT),
        ("PAT DOE", None, None),
        (None, "Alex", "Alex"),
        (None, JOINT, JOINT),
        (None, None, None),
        ("", "Alex", "Alex"),
    ],
)
def test_person_for(cardholder: str | None, owner: str | None, expected: str | None) -> None:
    assert person_for(cardholder, owner, ALIASES) == expected


def test_person_for_with_no_aliases() -> None:
    assert person_for("SAM DOE", "Alex", {}) == "Alex"
