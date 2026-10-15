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

POSTS = ["/accounts/rename", "/accounts/active", "/transactions/bulk"]


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


def bulk(client: TestClient, **fields) -> object:
    return client.post(
        "/transactions/bulk",
        data={"csrf": client.cookies["fin_csrf"], **fields},
        follow_redirects=False,
    )


def redirected(response, location: str) -> bool:
    return (response.status_code, response.headers.get("location")) == (303, location)


@pytest.mark.parametrize("path", POSTS)
def test_a_form_without_the_token_is_refused(home: TestClient, path: str) -> None:
    response = home.post(path, data={}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")


# Accounts


def test_rename_close_and_reopen_an_account(home: TestClient) -> None:
    response = post(home, "/accounts/rename", account="Test Card", to="Family Card")
    assert redirected(response, "/accounts?notice=account-renamed")
    found = page(home, response.headers["location"])
    assert ("notice", "Account renamed.") in found.paragraphs
    assert [row[0] for row in found.rows[1:]] == ["Family Card", "Test Checking"]
    response = post(home, "/accounts/active", account="Family Card", active="false")
    assert redirected(response, "/accounts?notice=account-closed")
    found = page(home, response.headers["location"])
    assert ("notice", "Account closed.") in found.paragraphs
    assert [row[0] for row in found.rows[1:]] == ["Test Checking"]
    response = post(home, "/accounts/active", account="Family Card", active="true")
    assert redirected(response, "/accounts?notice=account-reopened")
    assert ("notice", "Account reopened.") in page(home, response.headers["location"]).paragraphs


@pytest.mark.parametrize(
    ("path", "fields", "message"),
    [
        (
            "/accounts/rename",
            {"account": "Test Card", "to": "Test Checking"},
            "an account with this name already exists",
        ),
        ("/accounts/rename", {"account": "Nope", "to": "Other"}, "account not found"),
        ("/accounts/active", {"account": "Test Card", "active": "maybe"}, "choose Close or Reopen"),
        ("/accounts/active", {"account": "Nope", "active": "false"}, "account not found"),
    ],
)
def test_a_refused_account_change(home: TestClient, path: str, fields: dict, message: str) -> None:
    response = post(home, path, **fields)
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", message) in found.paragraphs
    assert [row[0] for row in found.rows[1:]] == ["Test Card", "Test Checking"]


def test_a_refused_rename_keeps_the_new_name(home: TestClient) -> None:
    response = post(home, "/accounts/rename", account="Test Checking", to="Test Card")
    assert Page(response.text).find("/accounts/rename")["inputs"]["to"] == ("text", "Test Card")


# Several transactions at once


def test_every_row_has_a_checkbox_and_select_all_checks_them(home: TestClient) -> None:
    html = home.get("/transactions?text=acme").text
    assert 'name="id" value="2">' in html and 'name="id" value="1">' in html
    assert "checked" not in html.split('action="/transactions/bulk"')[1]
    found = Page(html)
    assert found.rows[1][0] == "2026-05-02"
    assert found.find("/transactions/bulk")["inputs"]["back"] == ("hidden", "text=acme")
    assert "/transactions?text=acme&select=all" in found.links
    html = home.get("/transactions?text=acme&select=all").text
    assert 'name="id" value="2" checked>' in html and 'name="id" value="1" checked>' in html
    assert Page(html).find("/transactions/bulk")["inputs"]["back"] == ("hidden", "text=acme")
    assert "/transactions?text=acme" in Page(html).links


def test_set_and_clear_several_transactions(home: TestClient) -> None:
    response = bulk(
        home,
        id=["1", "2"],
        category="Dining",
        action="set",
        back="text=acme&notice=x&evil=1&select=all",
    )
    assert redirected(response, "/transactions?text=acme&notice=bulk-set")
    found = page(home, response.headers["location"])
    assert ("notice", "Category set by hand on the chosen transactions.") in found.paragraphs
    assert [row[3] for row in found.rows[1:]] == ["Dining", "Dining"]
    response = bulk(home, id=["1", "2"], category="", action="clear", back="")
    assert redirected(response, "/transactions?notice=bulk-cleared")
    assert (
        "notice",
        "The chosen transactions were left to the rules, and the rules were run again.",
    ) in page(home, response.headers["location"]).paragraphs
    assert categories_of() == {
        1: "Coffee & Dessert",
        2: "Coffee & Dessert",
        3: "Groceries",
        4: "Dining",
    }


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"category": "Dining", "action": "set"}, "choose at least one transaction"),
        ({"id": ["1", "x"], "category": "Dining", "action": "set"}, "transaction not found"),
        ({"id": ["1", "99"], "category": "Dining", "action": "set"}, "transaction not found"),
        ({"id": ["1"], "category": "", "action": "set"}, "category not found"),
        (
            {"id": ["1"], "category": "Food", "action": "set"},
            "rules and transactions take a category, not a group",
        ),
        (
            {"id": ["1"], "category": "Dining", "action": "drop"},
            "choose Set category or Leave to the rules",
        ),
    ],
)
def test_a_refused_bulk_change(home: TestClient, fields: dict, message: str) -> None:
    response = bulk(home, back="text=acme", **fields)
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", message) in found.paragraphs
    assert "<h1>Transactions</h1>" in response.text
    assert [row[0] for row in found.rows[1:]] == ["2026-05-02", "2026-05-01"]
    assert categories_of()[1] == "Coffee & Dessert"
