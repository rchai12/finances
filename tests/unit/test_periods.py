from datetime import date

import pytest

from finances.domain.periods import MONTHS_MAX, months_ending, uncovered


def test_at_most_two_years() -> None:
    assert MONTHS_MAX == 24


def test_months_ending_in_a_month_oldest_first() -> None:
    assert months_ending(date(2026, 3, 17), 4) == [
        (date(2025, 12, 1), date(2025, 12, 31)),
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 28)),
        (date(2026, 3, 1), date(2026, 3, 31)),
    ]
    assert months_ending(date(2026, 3, 1), 1) == [(date(2026, 3, 1), date(2026, 3, 31))]
    assert len(months_ending(date(2026, 3, 1), 24)) == 24


@pytest.mark.parametrize("count", [0, -1, 25])
def test_a_count_out_of_range(count: int) -> None:
    with pytest.raises(ValueError) as caught:
        months_ending(date(2026, 3, 1), count)
    assert str(caught.value) == "count must be from 1 to 24"


def test_uncovered_names_the_accounts_missing_part_of_the_range() -> None:
    spans = {
        "whole": (date(2026, 3, 1), date(2026, 3, 31)),
        "Wider": (date(2026, 1, 9), date(2026, 5, 2)),
        "starts late": (date(2026, 3, 2), date(2026, 5, 2)),
        "Ends early": (date(2026, 1, 1), date(2026, 3, 30)),
        "no data": None,
        "after": (date(2026, 4, 1), date(2026, 4, 30)),
    }
    assert uncovered(spans, date(2026, 3, 1), date(2026, 3, 31)) == [
        "after",
        "Ends early",
        "no data",
        "starts late",
    ]
    assert uncovered({}, date(2026, 3, 1), date(2026, 3, 31)) == []
