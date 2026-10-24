from datetime import date

import pytest

from finances.domain.shared import Owed, Settlement, Share, balances, half_share, signed_share

DAY = date(2026, 5, 20)
ZERO = "a transaction of zero cannot be shared"
SIZE = "a share must be more than zero and at most the transaction's amount"


@pytest.mark.parametrize(
    ("amount", "owed"),
    [(-2000, 1000), (-2001, 1000), (2001, -1000), (-1, 0)],
)
def test_half_a_share(amount: int, owed: int) -> None:
    assert half_share(amount) == owed


@pytest.mark.parametrize(
    ("amount", "size", "owed"),
    [(-2000, 1200, 1200), (2000, 500, -500), (-2000, 2000, 2000), (-2000, 1, 1)],
)
def test_a_share_of_a_size(amount: int, size: int, owed: int) -> None:
    assert signed_share(amount, size) == owed


@pytest.mark.parametrize(
    ("work", "message"),
    [
        (lambda: half_share(0), ZERO),
        (lambda: signed_share(0, 100), ZERO),
        (lambda: signed_share(-2000, 2001), SIZE),
        (lambda: signed_share(2000, 2001), SIZE),
        (lambda: signed_share(-2000, 0), SIZE),
        (lambda: signed_share(-2000, -100), SIZE),
    ],
)
def test_a_share_that_is_refused(work, message: str) -> None:
    with pytest.raises(ValueError) as raised:
        work()
    assert str(raised.value) == message


def test_no_shares_owe_nothing() -> None:
    assert balances([], []) == []


def test_shares_net_against_each_other() -> None:
    shares = [
        Share(1, "Sam", "Alex", 1000),
        Share(2, "Sam", "Alex", -300),
        Share(3, "Alex", "Sam", 200),
    ]
    assert balances(shares, []) == [Owed("Alex", "Sam", 500)]


@pytest.mark.parametrize(
    ("paid", "owed"),
    [
        (500, []),
        (200, [Owed("Alex", "Sam", 300)]),
        (700, [Owed("Sam", "Alex", 200)]),
    ],
)
def test_a_settlement_pays_it_down(paid: int, owed: list[Owed]) -> None:
    shares = [Share(1, "Sam", "Alex", 1000), Share(2, "Alex", "Sam", 500)]
    assert balances(shares, [Settlement(1, "Alex", "Sam", paid, DAY)]) == owed


def test_a_settlement_the_other_way_adds_to_it() -> None:
    shares = [Share(1, "Sam", "Alex", 1000)]
    assert balances(shares, [Settlement(1, "Sam", "Alex", 250, DAY)]) == [Owed("Alex", "Sam", 1250)]


def test_three_people_by_debtor_then_creditor() -> None:
    shares = [
        Share(1, "Sam", "Alex", 1000),
        Share(2, "Sam", "Kai", 400),
        Share(3, "Kai", "Alex", 250),
    ]
    assert balances(shares, []) == [
        Owed("Alex", "Kai", 250),
        Owed("Alex", "Sam", 1000),
        Owed("Kai", "Sam", 400),
    ]
