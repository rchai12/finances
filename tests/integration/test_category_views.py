from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.config import Settings
from finances.db.engine import session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    assign_by_rule,
    create_account,
    create_category,
    create_rule,
    get_transaction,
    set_category_by_hand,
)
from finances.views.categories import TransactionDetail, category_choices, transaction_detail
from finances.web.app import create_app

PORT = 8765


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    """A migrated database with one card (id 1) and no transactions."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        yield opened


def add_transaction(
    session: Session, day: int, description: str, cents: int = -450, card: str | None = None
) -> int:
    row = TransactionRow(
        account_id=1,
        posted_date=date(2026, 5, day),
        amount_cents=cents,
        description=description,
        card_last4=card,
        source="statement",
        fingerprint=f"{description}{day}".ljust(64, "0")[:64],
    )
    session.add(row)
    session.flush()
    return row.id


# get_transaction


def test_a_known_transaction_is_found(session: Session) -> None:
    made = add_transaction(session, 3, "ACME COFFEE")
    found = get_transaction(session, made)
    assert found is not None
    assert (found.id, found.description, found.amount_cents) == (made, "ACME COFFEE", -450)


def test_an_unknown_transaction_is_none(session: Session) -> None:
    assert get_transaction(session, 99) is None


# transaction_detail


def test_the_detail_of_an_unknown_transaction_is_none(session: Session) -> None:
    assert transaction_detail(session, 99) is None


def test_a_transaction_without_a_category(session: Session) -> None:
    made = add_transaction(session, 3, "SQ *ACME COFFEE #12", cents=-2599)
    assert transaction_detail(session, made) == TransactionDetail(
        id=made,
        date="2026-05-03",
        account="Test Card",
        description="SQ *ACME COFFEE #12",
        merchant="ACME COFFEE",
        amount="-$25.99",
        card="",
        category="",
        set_by="",
    )


def test_the_card_is_masked(session: Session) -> None:
    made = add_transaction(session, 3, "ACME COFFEE", card="4321")
    detail = transaction_detail(session, made)
    assert detail is not None
    assert detail.card == "••4321"


def test_a_category_set_by_hand(session: Session) -> None:
    made = add_transaction(session, 3, "FOOBAR GROCERY")
    set_category_by_hand(session, made, "groceries")
    detail = transaction_detail(session, made)
    assert detail is not None
    assert (detail.category, detail.set_by) == ("Groceries", "by hand")


def test_a_category_set_by_a_rule(session: Session) -> None:
    made = add_transaction(session, 3, "ACME COFFEE")
    create_rule(session, "ACME", "Dining")
    rule = create_rule(session, "ACME COFFEE", "Coffee & Dessert", priority=5)
    assign_by_rule(session, made, rule)
    detail = transaction_detail(session, made)
    assert detail is not None
    assert (detail.category, detail.set_by) == ("Coffee & Dessert", f"by rule {rule.id}")


# category_choices


def test_groups_and_their_categories_in_name_order(session: Session) -> None:
    create_category(session, "aquarium", "Home")
    choices = category_choices(session)
    groups = [group for group, _ in choices]
    assert groups == sorted(groups, key=str.lower)
    names = dict(choices)["Home"]
    assert names[0] == "aquarium"
    assert names == sorted(names, key=str.lower)
    every_name = {name for _, found in choices for name in found}
    assert every_name.isdisjoint(groups)


# The pages that show them


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")


@pytest.mark.parametrize("path", ["/categories", "/transactions/1"])
def test_the_pages_need_a_migrated_database(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 503
    assert "The database is not up to date. Run: fin db upgrade" in response.text


@pytest.mark.parametrize("path", ["/transactions/abc/category", "/transactions/abc/category/clear"])
def test_a_form_for_a_transaction_id_that_is_not_a_number(client: TestClient, path: str) -> None:
    upgrade_to_head()
    client.get("/categories")
    response = client.post(
        path,
        data={"csrf": client.cookies["fin_csrf"], "category": "Dining"},
        follow_redirects=False,
    )
    assert response.status_code == 404
    assert "transaction not found" in response.text
