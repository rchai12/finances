from datetime import date

import pytest

from finances.domain.insights import (
    TYPES,
    Finding,
    MerchantStat,
    charges_found,
    frequent_small,
    merchant_stats,
    order_findings,
    overlaps,
    price_increases,
    spikes,
)
from finances.domain.recurring import Charge, Recurring, find_recurring
from finances.domain.spending import INCOME, SPENDING, Flow

MAY = date(2026, 5, 1)


def flow(
    merchant: str, day: date, cents: int, category: str = "Dining", kind: str = SPENDING
) -> Flow:
    return Flow(
        amount_cents=cents,
        day=day,
        kind=kind,
        category=category,
        group="Food",
        merchant=merchant,
        person="Unassigned",
        account="Test Card",
        bank="Test Bank",
        card="No card",
    )


def series(
    merchant: str,
    amount: int,
    monthly: int,
    last: date,
    *,
    previous: int | None = None,
    active: bool = True,
    cadence: str = "month",
) -> Recurring:
    return Recurring(
        merchant=merchant,
        cadence=cadence,
        amount_cents=amount,
        monthly_cents=monthly,
        count=3,
        first_day=date(2026, 1, 1),
        last_day=last,
        next_day=date(2026, 6, 1),
        active=active,
        previous_cents=previous,
    )


def test_the_types() -> None:
    assert TYPES == (
        "spike",
        "frequent_small",
        "subscription_overlap",
        "price_increase",
        "interest",
        "fees",
        "duplicate",
        "large_first_charge",
    )


def test_a_finding_has_a_key_for_its_kind_subject_and_month() -> None:
    finding = Finding("spike", "medium", MAY, "Dining", 18000, "detail")
    assert finding.key == "spike:Dining:2026-05"


def test_recurring_remembers_a_changed_price() -> None:
    gym = [
        Charge("ACME GYM", date(2026, 1, 10), -3000),
        Charge("ACME GYM", date(2026, 2, 10), -3000),
        Charge("ACME GYM", date(2026, 3, 10), -3500),
    ]
    steady = [
        Charge("QUUX", day, -999) for day in (date(2026, 1, 3), date(2026, 2, 3), date(2026, 3, 3))
    ]
    found = find_recurring(gym + steady, date(2026, 3, 20))
    assert [(item.merchant, item.previous_cents) for item in found] == [
        ("ACME GYM", 3000),
        ("QUUX", None),
    ]


def test_merchant_stats() -> None:
    month = [
        flow("ACME COFFEE", date(2026, 5, 2), -500),
        flow("ACME COFFEE", date(2026, 5, 3), -450),
        flow("ACME COFFEE", date(2026, 5, 6), -550),
        flow("ACME COFFEE", date(2026, 5, 7), 100),
        flow("FOOBAR GROCERY", date(2026, 5, 4), -8000),
        flow("PAYCHECK EXAMPLE CORP", date(2026, 5, 15), 300000, "Paycheck", INCOME),
    ]
    earlier = [
        flow("ACME COFFEE", date(2026, 3, 1), -1000),
        flow("ACME COFFEE", date(2026, 4, 1), -2000),
        flow("FOOBAR GROCERY", date(2026, 3, 9), -9000),
        flow("BAZ BOOKS", date(2026, 2, 9), -700),
    ]
    assert merchant_stats(month, earlier) == [
        MerchantStat("FOOBAR GROCERY", 1, 8000, 8000, 3000, 5000, 0),
        MerchantStat("ACME COFFEE", 3, 1400, 500, 1000, 400, 2),
    ]


def test_spikes() -> None:
    month = [
        flow("ACME DINER", date(2026, 5, 9), -30000, "Dining"),
        flow("FOOBAR GROCERY", date(2026, 5, 9), -20000, "Groceries"),
        flow("QUUX AIR", date(2026, 5, 9), -50000, "Flights"),
        flow("BAZ GIFTS", date(2026, 5, 9), -8000, "Gifts & Donations"),
        flow("BAZ SHOES", date(2026, 5, 9), -15000, "Clothing"),
        flow("BAZ TECH", date(2026, 5, 9), -14999, "Electronics"),
        flow("UNKNOWN SHOP", date(2026, 5, 9), -90000, "Uncategorized"),
    ]
    earlier = [
        flow("ACME DINER", date(2026, 3, 9), -36000, "Dining"),
        flow("FOOBAR GROCERY", date(2026, 3, 9), -54000, "Groceries"),
        flow("QUUX AIR", date(2026, 3, 9), -15000, "Flights"),
        flow("BAZ SHOES", date(2026, 3, 9), -30000, "Clothing"),
        flow("BAZ TECH", date(2026, 3, 9), -30000, "Electronics"),
        flow("UNKNOWN SHOP", date(2026, 3, 9), -3000, "Uncategorized"),
    ]
    assert spikes(MAY, month, earlier) == [
        Finding(
            "spike",
            "medium",
            MAY,
            "Clothing",
            5000,
            "Clothing: $150.00 this month, against $100.00 a month before.",
        ),
        Finding(
            "spike",
            "medium",
            MAY,
            "Dining",
            18000,
            "Dining: $300.00 this month, against $120.00 a month before.",
        ),
        Finding(
            "spike",
            "high",
            MAY,
            "Flights",
            45000,
            "Flights: $500.00 this month, against $50.00 a month before.",
        ),
    ]


