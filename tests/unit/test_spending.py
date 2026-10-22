from datetime import date

import pytest

from finances.domain.models import Category
from finances.domain.spending import (
    BY,
    INCOME,
    SPENDING,
    TRANSFER,
    UNSORTED_IN,
    Flow,
    SpendingLine,
    SpendingSummary,
    flow_kind,
    month_bounds,
    month_range,
    spending_lines,
    summarize,
)

DINING = Category(10, "Dining", 1, False, False, False)
PAYCHECK = Category(20, "Paycheck", 2, False, True, False)
CARD_PAYMENT = Category(30, "Credit Card Payment", 3, True, False, False)


def flow(
    cents: int, kind: str = SPENDING, category: str = "Dining", merchant: str = "ACME"
) -> Flow:
    return Flow(
        amount_cents=cents,
        day=date(2026, 5, 1),
        kind=kind,
        category=category,
        group="Food",
        merchant=merchant,
        person="Unassigned",
        account="Test Card",
        bank="Test Bank",
        card="No card",
    )


@pytest.mark.parametrize(
    ("cents", "paired", "category", "kind"),
    [
        (-500, False, DINING, SPENDING),
        (500, False, DINING, SPENDING),
        (-500, False, None, SPENDING),
        (500, False, None, UNSORTED_IN),
        (300000, False, PAYCHECK, INCOME),
        (-50000, False, CARD_PAYMENT, TRANSFER),
        (-50000, True, None, TRANSFER),
        (300000, True, PAYCHECK, TRANSFER),
    ],
    ids=[
        "a-purchase",
        "a-refund",
        "uncategorized-out",
        "uncategorized-in",
        "income",
        "transfer-category",
        "paired",
        "paired-wins",
    ],
)
def test_flow_kind(cents: int, paired: bool, category: Category | None, kind: str) -> None:
    assert flow_kind(cents, paired=paired, category=category) == kind


def test_the_ways_to_group() -> None:
    assert BY == ("category", "group", "merchant", "person", "account", "bank", "card")


def test_refunds_net_and_the_largest_comes_first() -> None:
    flows = [
        flow(-450, category="Coffee & Dessert"),
        flow(-2599, category="Groceries"),
        flow(599, category="Groceries"),
        flow(-1250, category="Coffee & Dessert"),
        flow(-12000, category="Utilities & Internet"),
        flow(300000, INCOME, category="Paycheck"),
        flow(-50000, TRANSFER, category="Uncategorized"),
        flow(2500, UNSORTED_IN, category="Uncategorized"),
    ]
    assert spending_lines(flows, "category") == [
        SpendingLine("Utilities & Internet", 12000, 1),
        SpendingLine("Groceries", 2000, 2, refunds_cents=599),
        SpendingLine("Coffee & Dessert", 1700, 2),
    ]


def test_a_tie_goes_by_name_ignoring_case_and_a_refund_can_win() -> None:
    flows = [
        flow(-500, merchant="beta"),
        flow(-500, merchant="Alpha"),
        flow(700, merchant="QUUX"),
        flow(-200, merchant="QUUX"),
    ]
    assert spending_lines(flows, "merchant") == [
        SpendingLine("Alpha", 500, 1),
        SpendingLine("beta", 500, 1),
        SpendingLine("QUUX", -500, 2, refunds_cents=700),
    ]


def test_group_by_another_field() -> None:
    assert spending_lines([flow(-450), flow(-50)], "group") == [SpendingLine("Food", 500, 2)]


def test_an_unknown_way_to_group() -> None:
    with pytest.raises(ValueError) as caught:
        spending_lines([], "vendor")
    assert str(caught.value) == (
        "by must be one of: category, group, merchant, person, account, bank, card"
    )


def test_summarize() -> None:
    flows = [
        flow(-2599),
        flow(599),
        flow(300000, INCOME),
        flow(-1000, INCOME),
        flow(-50000, TRANSFER),
        flow(50000, TRANSFER),
        flow(2500, UNSORTED_IN),
    ]
    assert summarize(flows) == SpendingSummary(
        spent_cents=2000,
        income_cents=299000,
        transfers=2,
        unsorted_in_cents=2500,
        unsorted_in_count=1,
        refunds_cents=599,
    )
    assert summarize([]) == SpendingSummary(0, 0, 0, 0, 0)


@pytest.mark.parametrize(
    ("text", "bounds"),
    [
        ("2026-05", (date(2026, 5, 1), date(2026, 5, 31))),
        ("2026-02", (date(2026, 2, 1), date(2026, 2, 28))),
        ("2024-02", (date(2024, 2, 1), date(2024, 2, 29))),
        ("2026-12", (date(2026, 12, 1), date(2026, 12, 31))),
    ],
)
def test_month_range(text: str, bounds: tuple[date, date]) -> None:
    assert month_range(text) == bounds


@pytest.mark.parametrize("text", ["2026-13", "2026-00", "2026-5", "May 2026", "", "2026-05-01"])
def test_a_month_that_is_not_one(text: str) -> None:
    with pytest.raises(ValueError) as caught:
        month_range(text)
    assert str(caught.value) == "month must be a year and month, like 2026-05"


def test_month_bounds() -> None:
    assert month_bounds(date(2026, 12, 15)) == (date(2026, 12, 1), date(2026, 12, 31))
