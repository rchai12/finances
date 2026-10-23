from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_person,
    create_rule,
    record_change,
    set_budget,
    set_category_by_hand,
)
from finances.domain.audit import Change
from finances.views.audit import change_link
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts

HEADINGS = ["When (UTC)", "Who", "Action", "Record", "Before", "After"]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def changed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Five changes: a card on 24 May, then a person, a rule, a category set by hand, and a
    budget on 25 May."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        monkeypatch.setattr(
            "finances.db.repositories.audit._now", lambda: datetime(2026, 5, 24, 9, 0, tzinfo=UTC)
        )
        create_account(session, "Test Card", "Test Bank", "credit_card")
        monkeypatch.setattr(
            "finances.db.repositories.audit._now", lambda: datetime(2026, 5, 25, 14, 3, tzinfo=UTC)
        )
        create_person(session, "Pat Example")
        create_rule(session, "ACME", "Dining")
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=date(2026, 5, 2),
                amount_cents=-500,
                description="ACME COFFEE",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
        session.flush()
        set_category_by_hand(session, 1, "Groceries")
        set_budget(session, "Groceries", 15000)
    engine.dispose()
    return client


def test_the_history_newest_first_with_links(changed: TestClient) -> None:
    response = changed.get("/history")
    assert response.status_code == 200
    assert 'href="/history" aria-current="page">History</a>' in response.text
    found = Page(response.text)
    assert found.rows == [
        HEADINGS,
        ["2026-05-25 14:03", "person", "budget_set", "category 13", "", "$150.00"],
        ["2026-05-25 14:03", "person", "category_set", "transaction 1", "", "Groceries"],
        [
            "2026-05-25 14:03",
            "person",
            "rule_added",
            "rule 1",
            "",
            'contains "ACME" -> Dining (priority 0)',
        ],
        ["2026-05-25 14:03", "person", "person_added", "person 1", "", "Pat Example"],
        ["2026-05-24 09:00", "person", "account_added", "account 1", "", "Test Card"],
    ]
    links = [
        link
        for link in found.links
        if link in ("/categories", "/transactions/1", "/people", "/accounts")
    ]
    assert links[-5:] == ["/categories", "/transactions/1", "/categories", "/people", "/accounts"]


def test_one_action_and_one_day(changed: TestClient) -> None:
    assert page(changed, "/history?action=person_added").rows[1:] == [
        ["2026-05-25 14:03", "person", "person_added", "person 1", "", "Pat Example"]
    ]
    assert len(page(changed, "/history?since=2026-05-25").rows) == 5
    form = page(changed, "/history?action=budget_set&since=2026-05-25").find("/history")
    assert form["inputs"]["since"] == ("date", "2026-05-25")
    assert ("budget_set", True) in form["selects"]["action"]


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("action=nope", "choose an action from the list"),
        ("since=25-05-2026", "since must be a date as YYYY-MM-DD"),
    ],
)
def test_refused_filters(changed: TestClient, query: str, message: str) -> None:
    response = changed.get(f"/history?{query}")
    assert response.status_code == 400
    assert ("error", message) in Page(response.text).paragraphs


def test_nothing_yet(client: TestClient) -> None:
    upgrade_to_head()
    assert texts(page(client, "/history"), "empty") == ["No changes recorded."]


def test_only_the_newest_two_hundred(client: TestClient) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        for number in range(201):
            record_change(
                session, action="person_added", kind="person", record_id=number, after="P"
            )
    engine.dispose()
    found = page(client, "/history")
    assert len(found.rows) == 201
    assert texts(found, "hint") == [
        "Showing the 200 newest. Choose an action or a day to see others."
    ]


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get("/history")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


@pytest.mark.parametrize(
    ("kind", "record_id", "link"),
    [
        ("account", 3, "/accounts"),
        ("person", 1, "/people"),
        ("category", 13, "/categories"),
        ("rule", 2, "/categories"),
        ("transaction", 7, "/transactions/7"),
        ("transfer", 1, "/transfers"),
        ("statement", 4, "/statements"),
        ("backup", None, "/backups"),
    ],
)
def test_each_kind_links_to_its_page(kind: str, record_id: int | None, link: str) -> None:
    change = Change(
        1, datetime(2026, 5, 25, tzinfo=UTC), "person", "x", kind, record_id, None, None
    )
    assert change_link(change) == link
