from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.categorize.service import categorize
from finances.categorize.transfers import pair_transfers
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    clear_category_by_hand,
    create_account,
    create_category,
    create_person,
    create_rule,
    create_transfer_pair,
    delete_category,
    delete_rule,
    edit_rule,
    list_changes,
    record_change,
    reject_transfer,
    remove_budget,
    rename_account,
    rename_category,
    set_account_active,
    set_account_owner,
    set_budget,
    set_cardholder_alias,
    set_category_by_hand,
    unpair_transfer,
)
from finances.domain.audit import Change
from finances.domain.models import CONFIRMED

NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    monkeypatch.setattr("finances.db.repositories.audit._now", lambda: NOON)
    with session_scope(db_engine) as opened:
        yield opened


def add(session: Session, number: int, account: int, cents: int, description: str) -> None:
    session.add(
        TransactionRow(
            account_id=account,
            posted_date=date(2026, 5, number),
            amount_cents=cents,
            description=description,
            source="statement",
            fingerprint=f"t{number:02d}".ljust(64, "0"),
        )
    )
    session.flush()


def trail(session: Session) -> list[tuple]:
    return [
        (item.who, item.action, item.kind, item.record_id, item.before, item.after)
        for item in reversed(list_changes(session, limit=1000))
    ]


def test_each_change_a_person_makes(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    create_account(session, "Test Checking", "Test Bank", "checking")
    rename_account(session, 1, "Test Visa")
    set_account_active(session, 2, False)
    set_account_active(session, 2, True)
    create_person(session, "Pat Example")
    set_account_owner(session, 1, 1)
    set_account_owner(session, 1, None)
    set_cardholder_alias(session, "p example", 1)
    create_category(session, "Pets", "Home")
    rename_category(session, "Pets", "Pet Care")
    create_rule(session, "acme  coffee", "Coffee & Dessert")
    edit_rule(session, 1, priority=5)
    set_budget(session, "Groceries", 15000)
    set_budget(session, "Groceries", 20000)
    remove_budget(session, "Groceries")
    add(session, 1, 1, -500, "ACME COFFEE")
    add(session, 2, 2, -2000, "TRANSFER TO CARD")
    add(session, 3, 1, 2000, "PAYMENT THANK YOU")
    set_category_by_hand(session, 1, "Dining")
    set_category_by_hand(session, 1, "Groceries")
    clear_category_by_hand(session, 1)
    create_transfer_pair(session, 2, 3, CONFIRMED)
    unpair_transfer(session, 1)
    reject_transfer(session, 2, 3)
    delete_rule(session, 1)
    delete_category(session, "Pet Care")
    rule_5 = 'contains "ACME COFFEE" -> Coffee & Dessert (priority 5)'
    assert trail(session) == [
        ("person", "account_added", "account", 1, None, "Test Card"),
        ("person", "account_added", "account", 2, None, "Test Checking"),
        ("person", "account_renamed", "account", 1, "Test Card", "Test Visa"),
        ("person", "account_closed", "account", 2, "open", "closed"),
        ("person", "account_reopened", "account", 2, "closed", "open"),
        ("person", "person_added", "person", 1, None, "Pat Example"),
        ("person", "owner_set", "account", 1, None, "Pat Example"),
        ("person", "owner_set", "account", 1, "Pat Example", "Joint"),
        ("person", "cardholder_set", "person", 1, None, "P EXAMPLE"),
        ("person", "category_added", "category", 47, None, "Pets"),
        ("person", "category_renamed", "category", 47, "Pets", "Pet Care"),
        (
            "person",
            "rule_added",
            "rule",
            1,
            None,
            'contains "ACME COFFEE" -> Coffee & Dessert (priority 0)',
        ),
        (
            "person",
            "rule_edited",
            "rule",
            1,
            'contains "ACME COFFEE" -> Coffee & Dessert (priority 0)',
            rule_5,
        ),
        ("person", "budget_set", "category", 13, None, "$150.00"),
        ("person", "budget_set", "category", 13, "$150.00", "$200.00"),
        ("person", "budget_removed", "category", 13, "$200.00", None),
        ("person", "category_set", "transaction", 1, None, "Dining"),
        ("person", "category_set", "transaction", 1, "Dining", "Groceries"),
        ("person", "category_cleared", "transaction", 1, "Groceries", None),
        ("person", "transfer_confirmed", "transfer", 1, None, "2 -> 3"),
        ("person", "transfer_unpaired", "transfer", 1, "2 -> 3", None),
        ("person", "transfer_rejected", "transaction", 2, None, "2 -> 3"),
        ("person", "rule_deleted", "rule", 1, rule_5, None),
        ("person", "category_deleted", "category", 47, "Pet Care", None),
    ]


def test_nothing_is_recorded_when_nothing_changes(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    create_person(session, "Pat Example")
    set_account_owner(session, 1, 1)
    set_cardholder_alias(session, "P EXAMPLE", 1)
    add(session, 1, 1, -500, "ACME COFFEE")
    set_category_by_hand(session, 1, "Dining")
    set_budget(session, "Groceries", 15000)
    before = len(list_changes(session, limit=1000))
    rename_account(session, 1, "Test Card")
    set_account_active(session, 1, True)
    set_account_owner(session, 1, 1)
    set_cardholder_alias(session, "P EXAMPLE", 1)
    set_category_by_hand(session, 1, "Dining")
    set_budget(session, "Groceries", 15000)
    rename_category(session, "Dining", "Dining")
    add(session, 2, 1, 999, "BAZ CREDIT")
    clear_category_by_hand(session, 2)
    assert len(list_changes(session, limit=1000)) == before


def test_rules_and_automatic_pairing_record_nothing(session: Session) -> None:
    create_account(session, "Test Checking", "Test Bank", "checking")
    create_account(session, "Test Card", "Test Bank", "credit_card")
    create_rule(session, "ACME", "Dining")
    add(session, 1, 2, -500, "ACME COFFEE")
    add(session, 2, 1, -2000, "PAYMENT TO CARD")
    add(session, 3, 2, 2000, "PAYMENT THANK YOU")
    before = len(list_changes(session, limit=1000))
    categorize(session)
    pair_transfers(session)
    assert len(list_changes(session, limit=1000)) == before


def test_a_refused_change_records_nothing(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    with pytest.raises(ValueError, match="category not found"):
        set_budget(session, "Nope", 100)
    assert [item.action for item in list_changes(session)] == ["account_added"]


def test_record_change_checks_and_fits(session: Session) -> None:
    found = record_change(
        session, action="budget_set", kind="category", record_id=13, after="x" * 250, who="system"
    )
    assert found == Change(found.id, NOON, "system", "budget_set", "category", 13, None, "x" * 200)
    for field, value, message in (
        ("action", "nope", "action must be one of: account_added, "),
        (
            "kind",
            "nope",
            "kind must be one of: account, person, category, rule, transaction, transfer",
        ),
        ("who", "agent", "who must be one of: person, system"),
    ):
        arguments = {"action": "budget_set", "kind": "category", "record_id": 13, field: value}
        with pytest.raises(ValueError, match=message):
            record_change(session, **arguments)


def test_list_changes_newest_first_and_filters(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    for day, name in ((24, "Test A"), (25, "Test B"), (25, "Test C")):
        moment = datetime(2026, 5, day, 23, 30, tzinfo=UTC)
        monkeypatch.setattr("finances.db.repositories.audit._now", lambda moment=moment: moment)
        create_account(session, name, "Test Bank", "checking")
    create_person(session, "Pat Example")
    assert [item.after for item in list_changes(session)] == [
        "Pat Example",
        "Test C",
        "Test B",
        "Test A",
    ]
    assert [item.after for item in list_changes(session, since=date(2026, 5, 25))] == [
        "Pat Example",
        "Test C",
        "Test B",
    ]
    assert [item.after for item in list_changes(session, action="person_added")] == ["Pat Example"]
    assert [item.after for item in list_changes(session, limit=1)] == ["Pat Example"]
    with pytest.raises(ValueError, match="limit must be at least 1"):
        list_changes(session, limit=0)
