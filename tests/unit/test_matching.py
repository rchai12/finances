import random
from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from finances.domain.matching import MATCH_MAX_DAYS, MatchItem, match_one_to_one, period_zone


def item(key: int, cents: int, day: int, zone: int = 0) -> MatchItem:
    return MatchItem(key, cents, date(2026, 5, day), zone)


def test_the_default_reach_is_five_days() -> None:
    assert MATCH_MAX_DAYS == 5
    assert type(MATCH_MAX_DAYS) is int


def test_a_match_item_is_frozen_and_its_zone_defaults_to_zero() -> None:
    made = item(7, -450, 3)
    assert (made.key, made.amount_cents, made.day, made.zone) == (7, -450, date(2026, 5, 3), 0)
    assert MatchItem(7, -450, date(2026, 5, 3), 4).zone == 4
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


def test_the_most_pairs_are_made() -> None:
    left = [item(1, -450, 10), item(2, -450, 13)]
    right = [item(8, -450, 13), item(9, -450, 16)]
    assert match_one_to_one(left, right) == [(1, 8), (2, 9)]
    left = [item(1, -450, 21), item(2, -450, 26)]
    right = [item(8, -450, 24), item(9, -450, 31)]
    assert match_one_to_one(left, right) == [(1, 8), (2, 9)]


def test_among_the_most_pairs_the_fewest_days_apart_win() -> None:
    left = [item(1, -450, 10), item(2, -450, 20)]
    right = [item(8, -450, 14), item(9, -450, 12)]
    assert match_one_to_one(left, right) == [(1, 9)]
    left = [item(1, -450, 5), item(2, -450, 9)]
    right = [item(8, -450, 7), item(9, -450, 11), item(7, -450, 13)]
    assert match_one_to_one(left, right) == [(1, 8), (2, 9)]


def test_equally_good_pairings_pair_the_earlier_items() -> None:
    left = [item(1, -450, 10), item(2, -450, 13)]
    right = [item(8, -450, 13), item(9, -450, 15)]
    assert match_one_to_one(left, right) == [(1, 8), (2, 9)]


def test_ties_go_to_the_earlier_day_then_the_earlier_position() -> None:
    left = [item(1, -450, 9), item(2, -450, 11)]
    assert match_one_to_one(left, [item(9, -450, 10)]) == [(1, 9)]
    assert match_one_to_one(list(reversed(left)), [item(9, -450, 10)]) == [(1, 9)]
    right = [item(8, -450, 12), item(9, -450, 8)]
    assert match_one_to_one([item(1, -450, 10)], right) == [(1, 9)]
    assert match_one_to_one([item(1, -450, 10)], list(reversed(right))) == [(1, 9)]
    same_day = [item(1, -450, 3), item(2, -450, 3)]
    assert match_one_to_one(same_day, [item(9, -450, 3)]) == [(1, 9)]
    assert match_one_to_one(list(reversed(same_day)), [item(9, -450, 3)]) == [(2, 9)]
    later = [item(1, -450, 15), item(2, -450, 15)]
    passed_over = [item(7, -450, 1), item(8, -450, 18)]
    assert match_one_to_one(later, passed_over) == [(1, 8)]
    assert match_one_to_one(list(reversed(later)), passed_over) == [(2, 8)]


def test_a_pair_within_one_zone_beats_a_closer_pair_across_zones() -> None:
    left = [item(1, -450, 10, zone=1)]
    assert match_one_to_one(left, [item(8, -450, 9, zone=0), item(9, -450, 13, zone=1)]) == [(1, 9)]
    assert match_one_to_one(left, [item(8, -450, 7, zone=0), item(9, -450, 13, zone=1)]) == [(1, 9)]
    assert match_one_to_one(left, [item(8, -450, 9, zone=0)]) == [(1, 8)]


def test_more_pairs_beat_pairs_within_one_zone() -> None:
    left = [item(1, -450, 10, zone=1), item(2, -450, 14, zone=1)]
    right = [item(8, -450, 12, zone=1), item(9, -450, 17, zone=2)]
    assert match_one_to_one(left, right) == [(1, 8), (2, 9)]
    left = [item(1, -450, 10, zone=1), item(2, -450, 5, zone=0)]
    right = [item(8, -450, 9, zone=1), item(9, -450, 15, zone=2)]
    assert match_one_to_one(left, right) == [(1, 9), (2, 8)]


