from datetime import date

import pytest

from finances.categorize.service import categorize
from finances.categorize.transfers import pair_transfers
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_person,
    create_rule,
    set_account_active,
    set_account_owner,
)
from tests.integration.test_mcp_spending import call, ids


@pytest.fixture
def money(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 5, 29))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        set_account_owner(session, card.id, create_person(session, "Pat Example").id)
        rows = [
            (card, date(2026, 5, 2), -2599, "FOOBAR GROCERY #77", "1111", False),
            (card, date(2026, 5, 10), 599, "FOOBAR GROCERY #77", "1111", False),
            (card, date(2026, 5, 12), -1500, "BAZ BOOKS", None, False),
            (checking, date(2026, 5, 15), 300000, "PAYCHECK EXAMPLE CORP", None, False),
            (checking, date(2026, 5, 20), -50000, "PAYMENT TO TEST CARD", None, False),
            (card, date(2026, 5, 21), 50000, "PAYMENT THANK YOU", None, False),
            (card, date(2026, 4, 8), -3000, "FOOBAR GROCERY #12", "1111", False),
            (card, date(2026, 5, 25), -999, "QUUX STREAMING", None, True),
            (checking, date(2026, 5, 28), 2500, "ACME CREDIT", None, False),
        ]
        for number, (account, day, cents, description, last4, pending) in enumerate(rows, 1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    card_last4=last4,
                    is_pending=pending,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        pair_transfers(session)
        create_rule(session, "FOOBAR", "Groceries")
        create_rule(session, "PAYCHECK", "Paycheck")
        categorize(session)
    engine.dispose()
    return tmp_settings


def test_account_bank_and_group_filters(money: Settings) -> None:
    assert ids(call("list_transactions", {"account": "Test Card"})) == [8, 6, 3, 2, 1, 7]
    assert ids(call("list_transactions", {"bank": "Test Bank"})) == [9, 8, 6, 5, 4, 3, 2, 1, 7]
    assert ids(call("list_transactions", {"group": "Food"})) == [2, 1, 7]


def test_a_closed_account_still_lists_its_transactions(tmp_settings: Settings) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Old Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=card.id,
                posted_date=date(2026, 5, 2),
                amount_cents=-2599,
                description="FOOBAR GROCERY",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
        session.flush()
        set_account_active(session, card.id, False)
    engine.dispose()
    found = call("list_transactions")
    assert ids(found) == [1]
    assert found.structured_content["transactions"][0]["account"] == "Old Card"


def test_a_full_page_of_200_has_a_next_offset(tmp_settings: Settings) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        for number in range(1, 202):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=date(2026, 5, 1),
                    amount_cents=-100,
                    description="FOOBAR GROCERY",
                    source="statement",
                    fingerprint=f"t{number:03d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    found = call("list_transactions", {"limit": 200})
    assert len(found.structured_content["transactions"]) == 200
    assert found.structured_content["next_offset"] == 200


@pytest.mark.parametrize(
    ("by", "labels"),
    [
        ("merchant", ["FOOBAR GROCERY", "BAZ BOOKS"]),
        ("account", ["Test Card"]),
        ("bank", ["Test Bank"]),
        ("card", ["1111", "No card"]),
        ("group", ["Food", "Uncategorized"]),
    ],
)
def test_spending_grouped_the_other_ways(money: Settings, by: str, labels: list[str]) -> None:
    found = call("get_spending", {"by": by})
    assert [line["label"] for line in found.structured_content["lines"]] == labels


def test_a_period_with_no_spending(money: Settings) -> None:
    found = call("get_spending", {"start": "2020-01-01", "end": "2020-01-31"})
    assert found.structured_content == {
        "start": "2020-01-01",
        "end": "2020-01-31",
        "by": "category",
        "lines": [],
        "summary": {
            "spent_cents": 0,
            "refunds_cents": 0,
            "net_cents": 0,
            "income_cents": 0,
            "transfers": 0,
            "unsorted_in_cents": 0,
            "unsorted_in_count": 0,
        },
    }


def test_month_over_month_count_24(money: Settings) -> None:
    months = call("month_over_month", {"count": 24}).structured_content["months"]
    assert [item["month"] for item in months] == [
        "2024-06",
        "2024-07",
        "2024-08",
        "2024-09",
        "2024-10",
        "2024-11",
        "2024-12",
        "2025-01",
        "2025-02",
        "2025-03",
        "2025-04",
        "2025-05",
        "2025-06",
        "2025-07",
        "2025-08",
        "2025-09",
        "2025-10",
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
        "2026-05",
    ]
