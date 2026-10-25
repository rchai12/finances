import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import get_category_by_name
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts

KIND = "a group's kind must be spending, transfer, or income"


@pytest.fixture
def home(tmp_settings: Settings) -> TestClient:
    upgrade_to_head()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/categories")
    return client


def group_flags(name: str) -> tuple[bool, bool, bool] | None:
    engine = get_engine()
    with session_scope(engine) as session:
        found = get_category_by_name(session, name)
    engine.dispose()
    if found is None:
        return None
    assert found.group_id is None
    return found.is_transfer, found.is_income, found.is_sensitive


def test_the_form(home: TestClient) -> None:
    form = page(home, "/categories").find("/categories/groups/add")
    assert form["inputs"]["sensitive"] == ("checkbox", "on")
    assert form["selects"]["kind"] == [("spending", True), ("transfer", False), ("income", False)]


def test_adding_a_group(home: TestClient) -> None:
    response = post(home, "/categories/groups/add", name="Pets", kind="spending")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/categories?notice=group-added",
    )
    found = page(home, response.headers["location"])
    assert texts(found, "notice") == ["Group added."]
    groups = [name for name, _ in found.find("/categories/add")["selects"]["group"]]
    assert "Pets" in groups
    assert group_flags("Pets") == (False, False, False)


def test_adding_an_income_group_that_is_sensitive(home: TestClient) -> None:
    post(home, "/categories/groups/add", name="Side Gigs", kind="income", sensitive="on")
    assert group_flags("Side Gigs") == (False, True, True)


def test_an_unknown_kind_is_refused_and_the_form_kept(home: TestClient) -> None:
    response = post(home, "/categories/groups/add", name="Pets", kind="savings", sensitive="on")
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == [KIND]
    form = found.find("/categories/groups/add")
    assert form["inputs"]["name"][1] == "Pets"
    assert group_flags("Pets") is None


def test_a_taken_name_is_refused(home: TestClient) -> None:
    response = post(home, "/categories/groups/add", name="Dining", kind="spending")
    assert (response.status_code, texts(Page(response.text), "error")) == (
        400,
        ["a category with this name already exists"],
    )
