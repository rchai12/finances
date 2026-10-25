from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import (
    CategoryExistsError,
    create_group,
    get_category_by_name,
    list_changes,
)
from finances.domain.models import Category
from finances.views.categories import CategoryLine, category_lines
from finances.web.app import create_app
from tests.support import WEB_PORT, post, run, table_rows

TAKEN = "a category with this name already exists"


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        yield opened


@pytest.fixture
def migrated(tmp_settings: Settings) -> Settings:
    upgrade_to_head()
    return tmp_settings


@pytest.fixture
def home(tmp_settings: Settings) -> TestClient:
    upgrade_to_head()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/categories")
    return client


def test_create_group_records_one_change_and_a_refusal_records_none(session: Session) -> None:
    made = create_group(session, "Pets")
    added = [item for item in list_changes(session) if item.action == "category_added"]
    assert [(item.kind, item.record_id, item.after) for item in added] == [
        ("category", made.id, "Pets")
    ]
    before = len(list_changes(session))
    with pytest.raises(ValueError, match="a group is for transfers or for income, not both"):
        create_group(session, "Moves", transfer=True, income=True)
    assert len(list_changes(session)) == before


def test_outer_spaces_are_stripped(session: Session) -> None:
    made = create_group(session, "  Pets  ")
    assert made.name == "Pets"
    found = get_category_by_name(session, "Pets")
    assert found is not None
    assert found.name == "Pets"


def test_a_name_that_differs_only_in_case_is_taken(session: Session) -> None:
    with pytest.raises(CategoryExistsError, match=TAKEN):
        create_group(session, "food")


def test_an_empty_transfer_group_is_one_line() -> None:
    group = Category(99, "Between Banks", None, True, False, False)
    assert category_lines([(group, [])]) == [CategoryLine("Between Banks", "", "transfer")]


def test_an_empty_group_can_be_deleted(migrated: Settings) -> None:
    run("categories", "add-group", "--name", "Pets")
    result = run("categories", "delete", "--name", "Pets")
    assert (result.exit_code, result.output) == (0, 'Deleted group "Pets".\n')
    rows = table_rows(run("categories", "list").output)
    assert not any(row[:2] == ["Pets", ""] for row in rows)


def test_a_transfer_group_that_is_sensitive(home: TestClient) -> None:
    post(home, "/categories/groups/add", name="Between Banks", kind="transfer", sensitive="on")
    engine = get_engine()
    with session_scope(engine) as session:
        found = get_category_by_name(session, "Between Banks")
    engine.dispose()
    assert found is not None
    assert found.group_id is None
    assert (found.is_transfer, found.is_income, found.is_sensitive) == (True, False, True)


def test_a_form_without_the_token_is_refused(home: TestClient) -> None:
    response = home.post("/categories/groups/add", data={}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")
