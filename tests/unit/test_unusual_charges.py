from datetime import date

from finances.domain.insights import TYPES, Finding, duplicates, large_first_charges
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


def test_the_two_new_types_come_last() -> None:
    assert TYPES[-2:] == ("duplicate", "large_first_charge")


def test_duplicates() -> None:
    month = [
        flow("ACME COFFEE", date(2026, 5, 3), -450),
        flow("ACME COFFEE", date(2026, 5, 3), -450),
        flow("ACME COFFEE", date(2026, 5, 4), -450),
        flow("ACME COFFEE", date(2026, 5, 10), -1200),
        flow("ACME COFFEE", date(2026, 5, 10), -1200),
        flow("ACME COFFEE", date(2026, 5, 10), -1200),
        flow("BAZ BOOKS", date(2026, 5, 5), -3000, account="Test Card"),
        flow("BAZ BOOKS", date(2026, 5, 5), -3000, account="Test Checking"),
        flow("QUUX DELI", date(2026, 5, 6), -500),
        flow("QUUX DELI", date(2026, 5, 6), 500),
        flow("FOOBAR", date(2026, 5, 7), -2500),
        flow("FOOBAR", date(2026, 5, 7), -2500),
        flow("baz cafe", date(2026, 5, 8), -300),
        flow("baz cafe", date(2026, 5, 8), -300),
    ]
    assert duplicates(MAY, month) == [
        Finding(
            "duplicate",
            "medium",
            MAY,
            "ACME COFFEE",
            2850,
            "ACME COFFEE: 2 charges of $4.50 on 2026-05-03; 3 charges of $12.00 on 2026-05-10.",
        ),
        Finding(
            "duplicate", "low", MAY, "baz cafe", 300, "baz cafe: 2 charges of $3.00 on 2026-05-08."
        ),
        Finding(
            "duplicate", "medium", MAY, "FOOBAR", 2500, "FOOBAR: 2 charges of $25.00 on 2026-05-07."
        ),
    ]
    assert duplicates(MAY, []) == []


def test_large_first_charges() -> None:
    earlier = [
        flow("BAZ TECH", date(2026, 3, 10), -10000, "Electronics"),
        flow("BAZ TECH", date(2026, 4, 10), -20000, "Electronics"),
        flow("OLD SHOP", date(2026, 4, 1), -100, "General Shopping"),
    ]
    month = [
        flow("NEW TV", date(2026, 5, 2), -1000, "Electronics"),
        flow("NEW TV", date(2026, 5, 8), -60000, "Electronics"),
        flow("NEW CAMERA", date(2026, 5, 9), -40000, "Electronics"),
        flow("NEW SOFA", date(2026, 5, 11), -30000, "Home & Garden"),
        flow("NEW SOFA", date(2026, 5, 20), -30000, "Home & Garden"),
        flow("NEW GYM", date(2026, 5, 12), -26000, "Uncategorized"),
        flow("SMALL NEW", date(2026, 5, 13), -24999, "Uncategorized"),
        flow("OLD SHOP", date(2026, 5, 14), -90000, "General Shopping"),
        flow("REFUND ONLY", date(2026, 5, 15), 50000, "Electronics"),
    ]
    seen = {"BAZ TECH", "OLD SHOP", "SOMEWHERE LONG AGO"}
    assert large_first_charges(MAY, month, earlier, seen) == [
        Finding(
            "large_first_charge",
            "medium",
            MAY,
            "NEW GYM",
            0,
            "NEW GYM: first seen this month, with a charge of $260.00 on 2026-05-12.",
        ),
        Finding(
            "large_first_charge",
            "medium",
            MAY,
            "NEW SOFA",
            0,
            "NEW SOFA: first seen this month, with a charge of $300.00 on 2026-05-11.",
        ),
        Finding(
            "large_first_charge",
            "medium",
            MAY,
            "NEW TV",
            0,
            "NEW TV: first seen this month, with a charge of $600.00 on 2026-05-08.",
        ),
    ]


def test_three_times_the_category_average_exactly() -> None:
    earlier = [flow("BAZ TECH", date(2026, 4, 10), -10000, "Electronics")]
    at = [flow("NEW TV", date(2026, 5, 8), -30000, "Electronics")]
    below = [flow("NEW TV", date(2026, 5, 8), -29999, "Electronics")]
    assert [item.subject for item in large_first_charges(MAY, at, earlier, set())] == ["NEW TV"]
    assert large_first_charges(MAY, below, earlier, set()) == []