def test_frequent_small_purchases() -> None:
    month = (
        [flow("ACME COFFEE", date(2026, 5, day), -500) for day in range(1, 9)]
        + [flow("BAZ SNACKS", date(2026, 5, day), -300) for day in range(1, 8)]
        + [flow("QUUX DELI", date(2026, 5, day), -1600) for day in range(1, 11)]
        + [flow("FOOBAR BAR", date(2026, 5, day), -1500) for day in range(1, 21)]
        + [flow("BAZ CAFE", date(2026, 5, day), -333) for day in range(1, 10)]
    )
    assert frequent_small(MAY, month) == [
        Finding(
            "frequent_small",
            "low",
            MAY,
            "ACME COFFEE",
            2000,
            "ACME COFFEE: 8 visits averaging $5.00.",
        ),
        Finding(
            "frequent_small", "low", MAY, "BAZ CAFE", 1499, "BAZ CAFE: 9 visits averaging $3.33."
        ),
        Finding(
            "frequent_small",
            "medium",
            MAY,
            "FOOBAR BAR",
            15000,
            "FOOBAR BAR: 20 visits averaging $15.00.",
        ),
    ]


def test_interest_and_fees() -> None:
    month = [
        flow("PURCHASE INTEREST CHARGE", date(2026, 5, 28), -2345, "Uncategorized"),
        flow("INTEREST CHARGE ON PURCHASES", date(2026, 5, 28), -100, "Fees & Interest"),
        flow("LATE FEE", date(2026, 5, 20), -3500, "Fees & Interest"),
        flow("ANNUAL MEMBERSHIP FEE", date(2026, 5, 2), -9500, "Uncategorized"),
        flow("COFFEE FEED STORE", date(2026, 5, 2), -700),
        flow("INTEREST PAID", date(2026, 5, 31), 50, "Interest Income", INCOME),
    ]
    assert charges_found(MAY, month) == [
        Finding("interest", "high", MAY, "", 2445, "Interest charged: $24.45."),
        Finding("fees", "medium", MAY, "", 13000, "Fees charged: $130.00."),
    ]
    assert charges_found(MAY, [flow("LATE FEE", date(2026, 5, 20), -3500)]) == [
        Finding("fees", "medium", MAY, "", 3500, "Fees charged: $35.00.")
    ]


def test_price_increases() -> None:
    found = price_increases(
        MAY,
        [
            series("QUUX STREAMING", 1799, 1799, date(2026, 5, 5), previous=1599),
            series("BAZ VIDEO", 1799, 1799, date(2026, 5, 6), previous=1999),
            series("ACME GYM", 3500, 3500, date(2026, 4, 30), previous=3000),
            series("OLD TV", 1200, 1200, date(2026, 5, 2), previous=1000, active=False),
            series("QUUX CLOUD", 10900, 908, date(2026, 5, 3), previous=9900, cadence="year"),
            series("FOOBAR APPS", 299, 299, date(2026, 5, 3)),
        ],
    )
    assert found == [
        Finding(
            "price_increase",
            "medium",
            MAY,
            "QUUX CLOUD",
            83,
            "QUUX CLOUD went from $99.00 to $109.00.",
        ),
        Finding(
            "price_increase",
            "medium",
            MAY,
            "QUUX STREAMING",
            200,
            "QUUX STREAMING went from $15.99 to $17.99.",
        ),
    ]


def test_overlapping_subscriptions() -> None:
    found = overlaps(
        MAY,
        [
            series("QUUX STREAMING", 1799, 1799, date(2026, 5, 5)),
            series("ACME GYM", 3000, 3000, date(2026, 5, 5)),
            series("BAZ VIDEO", 999, 999, date(2026, 5, 12)),
            series("FOOBAR APPS", 299, 299, date(2026, 5, 3)),
            series("FOOBAR APPS", 999, 999, date(2026, 5, 20)),
            series("OLD TV", 1200, 1200, date(2026, 3, 2), active=False),
        ],
        {
            "QUUX STREAMING": "Subscriptions & Digital",
            "ACME GYM": "Fitness",
            "BAZ VIDEO": "Subscriptions & Digital",
            "FOOBAR APPS": "Uncategorized",
            "OLD TV": "Subscriptions & Digital",
        },
    )
    assert found == [
        Finding(
            "subscription_overlap",
            "low",
            MAY,
            "Subscriptions & Digital",
            999,
            "Subscriptions & Digital: QUUX STREAMING ($17.99), BAZ VIDEO ($9.99).",
        )
    ]


def test_order_findings() -> None:
    low = Finding("subscription_overlap", "low", MAY, "Subscriptions & Digital", 999, "")
    small = Finding("frequent_small", "low", MAY, "ACME COFFEE", 999, "")
    small_b = Finding("frequent_small", "low", MAY, "baz cafe", 999, "")
    medium = Finding("price_increase", "medium", MAY, "QUUX", 200, "")
    spike = Finding("spike", "medium", MAY, "Dining", 14000, "")
    high = Finding("interest", "high", MAY, "", 1, "")
    assert order_findings([low, small_b, medium, small, high, spike]) == [
        high,
        spike,
        medium,
        small,
        small_b,
        low,
    ]


@pytest.mark.parametrize("flows", [[], [flow("ACME", MAY, 500)]])
def test_nothing_to_find(flows: list[Flow]) -> None:
    assert spikes(MAY, flows, []) == []
    assert frequent_small(MAY, flows) == []
    assert charges_found(MAY, flows) == []
    assert price_increases(MAY, []) == []
    assert overlaps(MAY, [], {}) == []
