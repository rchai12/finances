from datetime import date

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.categories import (
    card_credit_count,
    transaction_facts,
    uncategorized_items,
)
from finances.analysis.listings import account_listing, people_listing
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    assign_by_rule,
    create_account,
    create_rule,
    set_account_active,
)


def add_transaction(session: Session, account_id: int, day: int, description: str) -> int:
    row = TransactionRow(
        account_id=account_id,
        posted_date=date(2026, 5, day),
        amount_cents=-450,
        description=description,
        source="statement",
        fingerprint=f"{description}{day}".ljust(64, "0")[:64],
    )
    session.add(row)
    session.flush()
    return row.id


def test_account_listing_includes_closed_when_asked(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Open", "Test Bank", "checking")
        old = create_account(session, "Test Closed", "Test Bank", "checking")
        set_account_active(session, old.id, False)
        assert [item.account.name for item in account_listing(session)] == ["Test Open"]
        names = [item.account.name for item in account_listing(session, include_inactive=True)]
        assert names == ["Test Closed", "Test Open"]


def test_people_listing_with_no_people(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        assert people_listing(session) == []


def test_uncategorized_items_on_a_closed_account(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        old = create_account(session, "Test Closed", "Test Bank", "credit_card")
        add_transaction(session, old.id, 3, "ACME COFFEE")
        set_account_active(session, old.id, False)
        items = uncategorized_items(session, 50)
        assert [item.account.name for item in items] == ["Test Closed"]
        assert items[0].account.is_active is False


def test_transaction_facts_for_a_rule_category(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        made = add_transaction(session, card.id, 3, "ACME COFFEE")
        rule = create_rule(session, "ACME COFFEE", "Coffee & Dessert", priority=5)
        assign_by_rule(session, made, rule)
        facts = transaction_facts(session, made)
        assert facts is not None
        assert facts.category == "Coffee & Dessert"
        assert facts.assignment is not None
        assert facts.assignment.rule_id == rule.id


def test_card_credit_count_on_an_empty_list() -> None:
    assert card_credit_count([]) == 0
