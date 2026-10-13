from datetime import date

import pytest

from finances.ingest.parsers.helpers import collapse_ws, infer_year, parse_amount, parse_month_day
from finances.ingest.statement import StatementError

WRAP = (date(2025, 12, 24), date(2026, 1, 23))
DECEMBER = (date(2025, 12, 1), date(2025, 12, 28))
LEAP = (date(2024, 2, 1), date(2024, 2, 29))
NOT_LEAP = (date(2025, 2, 1), date(2025, 2, 28))
QUARTER = (date(2026, 7, 1), date(2026, 9, 30))
LONG = (date(2025, 1, 1), date(2026, 6, 30))
OUTSIDE = "date is outside the statement period"
AMBIGUOUS = "date matches more than one year"
UNRECOGNIZED = "unrecognized date text"

VALID_AMOUNTS = [
    ("$3.00", 300),
    ("36.49", 3649),
    ("-43.19", -4319),
    ("-$6,985.57", -698557),
    ("- $500.00", -50000),
    ("-   $1.00", -100),
    ("-\t$2.00", -200),
    ("  - $1.00  ", -100),
    ("+$759.22", 75922),
    ("+ $4,139.73", 413973),
    ("+0.00", 0),
    ("=$10.00", 1000),
    ("= $4,124.21", 412421),
    ("= - $5.00", -500),
    ("= + $5.00", 500),
    ("(12.34)", -1234),
    ("12.34-", -1234),
]
INVALID_AMOUNTS = [
    "",
    "=",
    "+",
    "-",
    "-$",
    "abc",
    "= abc",
    "$ 5",
    "5 +",
    "+-5",
    "+ -5",
    "+(5)",
    "+5-",
    "++5",
    "+ +5",
    "--5",
    "- -5",
    "- (5)",
    "==5",
    "= = 5",
    "+ = 5",
    "- = 5",
]
YEARS = [
    (WRAP, 12, 23, date(2025, 12, 23)),
    (WRAP, 12, 24, date(2025, 12, 24)),
    (WRAP, 1, 5, date(2026, 1, 5)),
    (WRAP, 1, 23, date(2026, 1, 23)),
    (WRAP, 1, 30, date(2026, 1, 30)),
    (WRAP, 10, 25, date(2025, 10, 25)),
    (DECEMBER, 12, 15, date(2025, 12, 15)),
    (DECEMBER, 1, 2, date(2026, 1, 2)),
    (DECEMBER, 1, 4, date(2026, 1, 4)),
    (LEAP, 2, 29, date(2024, 2, 29)),
    (QUARTER, 8, 17, date(2026, 8, 17)),
]
OUTSIDE_DATES = [
    (WRAP, 1, 31),
    (WRAP, 10, 24),
    (WRAP, 6, 15),
    (DECEMBER, 1, 5),
    (NOT_LEAP, 2, 29),
    (WRAP, 2, 30),
    (WRAP, 4, 31),
    (WRAP, 13, 1),
    (WRAP, 0, 5),
    (WRAP, 1, 0),
]
MONTH_DAY = [
    ("Dec 23", date(2025, 12, 23)),
    ("Jan 5", date(2026, 1, 5)),
    ("Jan 05", date(2026, 1, 5)),
    ("JAN 5", date(2026, 1, 5)),
    ("jan 5", date(2026, 1, 5)),
    ("Jan   5", date(2026, 1, 5)),
    ("  Jan 5  ", date(2026, 1, 5)),
    ("01/05", date(2026, 1, 5)),
    ("1/5", date(2026, 1, 5)),
    ("12/23", date(2025, 12, 23)),
    ("01-05", date(2026, 1, 5)),
    ("12-23", date(2025, 12, 23)),
]
UNRECOGNIZED_DATES = [
    "",
    "Jan",
    "5",
    "Jan5",
    "Janu 5",
    "January 5",
    "Xyz 5",
    "Jan 5th",
    "Jan -5",
    "Jan 123",
    "01/05/2026",
    "1/5/26",
    "01.05",
    "01/",
    "/05",
    "123/05",
    "١/٥",
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ACME COFFEE", "ACME COFFEE"),
        ("  ACME   COFFEE  ", "ACME COFFEE"),
        ("ACME\tCOFFEE\n#12", "ACME COFFEE #12"),
        ("   ", ""),
    ],
)
def test_collapse_ws(text: str, expected: str) -> None:
    assert collapse_ws(text) == expected


@pytest.mark.parametrize(("text", "expected"), VALID_AMOUNTS)
def test_parse_amount_valid(text: str, expected: int) -> None:
    result = parse_amount(text)
    assert result == expected
    assert type(result) is int


@pytest.mark.parametrize("text", INVALID_AMOUNTS)
def test_parse_amount_invalid(text: str) -> None:
    with pytest.raises(ValueError) as excinfo:
        parse_amount(text)
    assert str(excinfo.value) == "invalid money text"


@pytest.mark.parametrize(("period", "month", "day", "expected"), YEARS)
def test_infer_year(period: tuple[date, date], month: int, day: int, expected: date) -> None:
    assert infer_year(month, day, *period) == expected


@pytest.mark.parametrize(("period", "month", "day"), OUTSIDE_DATES)
def test_infer_year_outside_the_period(period: tuple[date, date], month: int, day: int) -> None:
    with pytest.raises(StatementError) as excinfo:
        infer_year(month, day, *period)
    assert str(excinfo.value) == OUTSIDE


def test_infer_year_refuses_to_guess_between_two_years() -> None:
    with pytest.raises(StatementError) as excinfo:
        infer_year(3, 15, *LONG)
    assert str(excinfo.value) == AMBIGUOUS


@pytest.mark.parametrize(("text", "expected"), MONTH_DAY)
def test_parse_month_day(text: str, expected: date) -> None:
    assert parse_month_day(text, *WRAP) == expected


@pytest.mark.parametrize("month", range(1, 13))
def test_parse_month_day_knows_every_month(month: int) -> None:
    name = date(2026, month, 15).strftime("%b")
    period = (date(2026, month, 1), date(2026, month, 28))
    assert parse_month_day(f"{name} 15", *period) == date(2026, month, 15)


@pytest.mark.parametrize("text", UNRECOGNIZED_DATES)
def test_parse_month_day_unrecognized(text: str) -> None:
    with pytest.raises(StatementError) as excinfo:
        parse_month_day(text, *WRAP)
    assert str(excinfo.value) == UNRECOGNIZED


@pytest.mark.parametrize("text", ["Jun 15", "06/15", "06-15", "Feb 30", "13/01", "00/10"])
def test_parse_month_day_outside_the_period(text: str) -> None:
    with pytest.raises(StatementError) as excinfo:
        parse_month_day(text, *WRAP)
    assert str(excinfo.value) == OUTSIDE
