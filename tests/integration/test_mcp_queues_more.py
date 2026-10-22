from datetime import date

import pytest

from finances.categorize.transfers import pair_transfers
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_category,
    create_rule,
    reject_transfer,
    set_category_by_hand,
)
from tests.integration.test_mcp_queues import call


@pytest.fixture
def empty(tmp_settings: Settings) -> Settings:
    upgrade_to_head()
    return tmp_settings


def test_a_higher_priority_rule_comes_first(empty: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_rule(session, "FOOBAR", "Groceries")
        create_rule(session, "PAYCHECK", "Paycheck", priority=1)
    engine.dispose()
    assert [item["pattern"] for item in call("list_rules").structured_content["rules"]] == [
        "PAYCHECK",
        "FOOBAR",
    ]
    assert call("list_rules").structured_content["rules"][0]["priority"] == 1


def test_a_person_created_category_appears_in_order(empty: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_category(session, "Acupuncture", "Health")
    engine.dispose()
    names = [item["name"] for item in call("list_categories").structured_content["categories"]]
    assert names[0] == "Acupuncture"
    chosen = next(
        item
        for item in call("list_categories").structured_content["categories"]
        if item["name"] == "Acupuncture"
    )
    assert chosen == {
        "name": "Acupuncture",
        "group": "Health",
        "transfer": False,
        "income": False,
        "sensitive": True,
    }


def test_a_transaction_set_by_hand_is_not_uncategorized(empty: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=card.id,
                posted_date=date(2026, 5, 3),
                amount_cents=-1500,
                description="BAZ BOOKS",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
        session.flush()
        set_category_by_hand(session, 1, "General Shopping")
    engine.dispose()
    assert call("list_uncategorized").structured_content == {"total": 0, "transactions": []}


def test_a_rejected_suggestion_is_no_longer_listed(empty: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking").id
        savings = create_account(session, "Test Savings", "Test Bank", "savings").id
        rows = [
            (checking, date(2026, 5, 5), -2000, "TRANSFER TO SAVINGS"),
            (savings, date(2026, 5, 5), 2000, "TRANSFER FROM CHECKING"),
            (savings, date(2026, 5, 6), 2000, "TRANSFER FROM CHECKING"),
        ]
        for number, (account, day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=account,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        pair_transfers(session)
        reject_transfer(session, 1, 2)
    engine.dispose()
    suggestions = call("list_transfer_suggestions").structured_content["suggestions"]
    assert suggestions == []


@pytest.mark.parametrize(
    ("tool", "body"),
    [
        ("list_uncategorized", {"total": 0, "transactions": []}),
        ("list_rules", {"rules": []}),
        ("list_transfers", {"total": 0, "pairs": []}),
        ("list_transfer_suggestions", {"suggestions": []}),
    ],
)
def test_queue_tools_on_an_empty_database(empty: Settings, tool: str, body: dict) -> None:
    assert call(tool).structured_content == body


def test_categories_on_an_empty_database(empty: Settings) -> None:
    found = call("list_categories").structured_content["categories"]
    assert len(found) == 34
    assert all(item["group"] not in (None, "") for item in found)
