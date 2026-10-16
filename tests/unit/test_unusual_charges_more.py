from datetime import date

from finances.domain.insights import Finding, duplicates, large_first_charges
from finances.domain.spending import SPENDING, Flow

MAY = date(2026, 5, 1)


def flow(
    merchant: str,
    day: date,
    cents: int,
    category: str = "Dining",
    account: str = "Test Card",
) -> Flow:
    return Flow(
        amount_cents=cents,
        day=day,
        kind=SPENDING,
        category=category,
        group="Food",
        merchant=merchant,
        person="Unassigned",
        account=account,
        bank="Test Bank",
        card="No card",
    )


def test_duplicate_savings_at_exactly_twenty_dollars() -> None:
    medium = [
        flow("ACME", date(2026, 5, 3), -2000),
        flow("ACME", date(2026, 5, 3), -2000),
    ]
    low = [
        flow("ACME", date(2026, 5, 3), -1999),
        flow("ACME", date(2026, 5, 3), -1999),
    ]
    assert duplicates(MAY, medium) == [
        Finding(
            "duplicate",
            "medium",
            MAY,
            "ACME",
            2000,
            "ACME: 2 charges of $20.00 on 2026-05-03.",
        )
    ]
    assert duplicates(MAY, low) == [
        Finding(
            "duplicate",
            "low",
            MAY,
            "ACME",
            1999,
            "ACME: 2 charges of $19.99 on 2026-05-03.",
        )
    ]


def test_category_average_rounds_half_up() -> None:
    # Two earlier charges of $100.00 and $100.01 average to $100.01 after half-up.
    earlier = [
        flow("BAZ TECH", date(2026, 3, 10), -10000, "Electronics"),
        flow("BAZ TECH", date(2026, 4, 10), -10001, "Electronics"),
    ]
    at = [flow("NEW TV", date(2026, 5, 8), -30003, "Electronics")]
    below = [flow("NEW TV", date(2026, 5, 8), -30002, "Electronics")]
    assert [item.subject for item in large_first_charges(MAY, at, earlier, set())] == ["NEW TV"]
    assert large_first_charges(MAY, below, earlier, set()) == []


def test_a_merchant_with_only_refunds_is_not_a_first_charge() -> None:
    month = [flow("REFUND SHOP", date(2026, 5, 15), 50000, "Electronics")]
    assert large_first_charges(MAY, month, [], set()) == []
