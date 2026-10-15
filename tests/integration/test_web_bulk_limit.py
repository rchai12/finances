import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.web.app import create_app
from tests.support import WEB_PORT, Page


@pytest.fixture
def home(tmp_settings: Settings) -> TestClient:
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    upgrade_to_head()
    client.get("/transactions")
    return client


@pytest.mark.parametrize(
    ("count", "message"),
    [(1000, "transaction not found"), (1001, "at most 1000 transactions at once")],
)
def test_a_page_of_1000_rows_reaches_the_app(home: TestClient, count: int, message: str) -> None:
    """A full page of 1000 rows plus the form's own fields passes the framework's field limit."""
    response = home.post(
        "/transactions/bulk",
        data={
            "csrf": home.cookies["fin_csrf"],
            "id": [str(number) for number in range(1, count + 1)],
            "category": "Dining",
            "action": "set",
            "back": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert ("error", message) in Page(response.text).paragraphs
