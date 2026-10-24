import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import list_changes, set_tax_relevant
from finances.web.app import create_app
from tests.integration.test_web_year import tax_forms
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, post, texts


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    upgrade_to_head()
    client.get("/categories")
    return client


def test_get_on_the_tax_path_is_405(home: TestClient) -> None:
    assert home.get("/categories/tax").status_code == 405


def test_year_needs_a_migrated_database(client: TestClient) -> None:
    response = client.get("/year")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_a_year_with_no_tax_relevant_categories(home: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        for name in ("Medical", "Gifts & Donations", "Taxes"):
            set_tax_relevant(session, name, False)
    engine.dispose()
    found = page(home, "/year?year=2026")
    assert "No tax-relevant categories." in texts(found, "empty")


def test_a_refused_tax_form_keeps_the_page(home: TestClient) -> None:
    response = post(home, "/categories/tax", category="Health", tax="on")
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == ["a group cannot be tax-relevant; mark its categories"]
    assert ["Food", "Groceries", ""] in found.rows
    assert tax_forms(found) == ["Gifts & Donations", "Medical", "Taxes"]
    assert found.all("/categories/tax")


def test_marking_an_already_tax_relevant_category_records_nothing(home: TestClient) -> None:
    response = post(home, "/categories/tax", category="Medical", tax="on")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/categories?notice=tax-set",
    )
    engine = get_engine()
    with session_scope(engine) as session:
        logged = list_changes(session, action="category_tax_set")
    engine.dispose()
    assert logged == []


def test_a_form_without_a_valid_token_is_refused(home: TestClient) -> None:
    response = home.post("/categories/tax", data={}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")
