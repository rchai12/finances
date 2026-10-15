from datetime import date

import pytest

from finances.domain.periods import statement_gaps


def d(month: int, day: int) -> date:
    return date(2026, month, day)


@pytest.mark.parametrize(
    ("periods", "gaps"),
    [
        ([], []),
        ([(d(1, 1), d(1, 31))], []),
        ([(d(1, 1), d(1, 31)), (d(2, 1), d(2, 28))], []),
        ([(d(1, 1), d(1, 31)), (d(3, 1), d(3, 31))], [(d(2, 1), d(2, 28))]),
        ([(d(3, 5), d(4, 4)), (d(1, 5), d(2, 4))], [(d(2, 5), d(3, 4))]),
        ([(d(1, 1), d(1, 31)), (d(1, 15), d(2, 14)), (d(2, 16), d(3, 1))], [(d(2, 15), d(2, 15))]),
        ([(d(1, 1), d(3, 31)), (d(2, 1), d(2, 28)), (d(4, 2), d(4, 30))], [(d(4, 1), d(4, 1))]),
    ],
    ids=[
        "none",
        "one",
        "back-to-back",
        "a-month-missing",
        "unsorted",
        "overlap-then-one-day",
        "inside-another",
    ],
)
def test_statement_gaps(periods: list[tuple[date, date]], gaps: list[tuple[date, date]]) -> None:
    assert statement_gaps(periods) == gaps
