from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finances.analysis.dashboard import dashboard
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import rename_category, set_budget
from finances.web.app import create_app
from tests.support import WEB_PORT, page, post, texts


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("finances.web.app._today", lambda: date(2026, 5, 25))
    upgrade_to_head()
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


def test_dashboard_with_a_budget_and_no_spending(client: TestClient, tmp_path: Path) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        set_budget(session, "Travel", 10000)
        found = dashboard(session, date(2026, 5, 25), tmp_path)
    engine.dispose()
    assert len(found.budgets) == 1
    line = found.budgets[0]
    assert (line.name, line.spent_cents, line.target_cents) == ("Travel", 0, 10000)
    home = page(client, "/")
    start = home.rows.index(["Budget", "Spent", "Target", "Used", "Month gone"])
    assert home.rows[start + 1] == ["Travel", "$0.00", "$100.00", "0%", "81%"]


def test_budget_links_encode_ampersands(client: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        rename_category(session, "Travel", "Travel & Fun")
        set_budget(session, "Travel & Fun", 10000)
        set_budget(session, "Coffee & Dessert", 4500)
    engine.dispose()
    client.get("/budgets")
    found = page(client, "/budgets")
    links = [link for link in found.links if link.startswith("/transactions?")]
    assert (
        "/transactions?from=2026-05-01&to=2026-05-31&category=Coffee%20%26%20Dessert"
        "&kind=spending&limit=1000"
    ) in links
    assert (
        "/transactions?from=2026-05-01&to=2026-05-31&group=Travel%20%26%20Fun"
        "&kind=spending&limit=1000"
    ) in links


def test_no_budgets_left_shows_empty(client: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        set_budget(session, "Dining", 25000)
    engine.dispose()
    client.get("/budgets")
    response = post(client, "/budgets/remove", name="Dining")
    assert response.status_code == 303
    found = page(client, "/budgets")
    assert found.rows == []
    assert ("empty", "No budgets.") in found.paragraphs
    assert texts(found, "summary") == ["Budgets for 2026-05."]
