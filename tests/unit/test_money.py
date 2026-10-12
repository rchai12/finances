import pytest

from finances.domain.money import format_cents

FORMAT = [
    (123456, "$1,234.56"),
    (-1234, "-$12.34"),
    (0, "$0.00"),
    (5, "$0.05"),
    (-5, "-$0.05"),
    (100, "$1.00"),
    (-100, "-$1.00"),
    (99, "$0.99"),
    (10, "$0.10"),
    (100000000, "$1,000,000.00"),
    (-100000000, "-$1,000,000.00"),
    (123456789012, "$1,234,567,890.12"),
    (9007199254740993, "$90,071,992,547,409.93"),
]


@pytest.mark.parametrize(("cents", "expected"), FORMAT)
def test_format_cents(cents: int, expected: str) -> None:
    assert format_cents(cents) == expected


def test_format_cents_returns_str() -> None:
    assert type(format_cents(1)) is str
