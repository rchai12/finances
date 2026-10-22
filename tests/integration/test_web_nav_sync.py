import re

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, texts

BUTTON = re.compile(
    r'<form method="post" action="/sync/run" class="nav-sync">'
    r'<input type="hidden" name="csrf" value="([A-Za-z0-9_-]{43})">'
    r'<button type="submit">Sync now</button></form>'
)
PAGES = [
    "/",
    "/accounts",
    "/people",
    "/transactions",
    "/statements",
    "/categories",
    "/transfers",
    "/reports",
    "/insights",
    "/budgets",
    "/ahead",
    "/sync",
    "/backups",
]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


def menu(html: str) -> str:
    return html[html.index("<nav>") : html.index("</nav>")]


@pytest.mark.parametrize("path", PAGES)
def test_every_page_ends_its_menu_with_the_button(client: TestClient, path: str) -> None:
    upgrade_to_head()
    response = client.get(path)
    assert response.status_code == 200
    assert BUTTON.findall(menu(response.text)) == [client.cookies["fin_csrf"]]
    assert menu(response.text).rstrip().endswith("</form>")


def test_pressing_it_on_another_page_runs_a_sync(client: TestClient) -> None:
    upgrade_to_head()
    token = BUTTON.findall(client.get("/reports").text)[0]
    response = client.post(
        "/sync/run",
        data={"csrf": token},
        headers={"Origin": f"http://127.0.0.1:{WEB_PORT}"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert texts(Page(response.text), "empty") == ["No mapped accounts."]


def test_the_not_migrated_page_has_it_and_pressing_it_says_so(client: TestClient) -> None:
    response = client.get("/reports")
    assert response.status_code == 503
    tokens = BUTTON.findall(menu(response.text))
    assert tokens == [client.cookies["fin_csrf"]]
    pressed = client.post("/sync/run", data={"csrf": tokens[0]})
    assert pressed.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(pressed.text).paragraphs


def test_the_button_sits_at_the_right_of_the_menu(client: TestClient) -> None:
    assert "nav .nav-sync { margin: 0 0 0 auto; }" in client.get("/static/app.css").text