@pytest.mark.parametrize(
    ("day", "zone"),
    [(1, 0), (4, 0), (5, 1), (12, 1), (13, 2), (14, 2), (15, 3), (20, 3), (21, 4), (31, 4)],
)
def test_the_zone_of_a_day(day: int, zone: int) -> None:
    periods = [(date(2026, 5, 15), date(2026, 5, 20)), (date(2026, 5, 5), date(2026, 5, 12))]
    assert period_zone(date(2026, 5, day), periods) == zone


def test_without_periods_every_day_is_zone_zero() -> None:
    assert period_zone(date(2026, 5, 1), []) == 0


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


# Properties over generated lists. Small lists, so every pairing can be tried. Zones come
# from one statement period of a week, as the services compute them.

PERIOD = [(date(2026, 5, 8), date(2026, 5, 14))]
side = st.lists(
    st.tuples(st.sampled_from([-450, -1299]), st.integers(1, 20)), min_size=0, max_size=5
)


def items(raw: list[tuple[int, int]], first_key: int) -> list[MatchItem]:
    return [
        item(first_key + n, cents, day, period_zone(date(2026, 5, day), PERIOD))
        for n, (cents, day) in enumerate(raw)
    ]


def score(pairs: list[tuple[MatchItem, MatchItem]]) -> tuple[int, int, int]:
    """Pairs, pairs within one zone, and total days apart."""
    return (
        len(pairs),
        sum(one.zone == other.zone for one, other in pairs),
        sum(abs((one.day - other.day).days) for one, other in pairs),
    )


def best_possible(left: list[MatchItem], right: list[MatchItem]) -> tuple[int, int, int]:
    """The best score of any pairing, found by trying every pairing."""
    best = (0, 0, 0)

    def walk(position: int, used: frozenset[int], chosen: list) -> None:
        nonlocal best
        found = score(chosen)
        if (found[0], found[1], -found[2]) > (best[0], best[1], -best[2]):
            best = found
        if position == len(left):
            return
        walk(position + 1, used, chosen)
        for index, other in enumerate(right):
            gap = abs((left[position].day - other.day).days)
            if index not in used and other.amount_cents == left[position].amount_cents:
                if gap <= MATCH_MAX_DAYS:
                    walk(position + 1, used | {index}, [*chosen, (left[position], other)])

    walk(0, frozenset(), [])
    return best


def scored(pairs: list[tuple[int, int]], everything: list[MatchItem]) -> tuple[int, int, int]:
    by_key = {entry.key: entry for entry in everything}
    return score([(by_key[a], by_key[b]) for a, b in pairs])


@settings(max_examples=300)
@given(side, side)
def test_the_pairing_is_valid_and_the_best_possible(
    raw_left: list[tuple[int, int]], raw_right: list[tuple[int, int]]
) -> None:
    left, right = items(raw_left, 1), items(raw_right, 100)
    pairs = match_one_to_one(left, right)
    by_key = {entry.key: entry for entry in left + right}
    assert len({a for a, _ in pairs}) == len({b for _, b in pairs}) == len(pairs)
    for one, other in pairs:
        assert by_key[one].amount_cents == by_key[other].amount_cents
        assert abs((by_key[one].day - by_key[other].day).days) <= MATCH_MAX_DAYS
    assert [a for a, _ in pairs] == [entry.key for entry in left if entry.key in dict(pairs)]
    assert scored(pairs, left + right) == best_possible(left, right)


@settings(max_examples=200)
@given(side, side, st.randoms(use_true_random=False))
def test_the_order_of_the_lists_does_not_change_how_good_the_pairing_is(
    raw_left: list[tuple[int, int]], raw_right: list[tuple[int, int]], shuffler: random.Random
) -> None:
    left, right = items(raw_left, 1), items(raw_right, 100)
    shuffled_left, shuffled_right = list(left), list(right)
    shuffler.shuffle(shuffled_left)
    shuffler.shuffle(shuffled_right)
    expected = scored(match_one_to_one(left, right), left + right)
    assert scored(match_one_to_one(shuffled_left, shuffled_right), left + right) == expected
