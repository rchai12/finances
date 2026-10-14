from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from finances.domain.money import format_cents, parse_money
from finances.ingest.parsers.helpers import (
    EARLY_DAYS,
    LATE_DAYS,
    infer_year,
    parse_amount,
    parse_month_day,
)
from finances.ingest.statement import StatementError

cents = st.integers(-(10**13), 10**13)
sizes = st.integers(0, 10**13)
periods = st.tuples(st.dates(date(2000, 1, 1), date(2098, 12, 1)), st.integers(20, 40))


def plain(value: int) -> str:
    return f"{value // 100}.{value % 100:02d}"


@settings(max_examples=500)
@given(cents)
def test_formatted_money_reads_back_to_the_same_cents(value: int) -> None:
    assert parse_money(format_cents(value)) == value


@settings(max_examples=300)
@given(sizes)
def test_every_negative_form_gives_the_same_cents(value: int) -> None:
    text = plain(value)
    assert parse_money(f"({text})") == -value
    assert parse_money(f"{text}-") == -value
    assert parse_money(f"-{text}") == -value
    assert parse_money(f"-${text}") == -value
    assert parse_amount(f"- ${text}") == -value
    assert parse_amount(f"+ ${text}") == value
    assert parse_amount(f"= ${text}") == value


@settings(max_examples=300)
@given(sizes)
def test_thousands_separators_change_nothing(value: int) -> None:
    dollars, rest = divmod(value, 100)
    assert parse_money(f"${dollars:,}.{rest:02d}") == value


@settings(max_examples=200)
@given(st.integers(0, 10**9), st.integers(3, 6))
def test_three_or_more_decimals_are_refused(whole: int, places: int) -> None:
    with pytest.raises(ValueError):
        parse_money(f"{whole}." + "5" * places)


@settings(max_examples=500)
@given(st.text(max_size=16))
def test_any_text_gives_cents_or_a_value_error(text: str) -> None:
    try:
        value = parse_money(text)
    except ValueError:
        return
    assert type(value) is int


@settings(max_examples=500)
@given(st.text(alphabet="0123456789.,$()-+= ", max_size=16))
def test_any_amount_text_gives_cents_or_a_value_error(text: str) -> None:
    try:
        value = parse_amount(text)
    except ValueError:
        return
    assert type(value) is int


@settings(max_examples=500)
@given(periods, st.integers(-EARLY_DAYS, 40 + LATE_DAYS))
def test_a_day_near_the_period_gets_its_own_year(period: tuple[date, int], offset: int) -> None:
    start, length = period
    end = start + timedelta(days=length)
    day = start + timedelta(days=offset)
    if day > end + timedelta(days=LATE_DAYS):
        return
    assert infer_year(day.month, day.day, start, end) == day


@settings(max_examples=300)
@given(periods, st.integers(-EARLY_DAYS, 40 + LATE_DAYS))
def test_every_printed_form_of_a_day_gives_the_same_date(
    period: tuple[date, int], offset: int
) -> None:
    start, length = period
    end = start + timedelta(days=length)
    day = start + timedelta(days=offset)
    if day > end + timedelta(days=LATE_DAYS):
        return
    for text in (day.strftime("%b %d"), day.strftime("%m/%d"), f"{day.month}-{day.day}"):
        assert parse_month_day(text, start, end) == day


@settings(max_examples=300)
@given(periods, st.integers(1, 200))
def test_a_day_too_far_from_the_period_is_refused(period: tuple[date, int], beyond: int) -> None:
    start, length = period
    end = start + timedelta(days=length)
    for day in (
        start - timedelta(days=EARLY_DAYS + beyond),
        end + timedelta(days=LATE_DAYS + beyond),
    ):
        if abs((day - start).days) > 300:
            continue
        with pytest.raises(StatementError, match="^date is outside the statement period$"):
            infer_year(day.month, day.day, start, end)
