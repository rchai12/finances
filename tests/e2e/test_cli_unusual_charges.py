from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from tests.support import plain_lines, run, table_rows

HEADINGS = ["Severity", "Type", "About", "Saves a month", "Detail"]


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    """December: a hotel. April: a coffee and a gadget. May: the same coffee twice on one
    day, a television from a shop never used before (five times April's gadget), and the hotel
    again, which is not new because it was used in December. June: the television shop again."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (day, cents, description) in enumerate(
            (
                (date(2025, 12, 1), -40000, "BIG HOTEL"),
                (date(2026, 4, 2), -450, "ACME COFFEE"),
                (date(2026, 4, 10), -10000, "BAZ TECH"),
                (date(2026, 5, 3), -450, "ACME COFFEE"),
                (date(2026, 5, 3), -450, "ACME COFFEE"),
                (date(2026, 5, 8), -50000, "QUUX TV"),
                (date(2026, 5, 9), -40000, "BIG HOTEL"),
                (date(2026, 6, 8), -50000, "QUUX TV"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    for pattern, category in (("BAZ TECH", "Electronics"), ("QUUX TV", "Electronics")):
        assert run("rules", "add", "--pattern", pattern, "--category", category).exit_code == 0
    return tmp_settings


def test_duplicates_and_a_large_first_charge(money: Settings) -> None:
    result = run("insights", "--month", "2026-05")
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [
        HEADINGS,
        [
            "high",
            "spike",
            "Electronics",
            "$466.67",
            "Electronics: $500.00 this month, against $33.33 a month before.",
        ],
        [
            "medium",
            "large_first_charge",
            "QUUX TV",
            "$0.00",
            "QUUX TV: first seen this month, with a charge of $500.00 on 2026-05-08.",
        ],
        [
            "low",
            "duplicate",
            "ACME COFFEE",
            "$4.50",
            "ACME COFFEE: 2 charges of $4.50 on 2026-05-03.",
        ],
    ]
    assert plain_lines(result.stdout) == [
        "Insights for 2026-05.",
        "Findings: 3. Could save up to $471.17 a month.",
    ]


def test_a_shop_seen_in_an_earlier_month_is_not_new(money: Settings) -> None:
    """June's television comes from a shop first seen in May: only the spike is left."""
    rows = table_rows(run("insights", "--month", "2026-06").stdout)
    assert rows[1:] == [
        [
            "high",
            "spike",
            "Electronics",
            "$300.00",
            "Electronics: $500.00 this month, against $200.00 a month before.",
        ]
    ]
