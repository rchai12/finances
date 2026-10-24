import pytest

from finances.domain.money import decimal_text


@pytest.mark.parametrize(
    ("cents", "text"),
    [
        (0, "0.00"),
        (5, "0.05"),
        (-5, "-0.05"),
        (99, "0.99"),
        (-100, "-1.00"),
        (-1234, "-12.34"),
        (123456, "1234.56"),
        (100000000, "1000000.00"),
        (900719925474099301, "9007199254740993.01"),
    ],
)
def test_cents_as_plain_decimal_dollars(cents: int, text: str) -> None:
    assert decimal_text(cents) == text
