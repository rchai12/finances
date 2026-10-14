from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    CategoryExistsError,
    assign_by_rule,
    clear_category_by_hand,
    create_account,
    create_category,
    create_rule,
    delete_feed_transaction,
    delete_rule,
    get_category_by_name,
    insert_feed_transaction,
    list_categories,
    list_category_assignments,
    list_rules,
    list_transaction_descriptions,
    list_uncategorized,
    remove_category,
    set_category_by_hand,
)
from finances.domain.models import BY_RULE, MANUAL, CategoryAssignment, DataSource, NewTransaction

GROUP_GIVEN = "rules and transactions take a category, not a group"
BAD_NAME = "a category name must be 1 to 50 characters"
BAD_PATTERN = "a rule pattern must be 1 to 100 characters"
BAD_MATCH = "match must be one of: contains, starts_with, equals"


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    """A migrated database with one card (id 1) and no transactions."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        yield opened


def add_transaction(session: Session, day: int, description: str, cents: int = -100) -> int:
    row = TransactionRow(
        account_id=1,
        posted_date=date(2026, 5, day),
        amount_cents=cents,
        description=description,
        source="statement",
        fingerprint=f"{description}{day}".ljust(64, "0")[:64],
    )
    session.add(row)
    session.flush()
    return row.id


def category_id(session: Session, name: str) -> int:
    found = get_category_by_name(session, name)
    assert found is not None
    return found.id


# The category tree


def test_categories_are_listed_by_name_ignoring_case(session: Session) -> None:
    create_category(session, "aardvark Care", "Personal")
    found = list_categories(session)
    assert len(found) == 47
    assert [item.name for item in found] == sorted(
        (item.name for item in found), key=lambda name: name.lower()
    )
    assert found[0].name == "aardvark Care"


def test_a_group_or_category_is_found_ignoring_case_and_spaces(session: Session) -> None:
    food = get_category_by_name(session, "  fOOD ")
    coffee = get_category_by_name(session, "coffee & DESSERT")
    assert food is not None and food.name == "Food" and food.group_id is None
    assert coffee is not None and coffee.name == "Coffee & Dessert"
    assert coffee.group_id == food.id
    assert get_category_by_name(session, "Nope") is None


def test_a_new_category_takes_its_group_flags(session: Session) -> None:
    therapy = create_category(session, "  Therapy ", "health")
    moving = create_category(session, "Between Accounts", "TRANSFERS")
    salary = create_category(session, "Bonus", "Income")
    plain = create_category(session, "N" * 50, "Food")
    health = get_category_by_name(session, "Health")
    assert health is not None
    assert (therapy.name, therapy.group_id) == ("Therapy", health.id)
    assert (therapy.is_transfer, therapy.is_income, therapy.is_sensitive) == (False, False, True)
    assert (moving.is_transfer, moving.is_income, moving.is_sensitive) == (True, False, False)
    assert (salary.is_transfer, salary.is_income, salary.is_sensitive) == (False, True, False)
    assert (plain.is_transfer, plain.is_income, plain.is_sensitive) == (False, False, False)
    assert get_category_by_name(session, "therapy") == therapy


@pytest.mark.parametrize(
    ("name", "group", "message"),
    [
        ("", "Nope", BAD_NAME),
        ("   ", "Food", BAD_NAME),
        ("N" * 51, "Nope", BAD_NAME),
        ("Therapy", "Nope", "group not found"),
        ("Therapy", "Dining", "group not found"),
        ("Dining", "Nope", "group not found"),
    ],
)
def test_a_refused_category(session: Session, name: str, group: str, message: str) -> None:
    with pytest.raises(ValueError, match=f"^{message}$"):
        create_category(session, name, group)
    assert len(list_categories(session)) == 46


@pytest.mark.parametrize("name", ["food", " DINING ", "Coffee & dessert"])
def test_a_taken_name_is_refused(session: Session, name: str) -> None:
    with pytest.raises(CategoryExistsError, match="^a category with this name already exists$"):
        create_category(session, name, "Health")


# Rules


def test_a_rule_is_stored_with_its_pattern_normalized(session: Session) -> None:
    rule = create_rule(session, "  acme \t coffee ", "coffee & dessert", "equals", -3)
    assert (rule.pattern, rule.match, rule.priority) == ("ACME COFFEE", "equals", -3)
    assert rule.category_id == category_id(session, "Coffee & Dessert")
    assert list_rules(session) == [rule]


def test_a_rule_takes_the_defaults(session: Session) -> None:
    rule = create_rule(session, "acme", "Dining")
    assert (rule.match, rule.priority) == ("contains", 0)


@pytest.mark.parametrize(
    ("pattern", "category", "match", "message"),
    [
        ("  ", "Nope", "regex", BAD_PATTERN),
        ("P" * 101, "Nope", "regex", BAD_PATTERN),
        ("X", "Nope", "regex", BAD_MATCH),
        ("X", "Nope", "contains", "category not found"),
        ("X", "Food", "contains", GROUP_GIVEN),
        ("acme", "Groceries", "contains", "a rule with this pattern and match already exists"),
    ],
)
def test_a_refused_rule(
    session: Session, pattern: str, category: str, match: str, message: str
) -> None:
    create_rule(session, "ACME", "Dining")
    with pytest.raises(ValueError, match=f"^{message}$"):
        create_rule(session, pattern, category, match)
    assert len(list_rules(session)) == 1


def test_the_same_pattern_with_another_match_is_a_new_rule(session: Session) -> None:
    create_rule(session, "ACME", "Dining")
    create_rule(session, "acme", "Groceries", "equals")
    create_rule(session, "P" * 100, "Groceries")
    assert len(list_rules(session)) == 3


def test_rules_are_listed_in_the_order_they_are_tried(session: Session) -> None:
    low = create_rule(session, "A", "Dining", priority=-1)
    plain = create_rule(session, "B", "Dining")
    first_high = create_rule(session, "C", "Dining", priority=5)
    second_high = create_rule(session, "D", "Dining", priority=5)
    assert list_rules(session) == [first_high, second_high, plain, low]


def test_deleting_a_rule_removes_only_its_assignments(session: Session) -> None:
    coffee, grocery, diner = (
        add_transaction(session, day, text)
        for day, text in ((1, "ACME COFFEE"), (2, "FOOBAR GROCERY"), (3, "FOOBAR DINER"))
    )
    gone = create_rule(session, "ACME", "Coffee & Dessert")
    kept = create_rule(session, "FOOBAR", "Groceries")
    assign_by_rule(session, coffee, gone)
    assign_by_rule(session, grocery, kept)
    set_category_by_hand(session, diner, "Dining")
    delete_rule(session, gone.id)
    assert list_rules(session) == [kept]
    assert sorted(list_category_assignments(session)) == [grocery, diner]


def test_deleting_an_unknown_rule(session: Session) -> None:
    with pytest.raises(ValueError, match="^rule not found$"):
        delete_rule(session, 9)


# Assignments


def test_a_rule_assignment_is_replaced(session: Session) -> None:
    item = add_transaction(session, 1, "ACME COFFEE")
    first = create_rule(session, "ACME", "Dining")
    second = create_rule(session, "COFFEE", "Coffee & Dessert")
    assign_by_rule(session, item, first)
    assign_by_rule(session, item, second)
    assert list_category_assignments(session) == {
        item: CategoryAssignment(item, second.category_id, BY_RULE, second.id)
    }


def test_removing_a_category(session: Session) -> None:
    item = add_transaction(session, 1, "ACME COFFEE")
    other = add_transaction(session, 2, "FOOBAR GROCERY")
    remove_category(session, item)
    assign_by_rule(session, item, create_rule(session, "ACME", "Dining"))
    set_category_by_hand(session, other, "Groceries")
    remove_category(session, item)
    assert list(list_category_assignments(session)) == [other]


def test_a_category_set_by_hand_replaces_a_rule(session: Session) -> None:
    item = add_transaction(session, 1, "ACME COFFEE")
    assign_by_rule(session, item, create_rule(session, "ACME", "Dining"))
    chosen = set_category_by_hand(session, item, "  coffee & dessert ")
    assert chosen.name == "Coffee & Dessert"
    assert list_category_assignments(session) == {
        item: CategoryAssignment(item, chosen.id, MANUAL, None)
    }
    clear_category_by_hand(session, item)
    assert list_category_assignments(session) == {}


@pytest.mark.parametrize(
    ("transaction_id", "category", "message"),
    [
        (99, "Nope", "transaction not found"),
        (1, "Nope", "category not found"),
        (1, "Food", GROUP_GIVEN),
    ],
)
def test_a_refused_category_by_hand(
    session: Session, transaction_id: int, category: str, message: str
) -> None:
    add_transaction(session, 1, "ACME COFFEE")
    with pytest.raises(ValueError, match=f"^{message}$"):
        set_category_by_hand(session, transaction_id, category)
    assert list_category_assignments(session) == {}


def test_clearing_an_unknown_transaction(session: Session) -> None:
    with pytest.raises(ValueError, match="^transaction not found$"):
        clear_category_by_hand(session, 99)


def test_a_categorized_feed_row_can_be_deleted(session: Session) -> None:
    kept = add_transaction(session, 1, "FOOBAR GROCERY")
    feed_row = insert_feed_transaction(
        session,
        NewTransaction(
            account_id=1,
            statement_id=None,
            posted_date=date(2026, 5, 2),
            transaction_date=None,
            amount_cents=-450,
            description="ACME COFFEE",
            section=None,
            card_last4=None,
            cardholder=None,
            external_id=None,
            source=DataSource.AGGREGATOR,
            is_pending=False,
            fingerprint="f".ljust(64, "0"),
        ),
        "f-1",
    )
    assign_by_rule(session, feed_row.id, create_rule(session, "ACME", "Dining"))
    set_category_by_hand(session, kept, "Groceries")
    assert delete_feed_transaction(session, feed_row.id) is True
    assert session.get(TransactionRow, feed_row.id) is None
    assert list(list_category_assignments(session)) == [kept]


# Listings


def test_uncategorized_transactions_latest_first(session: Session) -> None:
    early, late_one, late_two, by_rule, by_hand = (
        add_transaction(session, day, text)
        for day, text in (
            (1, "EARLY"),
            (9, "LATE ONE"),
            (9, "LATE TWO"),
            (12, "BY RULE"),
            (15, "BY HAND"),
        )
    )
    assign_by_rule(session, by_rule, create_rule(session, "RULE", "Dining"))
    set_category_by_hand(session, by_hand, "Dining")
    assert [item.id for item in list_uncategorized(session, 10)] == [late_two, late_one, early]
    assert [item.id for item in list_uncategorized(session, 1)] == [late_two]
    with pytest.raises(ValueError, match="^limit must be at least 1$"):
        list_uncategorized(session, 0)


def test_descriptions_in_id_order(session: Session) -> None:
    second_day = add_transaction(session, 2, "SECOND DAY")
    first_day = add_transaction(session, 1, "FIRST DAY")
    assert list_transaction_descriptions(session) == [
        (second_day, "SECOND DAY"),
        (first_day, "FIRST DAY"),
    ]
