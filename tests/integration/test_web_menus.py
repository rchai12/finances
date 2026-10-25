import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, decline_proposal, propose_category
from finances.web.app import create_app
from finances.web.login import set_password
from tests.support import WEB_PORT

COUNT = '<span class="count" title="Proposals waiting for review">'
CURRENT = re.compile(r'<details class="menu current" name="menu">\s*<summary>(\w+)</summary>')


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    upgrade_to_head()
    return client


@pytest.fixture
def proposals(home: TestClient) -> TestClient:
    """Three category proposals, the third declined: two are waiting."""
    engine = get_engine()
    with session_scope(engine) as session:
        account = create_account(session, "Test Checking", "Test Bank", "checking")
        for number in (1, 2, 3):
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
        for number in (1, 2, 3):
            propose_category(session, number, "Coffee & Dessert", "a coffee shop")
        decline_proposal(session, 3)
    engine.dispose()
    return home


def test_the_menus_and_the_top_links_in_order(home: TestClient) -> None:
    html = home.get("/").text
    assert re.findall(r"<summary>(\w+)</summary>", html) == ["Money", "Plan", "Organize", "System"]
    marks = [">Home</a>", "<summary>Money", "<summary>Plan", "<summary>Organize"]
    marks += [">Review</a>", "<summary>System", ">Log out</button>", ">Sync now</button>"]
    assert [html.index(mark) for mark in marks] == sorted(html.index(mark) for mark in marks)


@pytest.mark.parametrize(
    ("path", "menus"),
    [
        ("/", []),
        ("/accounts", ["Money"]),
        ("/transactions", ["Money"]),
        ("/reports", ["Plan"]),
        ("/ahead", ["Plan"]),
        ("/people", ["Organize"]),
        ("/review", []),
        ("/sync", ["System"]),
        ("/history", ["System"]),
    ],
)
def test_the_menu_holding_the_page_is_marked(home: TestClient, path: str, menus: list[str]) -> None:
    html = home.get(path).text
    assert CURRENT.findall(html) == menus
    assert html.count('aria-current="page"') == 1


def test_review_shows_how_many_proposals_wait(proposals: TestClient) -> None:
    for path in ("/", "/accounts", "/review"):
        assert f">Review</a>{COUNT}2</span>" in proposals.get(path).text, path


def test_no_count_when_nothing_waits(home: TestClient) -> None:
    assert COUNT not in home.get("/").text


def test_no_count_on_the_login_page(proposals: TestClient) -> None:
    set_password("correct horse battery", None)
    response = proposals.get("/login")
    assert response.status_code == 200
    assert COUNT not in response.text


def test_a_page_shown_before_the_database_is_migrated_has_no_count(client: TestClient) -> None:
    response = client.get("/backups")
    assert response.status_code == 200
    assert COUNT not in response.text
