from datetime import date

import pytest

from finances.domain.transfers import (
    TRANSFER_MAX_DAYS,
    Movement,
    clear_pairs,
    transfer_candidates,
)


def m(transaction_id: int, account_id: int, cents: int, day: int) -> Movement:
    return Movement(transaction_id, account_id, cents, date(2026, 5, day))


def test_the_reach_is_five_days() -> None:
    assert TRANSFER_MAX_DAYS == 5


def test_a_card_payment_from_checking() -> None:
    movements = [m(1, 1, -50000, 3), m(2, 2, 50000, 4), m(3, 2, -1250, 4)]
    assert transfer_candidates(movements) == [(1, 2)]


@pytest.mark.parametrize(
    "other",
    [
        m(2, 1, 50000, 4),
        m(2, 2, 49999, 4),
        m(2, 2, -50000, 4),
        m(2, 2, 50000, 9),
    ],
    ids=["same-account", "other-amount", "same-sign", "six-days-later"],
)
def test_not_a_transfer(other: Movement) -> None:
    assert transfer_candidates([m(1, 1, -50000, 3), other]) == []


@pytest.mark.parametrize("day", [8, 1, 3])
def test_up_to_five_days_either_way(day: int) -> None:
    assert transfer_candidates([m(1, 1, -500, 3), m(2, 2, 500, day)]) == [(1, 2)]


def test_a_rejected_pair_is_not_a_candidate() -> None:
    movements = [m(1, 1, -500, 3), m(2, 2, 500, 3), m(3, 3, 500, 4)]
    assert transfer_candidates(movements, {(1, 2)}) == [(1, 3)]


def test_candidates_come_by_outflow_then_inflow() -> None:
    movements = [m(9, 2, 500, 3), m(4, 1, -500, 3), m(2, 3, 500, 4), m(7, 3, -500, 2)]
    assert transfer_candidates(movements) == [(4, 2), (4, 9), (7, 9)]


def test_a_given_reach_replaces_the_default() -> None:
    movements = [m(1, 1, -500, 1), m(2, 2, 500, 3)]
    assert transfer_candidates(movements, max_days=1) == []
    assert transfer_candidates(movements, max_days=2) == [(1, 2)]


def test_only_pairs_with_one_choice_on_each_side_are_clear() -> None:
    candidates = [(1, 2), (3, 4), (3, 5), (6, 8), (7, 8), (9, 10)]
    assert clear_pairs(candidates) == [(1, 2), (9, 10)]


def test_no_candidates() -> None:
    assert transfer_candidates([]) == []
    assert clear_pairs([]) == []
