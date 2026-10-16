from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule, set_budget
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, post, texts

TODAY = date(2026, 5, 25)
HEADINGS = ["Budget", "Kind", "Target", "Spent", "Left", "Used", "Month gone", ""]
AMOUNT = "a budget must be an amount from $0.01 to $1,000,000.00"
MAY = [
    HEADINGS,
    ["Dining", "category", "$250.00", "$300.00", "-$50.00", "120%", "81%", "Remove"],
    ["Food", "group", "$400.00", "$404.50", "-$4.50", "101%", "81%", "Remove"],
    ["Groceries", "category", "$200.00", "$100.00", "$100.00", "50%", "81%", "Remove"],
    ["Travel", "group", "$100.00", "$0.00", "$100.00", "0%", "81%", "Remove"],
]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """The data of tests/e2e/test_cli_budgets.py, with its four budgets set."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (day, cents, description) in enumerate(
            (
                (5, -20000, "ACME DINER"),
                (12, -10000, "ACME DINER"),
                (6, -12000, "FOOBAR GROCERY"),
                (9, 2000, "FOOBAR GROCERY"),
                (7, -450, "ACME COFFEE"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for pattern, category in (
            ("ACME DINER", "Dining"),
            ("FOOBAR", "Groceries"),
            ("ACME COFFEE", "Coffee & Dessert"),
        ):
            create_rule(session, pattern, category)
        categorize(session)
        for name, cents in (
            ("Dining", 25000),
            ("Food", 40000),
            ("Groceries", 20000),
            ("Travel", 10000),
        ):
            set_budget(session, name, cents)
    engine.dispose()
    client.get("/budgets")
    return client


def test_the_menu_has_budgets(home: TestClient) -> None:
    html = home.get("/budgets").text
    assert 'href="/budgets" aria-current="page">Budgets</a>' in html
    assert html.count('aria-current="page"') == 1
    assert 'href="/budgets">Budgets</a>' in home.get("/accounts").text
    assert "<script" not in html


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get("/budgets")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_this_months_budgets(home: TestClient) -> None:
    found = page(home, "/budgets")
    assert found.rows == MAY
    assert texts(found, "summary") == ["Budgets for 2026-05.", "Over budget: 2."]
    assert found.find("/budgets")["inputs"]["month"] == ("month", "")
    assert [form["inputs"]["name"] for form in found.all("/budgets/remove")] == [
        ("hidden", "Dining"),
        ("hidden", "Food"),
        ("hidden", "Groceries"),
        ("hidden", "Travel"),
    ]
    links = [link for link in found.links if link.startswith("/transactions?")]
    assert links[:2] == [
        "/transactions?from=2026-05-01&to=2026-05-31&category=Dining&kind=spending&limit=1000",
        "/transactions?from=2026-05-01&to=2026-05-31&group=Food&kind=spending&limit=1000",
    ]


def test_another_month(home: TestClient) -> None:
    found = page(home, "/budgets?month=2026-04")
    assert found.rows[1] == [
        "Dining",
        "category",
        "$250.00",
        "$0.00",
        "$250.00",
        "0%",
        "100%",
        "Remove",
    ]
    assert texts(found, "summary") == ["Budgets for 2026-04.", "Over budget: 0."]
    response = home.get("/budgets?month=2026-13")
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", "month must be a year and month, like 2026-05") in found.paragraphs
    assert found.rows == []


def test_set_a_budget(home: TestClient) -> None:
    response = post(home, "/budgets/set", name="Coffee & Dessert", amount="45.50")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/budgets?notice=budget-set",
    )
    found = page(home, response.headers["location"])
    assert ("notice", "Budget saved.") in found.paragraphs
    assert [
        "Coffee & Dessert",
        "category",
        "$45.50",
        "$4.50",
        "$41.00",
        "10%",
        "81%",
        "Remove",
    ] in found.rows
    response = post(home, "/budgets/set", name="dining", amount="$300.00")
    assert response.status_code == 303
    assert page(home, "/budgets").rows[2][:3] == ["Dining", "category", "$300.00"]


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"name": "Nope", "amount": "10"}, "category not found"),
        ({"name": "Dining", "amount": "ten"}, AMOUNT),
        ({"name": "Dining", "amount": "0"}, AMOUNT),
        ({"name": "Dining", "amount": "1000000.01"}, AMOUNT),
    ],
)
def test_a_refused_budget_keeps_the_form(home: TestClient, fields: dict, message: str) -> None:
    response = post(home, "/budgets/set", **fields)
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", message) in found.paragraphs
    form = found.find("/budgets/set")
    assert form["inputs"]["amount"] == ("text", fields["amount"])
    assert found.rows == MAY


def test_remove_a_budget(home: TestClient) -> None:
    response = post(home, "/budgets/remove", name="Groceries")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/budgets?notice=budget-removed",
    )
    found = page(home, response.headers["location"])
    assert ("notice", "Budget removed.") in found.paragraphs
    assert [row[0] for row in found.rows[1:]] == ["Dining", "Food", "Travel"]


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("Nope", "category not found"),
        ("Coffee & Dessert", "there is no budget for Coffee & Dessert"),
    ],
)
def test_a_refused_removal(home: TestClient, name: str, message: str) -> None:
    response = post(home, "/budgets/remove", name=name)
    assert response.status_code == 400
    assert ("error", message) in Page(response.text).paragraphs


@pytest.mark.parametrize("path", ["/budgets/set", "/budgets/remove"])
def test_a_form_without_the_token_is_refused(home: TestClient, path: str) -> None:
    response = home.post(path, data={"name": "Dining", "amount": "1"}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")
    assert home.get(path).status_code == 405


def test_the_dashboard_shows_this_months_budgets(home: TestClient) -> None:
    found = page(home, "/")
    start = found.rows.index(["Budget", "Spent", "Target", "Used", "Month gone"])
    assert found.rows[start : start + 5] == [
        ["Budget", "Spent", "Target", "Used", "Month gone"],
        ["Dining", "$300.00", "$250.00", "120%", "81%"],
        ["Food", "$404.50", "$400.00", "101%", "81%"],
        ["Groceries", "$100.00", "$200.00", "50%", "81%"],
        ["Travel", "$0.00", "$100.00", "0%", "81%"],
    ]
    assert "/budgets" in found.links


def test_the_dashboard_without_budgets(client: TestClient) -> None:
    upgrade_to_head()
    assert ("hint", "No budgets yet.") in page(client, "/").paragraphs
