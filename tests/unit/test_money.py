import pytest

from finances.domain.money import format_cents, parse_money

VALID = [
    ("12.34", 1234),
    ("-12.34", -1234),
    ("$1,234.56", 123456),
    ("(12.34)", -1234),
    ("12.34-", -1234),
    ("  7 ", 700),
    ("-$12.34", -1234),
    ("($1,234.56)", -123456),
    ("$12.34-", -1234),
    ("0", 0),
    ("-0.00", 0),
    (".5", 50),
    ("12.3", 1230),
    ("1.15", 115),
    ("0.29", 29),
    ("4.35", 435),
    ("$0.07", 7),
    ("1,000,000.00", 100000000),
]
INVALID = [
    "",
    "   ",
    "abc",
    "12.345",
    "12.",
    "1,23.45",
    "1234,567",
    "12,34",
    "1.2.3",
    "$",
    "-",
    "--5",
    "(5",
    "5)",
    "()",
    "(-5)",
    "-(5)",
    "-5-",
    "$-5",
    "$$5",
    "+5",
    "1 000",
    "$ 5",
    "- 5",
    "1e3",
    "1_000",
    "0x10",
    "NaN",
    "Infinity",
]

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


@pytest.mark.parametrize(("text", "expected"), VALID)
def test_parse_money_valid(text: str, expected: int) -> None:
    assert parse_money(text) == expected


@pytest.mark.parametrize("text", INVALID)
def test_parse_money_invalid(text: str) -> None:
    with pytest.raises(ValueError):
        parse_money(text)


def test_parse_money_error_does_not_echo_input() -> None:
    with pytest.raises(ValueError) as excinfo:
        parse_money("12.345")
    assert str(excinfo.value) == "invalid money text"


def test_parse_money_rejects_non_ascii_digits() -> None:
    with pytest.raises(ValueError):
        parse_money("١٢")


def test_parse_money_returns_int() -> None:
    assert type(parse_money("12.34")) is int


@pytest.mark.parametrize(("cents", "expected"), FORMAT)
def test_format_cents(cents: int, expected: str) -> None:
    assert format_cents(cents) == expected


def test_format_cents_returns_str() -> None:
    assert type(format_cents(1)) is str


@pytest.mark.parametrize("n", [0, 1, -1, 99, -99, 100, 12345, -12345, 100000000])
def test_round_trip(n: int) -> None:
    assert parse_money(format_cents(n)) == n
