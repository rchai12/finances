import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    accept_proposal,
    count_open_proposals,
    create_account,
    propose_category,
)
from finances.web.app import create_app
from tests.integration.test_web_menus import COUNT, CURRENT
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page

MENUS = {
    "Money": ["/accounts", "/transactions", "/statements", "/transfers"],
    "Plan": ["/reports", "/insights", "/budgets", "/ahead"],
    "Organize": ["/categories", "/people", "/shared"],
    "System": ["/sync", "/backups", "/history"],
}
BLOCK = re.compile(
    r'<details class="menu[^"]*" name="menu">\s*<summary>(\w+)</summary>\s*'
    r'<div class="menu-items">(.*?)</div>',
    re.S,
)
HREF = re.compile(r'<a href="([^"]*)"')


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    upgrade_to_head()
    return client


def _menus(html: str) -> dict[str, list[str]]:
    return {name: HREF.findall(body) for name, body in BLOCK.findall(html)}


def test_count_open_proposals_is_zero_then_one_when_one_is_accepted(home: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        assert count_open_proposals(session) == 0
        account = create_account(session, "Test Checking", "Test Bank", "checking")
        for number in (1, 2):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, number),
                    amount_cents=-1000 * number,
                    description="ACME COFFEE",
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        propose_category(session, 1, "Coffee & Dessert", "a coffee shop")
        propose_category(session, 2, "Coffee & Dessert", "a coffee shop")
        accept_proposal(session, 1)
        assert count_open_proposals(session) == 1
    engine.dispose()


def test_an_error_page_before_migration_has_no_count(client: TestClient) -> None:
    response = client.get("/accounts")
    assert response.status_code == 503
    assert Page(response.text).paragraphs == [("error", WEB_NOT_MIGRATED)]
    assert COUNT not in response.text


def test_each_link_sits_in_the_menu_the_goal_names(home: TestClient) -> None:
    html = home.get("/").text
    found = _menus(html)
    assert found == MENUS
    for href in ("/", "/review"):
        assert href in HREF.findall(html)
        assert all(href not in links for links in found.values())


def test_the_account_page_marks_money(home: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Checking", "Test Bank", "checking")
    engine.dispose()
    html = home.get("/account?name=Test Checking").text
    assert CURRENT.findall(html) == ["Money"]
    assert html.count('aria-current="page"') == 1
