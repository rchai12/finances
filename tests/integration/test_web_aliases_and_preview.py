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
    list_rules,
)
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts

PREVIEW_HEADINGS = ["ID", "Date", "Account", "Merchant", "Amount", "Now"]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Card: 1 ACME CAFE, 2 and 3 ACME COFFEE, 4 FOOBAR GROCERY; rule 1 puts ACME COFFEE in
    Coffee & Dessert, so 2 and 3 are categorized and 1 and 4 are not."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            (
                (-450, "ACME CAFE"),
                (-500, "ACME COFFEE"),
                (-700, "SQ *ACME COFFEE 12345"),
                (-2599, "FOOBAR GROCERY #77"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, number),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        create_rule(session, "ACME COFFEE", "Coffee & Dessert")
        categorize(session)
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


def rule_count() -> int:
    engine = get_engine()
    with session_scope(engine) as session:
        found = len(list_rules(session))
    engine.dispose()
    return found


def test_no_aliases_yet(home: TestClient) -> None:
    found = page(home, "/categories")
    assert texts(found, "empty") == ["No merchant aliases."]
    assert sorted(found.find("/categories/aliases/add")["inputs"]) == ["csrf", "source", "target"]


def test_merging_on_the_page(home: TestClient) -> None:
    response = post(home, "/categories/aliases/add", source=" acme  cafe ", target="acme coffee")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/categories?notice=merchant-merged",
    )
    found = page(home, "/categories?notice=merchant-merged")
    assert texts(found, "notice") == ["Merchants merged, and the rules were run again."]
    assert found.rows[-2:] == [["From", "To", ""], ["ACME CAFE", "ACME COFFEE", "Delete"]]
    assert found.find("/categories/aliases/delete")["inputs"]["source"] == ("hidden", "ACME CAFE")
    assert categories_of() == {1: "Coffee & Dessert", 2: "Coffee & Dessert", 3: "Coffee & Dessert"}


def test_unmerging_on_the_page(home: TestClient) -> None:
    post(home, "/categories/aliases/add", source="ACME CAFE", target="ACME COFFEE")
    response = post(home, "/categories/aliases/delete", source="ACME CAFE")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/categories?notice=merchant-unmerged",
    )
    found = page(home, "/categories?notice=merchant-unmerged")
    assert texts(found, "notice") == ["Merchant alias removed, and the rules were run again."]
    assert texts(found, "empty") == ["No merchant aliases."]
    assert categories_of() == {2: "Coffee & Dessert", 3: "Coffee & Dessert"}


@pytest.mark.parametrize(
    ("path", "fields", "message"),
    [
        (
            "/categories/aliases/add",
            {"source": "ACME CAFE", "target": "Acme Cafe"},
            "a merchant cannot be merged into itself",
        ),
        ("/categories/aliases/delete", {"source": "BAZ CAFE"}, "alias not found"),
    ],
)
def test_a_refused_alias(home: TestClient, path: str, fields: dict, message: str) -> None:
    response = post(home, path, **fields)
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == [message]
    assert found.find("/categories/aliases/add")["inputs"]["source"] == (
        "text",
        fields["source"] if path.endswith("add") else "",
    )


def test_previewing_a_rule(home: TestClient) -> None:
    response = post(
        home,
        "/categories/rules/preview",
        pattern="acme",
        match="contains",
        priority="5",
        category="Dining",
    )
    assert response.status_code == 200
    found = Page(response.text)
    assert texts(found, "preview") == ["This rule would put 3 transactions in Dining."]
    start = found.rows.index(PREVIEW_HEADINGS)
    assert found.rows[start + 1 : start + 4] == [
        ["3", "2026-05-03", "Test Card", "ACME COFFEE", "-$7.00", "Coffee & Dessert"],
        ["2", "2026-05-02", "Test Card", "ACME COFFEE", "-$5.00", "Coffee & Dessert"],
        ["1", "2026-05-01", "Test Card", "ACME CAFE", "-$4.50", ""],
    ]
    inputs = found.find("/categories/rules/add")["inputs"]
    assert (inputs["pattern"], inputs["priority"]) == (("text", "acme"), ("text", "5"))
    assert rule_count() == 1
    assert categories_of() == {2: "Coffee & Dessert", 3: "Coffee & Dessert"}


def test_a_refused_preview(home: TestClient) -> None:
    response = post(
        home,
        "/categories/rules/preview",
        pattern="acme coffee",
        match="contains",
        priority="",
        category="Dining",
    )
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == ["a rule with this pattern and match already exists"]
    assert texts(found, "preview") == []


def test_both_rule_forms_offer_a_preview(home: TestClient) -> None:
    for path in ("/categories", "/transactions/1"):
        assert 'formaction="/categories/rules/preview">Preview</button>' in home.get(path).text
