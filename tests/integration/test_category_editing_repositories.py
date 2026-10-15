from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.config import Settings
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    CategoryDeletion,
    assign_by_rule,
    create_account,
    create_category,
    create_rule,
    delete_category,
    edit_rule,
    get_category_by_name,
    list_categories,
    list_category_assignments,
    list_rules,
    rename_category,
    set_category_by_hand,
)
from finances.domain.models import BY_RULE, MANUAL, CategoryAssignment
from finances.web.app import create_app
from tests.support import WEB_PORT


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    """A migrated database with one card (id 1) and no transactions."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        yield opened


def add_transaction(session: Session, day: int, description: str) -> int:
    row = TransactionRow(
        account_id=1,
        posted_date=date(2026, 5, day),
        amount_cents=-100,
        description=description,
        source="statement",
        fingerprint=f"{description}{day}".ljust(64, "0")[:64],
    )
    session.add(row)
    session.flush()
    return row.id


def test_renaming_a_group_keeps_its_categories(session: Session) -> None:
    food = get_category_by_name(session, "Food")
    assert food is not None
    under = [item.id for item in list_categories(session) if item.group_id == food.id]
    old, renamed = rename_category(session, "food", "Eating")
    assert (old, renamed.name, renamed.group_id) == ("Food", "Eating", None)
    assert [item.id for item in list_categories(session) if item.group_id == renamed.id] == under
    assert get_category_by_name(session, "Coffee & Dessert").group_id == renamed.id


def test_renaming_keeps_a_change_of_its_own_case(session: Session) -> None:
    old, renamed = rename_category(session, "Dining", "dining")
    assert (old, renamed.name) == ("Dining", "dining")
    assert get_category_by_name(session, "DINING").name == "dining"


def test_a_moved_assignment_keeps_its_source(session: Session) -> None:
    by_hand = add_transaction(session, 1, "ACME DINNER")
    by_rule = add_transaction(session, 2, "ACME COFFEE")
    set_category_by_hand(session, by_hand, "Dining")
    rule = create_rule(session, "ACME COFFEE", "Coffee & Dessert")
    assign_by_rule(session, by_rule, rule)
    coffee = get_category_by_name(session, "Coffee & Dessert")
    dining = get_category_by_name(session, "Dining")
    assert coffee is not None and dining is not None
    deleted = delete_category(session, "Coffee & Dessert", "Dining")
    assert deleted == CategoryDeletion("Coffee & Dessert", False, "Dining", 1, 1)
    found = list_category_assignments(session)
    assert found[by_hand] == CategoryAssignment(by_hand, dining.id, MANUAL, None)
    assert found[by_rule] == CategoryAssignment(by_rule, dining.id, BY_RULE, rule.id)
    assert list_rules(session)[0].category_id == dining.id


def test_an_unused_category_with_a_move_to(session: Session) -> None:
    create_category(session, "Probe Snacks", "Food")
    deleted = delete_category(session, "Probe Snacks", "Dining")
    assert deleted == CategoryDeletion("Probe Snacks", False, None, 0, 0)
    assert get_category_by_name(session, "Probe Snacks") is None
    assert get_category_by_name(session, "Dining") is not None


def test_deleting_a_group_ignores_move_to(session: Session) -> None:
    delete_category(session, "Subscriptions & Digital")
    deleted = delete_category(session, "Subscriptions", "Dining")
    assert deleted == CategoryDeletion("Subscriptions", True, None, 0, 0)
    assert get_category_by_name(session, "Subscriptions") is None


def test_editing_only_the_priority_keeps_the_rest(session: Session) -> None:
    rule = create_rule(session, "ACME COFFEE", "Coffee & Dessert", "contains", 0)
    coffee = get_category_by_name(session, "Coffee & Dessert")
    assert coffee is not None
    changed = edit_rule(session, rule.id, priority=9)
    assert (changed.pattern, changed.match, changed.priority, changed.category_id) == (
        "ACME COFFEE",
        "contains",
        9,
        coffee.id,
    )


def test_editing_refuses_an_empty_pattern(session: Session) -> None:
    rule = create_rule(session, "ACME COFFEE", "Coffee & Dessert")
    with pytest.raises(ValueError, match="^a rule pattern must be 1 to 100 characters$"):
        edit_rule(session, rule.id, pattern="  ")


def test_opening_a_rule_needs_a_migrated_database(tmp_settings: Settings) -> None:
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    assert client.get("/categories/rules/1").status_code == 503
