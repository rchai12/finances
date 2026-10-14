import random
from datetime import date

import pytest

from finances.domain.matching import MATCH_MAX_DAYS, MatchItem, match_one_to_one


def item(key: int, cents: int, day: int) -> MatchItem:
    return MatchItem(key, cents, date(2026, 5, day))


def test_the_default_reach_is_five_days() -> None:
    assert MATCH_MAX_DAYS == 5
    assert type(MATCH_MAX_DAYS) is int


def test_a_match_item_is_frozen_and_has_three_fields() -> None:
    made = item(7, -450, 3)
    assert (made.key, made.amount_cents, made.day) == (7, -450, date(2026, 5, 3))
    with pytest.raises(AttributeError):
        made.key = 8  # type: ignore[misc]


def test_empty_lists() -> None:
    assert match_one_to_one([], []) == []
    assert match_one_to_one([item(1, -450, 3)], []) == []
    assert match_one_to_one([], [item(1, -450, 3)]) == []


def test_the_same_amount_on_the_same_day() -> None:
    assert match_one_to_one([item(10, -450, 3)], [item(77, -450, 3)]) == [(10, 77)]


@pytest.mark.parametrize("day", [10, 11, 14, 15, 20])
def test_days_apart_up_to_the_reach_in_either_direction(day: int) -> None:
    assert match_one_to_one([item(1, -450, 15)], [item(2, -450, day)]) == [(1, 2)]


@pytest.mark.parametrize("day", [1, 9, 21, 31])
def test_days_apart_beyond_the_reach(day: int) -> None:
    assert match_one_to_one([item(1, -450, 15)], [item(2, -450, day)]) == []


def test_the_reach_spans_a_month_and_a_year_end() -> None:
    left = [MatchItem(1, -450, date(2026, 12, 30))]
    right = [MatchItem(2, -450, date(2027, 1, 4))]
    assert match_one_to_one(left, right) == [(1, 2)]
    assert match_one_to_one(left, [MatchItem(2, -450, date(2027, 1, 5))]) == []


@pytest.mark.parametrize("cents", [-451, -449, 450, 0, -45000])
def test_amounts_must_be_equal_to_the_cent(cents: int) -> None:
    assert match_one_to_one([item(1, -450, 3)], [item(2, cents, 3)]) == []


def test_a_given_reach_replaces_the_default() -> None:
    left, right = [item(1, -450, 3)], [item(2, -450, 5)]
    assert match_one_to_one(left, right, max_days=1) == []
    assert match_one_to_one(left, right, max_days=2) == [(1, 2)]
    assert match_one_to_one(left, [item(2, -450, 3)], max_days=0) == [(1, 2)]
    assert match_one_to_one([item(1, -450, 1)], [item(2, -450, 31)], max_days=30) == [(1, 2)]


def test_each_item_is_used_once() -> None:
    left = [item(1, -450, 3), item(2, -450, 3)]
    assert match_one_to_one(left, [item(9, -450, 3)]) == [(1, 9)]
    right = [item(8, -450, 3), item(9, -450, 3)]
    assert match_one_to_one([item(1, -450, 3)], right) == [(1, 8)]
    assert match_one_to_one(left, right) == [(1, 8), (2, 9)]


def test_the_closest_day_wins() -> None:
    left = [item(1, -450, 10)]
    right = [item(7, -450, 14), item(8, -450, 11), item(9, -450, 6)]
    assert match_one_to_one(left, right) == [(1, 8)]


def test_closer_pairs_are_made_before_farther_ones() -> None:
    left = [item(1, -450, 10), item(2, -450, 13)]
    right = [item(8, -450, 13), item(9, -450, 16)]
    assert match_one_to_one(left, right) == [(2, 8)]
    right = [item(8, -450, 13), item(9, -450, 15)]
    assert match_one_to_one(left, right) == [(1, 9), (2, 8)]


def test_ties_go_to_the_earlier_left_item_then_the_earlier_right_item() -> None:
    left = [item(1, -450, 9), item(2, -450, 11)]
    assert match_one_to_one(left, [item(9, -450, 10)]) == [(1, 9)]
    assert match_one_to_one(list(reversed(left)), [item(9, -450, 10)]) == [(2, 9)]
    right = [item(8, -450, 12), item(9, -450, 8)]
    assert match_one_to_one([item(1, -450, 10)], right) == [(1, 8)]
    assert match_one_to_one([item(1, -450, 10)], list(reversed(right))) == [(1, 9)]


def test_pairs_come_back_in_the_order_of_the_left_list() -> None:
    left = [item(3, -100, 20), item(1, -200, 2), item(2, -300, 9)]
    right = [item(30, -300, 9), item(10, -100, 24), item(20, -200, 2)]
    assert match_one_to_one(left, right) == [(3, 10), (1, 20), (2, 30)]


def test_keys_are_returned_not_positions() -> None:
    left = [item(500, -100, 2), item(400, -100, 2)]
    right = [item(-7, -100, 2), item(0, -100, 2)]
    assert match_one_to_one(left, right) == [(500, -7), (400, 0)]


def test_different_amounts_are_matched_independently() -> None:
    left = [item(1, -450, 3), item(2, -1299, 3), item(3, -450, 4), item(4, 5000, 20)]
    right = [item(10, 5000, 22), item(11, -450, 4), item(12, -450, 3), item(13, -9999, 3)]
    assert match_one_to_one(left, right) == [(1, 12), (3, 11), (4, 10)]


def test_the_lists_are_not_changed() -> None:
    left = [item(2, -450, 4), item(1, -450, 3)]
    right = [item(9, -450, 3), item(8, -450, 4)]
    before = (list(left), list(right))
    match_one_to_one(left, right)
    assert (left, right) == before


def test_the_same_lists_always_give_the_same_pairs() -> None:
    generator = random.Random(8)
    left = [
        item(n, generator.choice([-100, -200, -300]), generator.randint(1, 28)) for n in range(40)
    ]
    right = [
        item(100 + n, generator.choice([-100, -200, -300]), generator.randint(1, 28))
        for n in range(40)
    ]
    first = match_one_to_one(left, right)
    assert first == match_one_to_one(list(left), list(right))
    assert len({pair[0] for pair in first}) == len(first)
    assert len({pair[1] for pair in first}) == len(first)
    by_key = {entry.key: entry for entry in left + right}
    for one, other in first:
        assert by_key[one].amount_cents == by_key[other].amount_cents
        assert abs((by_key[one].day - by_key[other].day).days) <= 5
    assert [pair[0] for pair in first] == [entry.key for entry in left if entry.key in dict(first)]
