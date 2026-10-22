from datetime import date

import pytest

from finances.domain.refunds import REFUND_WINDOW_DAYS, Purchase, likely_purchase
from finances.domain.spending import (
    INCOME,
    KINDS,
    REFUND,
    SEARCH_KINDS,
    SPENDING,
    TRANSFER,
    UNSORTED_IN,
    Flow,
    is_refund,
)

DAY = date(2026, 6, 12)


def flow(cents: int, kind: str) -> Flow:
    return Flow(cents, DAY, kind, "Groceries", "Food", "FOOBAR GROCERY", "", "Test Card", "", "")


@pytest.mark.parametrize(
    ("cents", "kind", "refund"),
    [
        (599, SPENDING, True),
        (-599, SPENDING, False),
        (599, INCOME, False),
        (599, TRANSFER, False),
        (599, UNSORTED_IN, False),
    ],
)
def test_a_refund_is_money_back_on_spending(cents: int, kind: str, refund: bool) -> None:
    assert is_refund(flow(cents, kind)) is refund


def test_refund_is_a_kind_to_search_by_but_not_a_flow_kind() -> None:
    assert SEARCH_KINDS == (*KINDS, REFUND)
    assert REFUND == "refund" and REFUND not in KINDS
    assert REFUND_WINDOW_DAYS == 90


@pytest.mark.parametrize(
    ("purchases", "found"),
    [
        ([Purchase(1, date(2026, 4, 1), -1000), Purchase(2, date(2026, 5, 10), -2599)], 2),
        ([Purchase(1, date(2026, 5, 10), -500)], None),
        ([Purchase(1, date(2026, 6, 13), -2599)], None),
        ([Purchase(1, DAY, -599)], 1),
        ([Purchase(1, date(2026, 3, 14), -599)], 1),
        ([Purchase(1, date(2026, 3, 13), -599)], None),
        ([Purchase(3, date(2026, 5, 10), -700), Purchase(5, date(2026, 5, 10), -700)], 5),
        ([Purchase(1, date(2026, 5, 10), 2599)], None),
        ([], None),
    ],
    ids=[
        "the latest that fits",
        "smaller than the refund",
        "after the refund",
        "the same day",
        "90 days before",
        "91 days before",
        "a tie goes to the newest",
        "money in is no purchase",
        "nothing",
    ],
)
def test_the_likely_purchase(purchases: list[Purchase], found: int | None) -> None:
    assert likely_purchase(DAY, 599, purchases) == found
