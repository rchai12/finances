from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_rule,
    list_categories,
    list_category_assignments,
    set_category_by_hand,
)
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post

POSTS = ["/categories/rename", "/categories/delete", "/categories/rules/2"]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Card: 1 and 2 coffee, 3 groceries; checking 4 a
    paycheck set to Dining by hand; rule 1 ACME COFFEE, rule 2 FOOBAR."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        for number, (account, cents, description) in enumerate(
            (
                (card, -450, "SQ *ACME COFFEE"),
                (card, -500, "ACME COFFEE #12"),
                (card, -2599, "FOOBAR GROCERY #77"),
                (checking, 300000, "PAYCHECK EXAMPLE CORP"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, number),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        create_rule(session, "ACME COFFEE", "Coffee & Dessert")
        create_rule(session, "FOOBAR", "Groceries")
        categorize(session)
        set_category_by_hand(session, 4, "Dining")
    engine.dispose()
    client.get("/categories")
    return client


def categories_of() -> dict[int, str]:
    engine = get_engine()
    with session_scope(engine) as session:
        names = {category.id: category.name for category in list_categories(session)}
        found = {
            transaction_id: names[assignment.category_id]
            for transaction_id, assignment in list_category_assignments(session).items()
        }
    engine.dispose()
    return found


def redirected(response, location: str) -> bool:
    return (response.status_code, response.headers.get("location")) == (303, location)


@pytest.mark.parametrize("path", POSTS)
def test_a_form_without_the_token_is_refused(home: TestClient, path: str) -> None:
    response = home.post(path, data={}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")


# Categories and rules


def test_rename_a_category(home: TestClient) -> None:
    response = post(home, "/categories/rename", name="Coffee & Dessert", to="Coffee")
    assert redirected(response, "/categories?notice=category-renamed")
    found = page(home, response.headers["location"])
    assert ("notice", "Category renamed.") in found.paragraphs
    assert ["Food", "Coffee", ""] in found.rows
    options = found.find("/categories/rename")["selects"]["name"]
    assert ("Food", False) in options and ("Coffee", False) in options


def test_a_refused_rename_keeps_the_form(home: TestClient) -> None:
    response = post(home, "/categories/rename", name="Dining", to="Groceries")
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", "a category with this name already exists") in found.paragraphs
    form = found.find("/categories/rename")
    assert ("Dining", True) in form["selects"]["name"]
    assert form["inputs"]["to"] == ("text", "Groceries")


def test_delete_a_category_after_moving_what_uses_it(home: TestClient) -> None:
    response = post(home, "/categories/delete", name="Coffee & Dessert", move_to="")
    assert response.status_code == 400
    found = Page(response.text)
    assert (
        "error",
        "Coffee & Dessert is in use (transactions: 2, rules: 1); choose a category to move them to",
    ) in found.paragraphs
    assert ("Coffee & Dessert", True) in found.find("/categories/delete")["selects"]["name"]
    response = post(home, "/categories/delete", name="Coffee & Dessert", move_to="Dining")
    assert redirected(response, "/categories?notice=category-deleted")
    found = page(home, response.headers["location"])
    assert ("notice", "Category deleted.") in found.paragraphs
    assert ["Food", "Coffee & Dessert", ""] not in found.rows
    assert categories_of() == {1: "Dining", 2: "Dining", 3: "Groceries", 4: "Dining"}


def test_edit_a_rule(home: TestClient) -> None:
    assert "/categories/rules/2" in page(home, "/categories").links
    found = page(home, "/categories/rules/2")
    form = found.find("/categories/rules/2")
    assert (form["inputs"]["pattern"], form["inputs"]["priority"]) == (
        ("text", "FOOBAR"),
        ("text", "0"),
    )
    assert ("contains", True) in form["selects"]["match"]
    assert ("Groceries", True) in form["selects"]["category"]
    response = post(
        home,
        "/categories/rules/2",
        pattern="FOOBAR",
        match="contains",
        priority="3",
        category="Dining",
    )
    assert redirected(response, "/categories?notice=rule-changed")
    found = page(home, response.headers["location"])
    assert ("notice", "Rule changed, and the rules were run again.") in found.paragraphs
    assert ["2", "3", "contains", "FOOBAR", "Dining", "Delete"] in found.rows
    assert categories_of()[3] == "Dining"


@pytest.mark.parametrize("path", ["/categories/rules/9", "/categories/rules/x"])
def test_an_unknown_rule(home: TestClient, path: str) -> None:
    for response in (
        home.get(path),
        post(home, path, pattern="X", match="contains", priority="0", category="Dining"),
    ):
        assert response.status_code == 404
        assert ("error", "rule not found") in Page(response.text).paragraphs


def test_a_refused_rule_edit_keeps_what_was_typed(home: TestClient) -> None:
    response = post(
        home,
        "/categories/rules/2",
        pattern="BAZ",
        match="contains",
        priority="x",
        category="Dining",
    )
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", "priority must be a whole number") in found.paragraphs
    form = found.find("/categories/rules/2")
    assert (form["inputs"]["pattern"], form["inputs"]["priority"]) == (
        ("text", "BAZ"),
        ("text", "x"),
    )
    assert categories_of()[3] == "Groceries"
