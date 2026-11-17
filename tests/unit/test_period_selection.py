from datetime import date

import pytest

from finances.domain import periods


@pytest.mark.parametrize(
    ("month", "start", "end", "expected"),
    [
        (None, None, None, (date(2024, 2, 1), date(2024, 2, 29))),
        ("2025-02", None, None, (date(2025, 2, 1), date(2025, 2, 28))),
        ("2025-12", None, None, (date(2025, 12, 1), date(2025, 12, 31))),
        ("2026-01", None, None, (date(2026, 1, 1), date(2026, 1, 31))),
        (None, date(2025, 1, 2), date(2025, 1, 3), (date(2025, 1, 2), date(2025, 1, 3))),
        (None, date(2025, 1, 3), date(2025, 1, 2), (date(2025, 1, 3), date(2025, 1, 2))),
    ],
    ids=["leap-default", "month", "december", "january", "range", "reversed-deferred"],
)
def test_select_period(month, start, end, expected):
    result = periods.select_period(month=month, start=start, end=end, today=date(2024, 2, 15))
    assert (result.start, result.end) == expected


@pytest.mark.parametrize(
    ("month", "start", "code", "message"),
    [
        ("bad", date(2024, 1, 1), "conflict", "month cannot accompany endpoints"),
        (None, date(2024, 1, 1), "incomplete", "both endpoints are required"),
        ("", None, "month", "month must be a year and month, like 2026-05"),
    ],
    ids=["conflict-first", "incomplete", "empty-is-month"],
)
def test_selection_errors(month, start, code, message):
    with pytest.raises(periods.PeriodError) as stopped:
        periods.select_period(month=month, start=start, end=None, today=date(2024, 2, 15))
    assert stopped.value.code == code
    assert str(stopped.value) == message


@pytest.mark.parametrize("month", [None, "2024-02"], ids=["default", "explicit"])
def test_first_day(month):
    assert periods.first_day(month, today=date(2024, 2, 15)) == date(2024, 2, 1)
