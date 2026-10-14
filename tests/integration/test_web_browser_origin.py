"""A browser's form reaches the site with the Origin header the site's own policy lets it send.

Browsers send `Origin: null` on every form post from a page whose Referrer-Policy is
`no-referrer`, even to the same site, and the site refuses `null`. These tests read the policy
from a real answer and post the Origin a browser would send under it.
"""

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.web.app import SECURITY_HEADERS, create_app

PORT = 8765
POSTS = [
    "/accounts/add",
    "/accounts/owner",
    "/people/add",
    "/people/alias",
    "/sync/link",
    "/sync/unlink",
    "/sync/map",
    "/sync/create",
    "/sync/run",
]
POLICIES = {
    "no-referrer",
    "no-referrer-when-downgrade",
    "same-origin",
    "origin",
    "strict-origin",
    "origin-when-cross-origin",
    "strict-origin-when-cross-origin",
    "unsafe-url",
}


def browser_origin(policy: str, page_origin: str) -> str:
    """The Origin a browser sends with a form posted from a plain-http page to the same site."""
    assert policy in POLICIES
    return "null" if policy == "no-referrer" else page_origin


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    upgrade_to_head()
    return TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")


def test_the_policy_names_this_site_to_itself_only() -> None:
    assert SECURITY_HEADERS["referrer-policy"] == "same-origin"


def test_the_model_of_a_browser() -> None:
    assert browser_origin("no-referrer", "http://127.0.0.1:8765") == "null"
    assert browser_origin("same-origin", "http://127.0.0.1:8765") == "http://127.0.0.1:8765"


@pytest.mark.parametrize("host", [f"127.0.0.1:{PORT}", f"localhost:{PORT}"])
@pytest.mark.parametrize("path", POSTS)
def test_every_form_accepts_what_a_browser_sends(client: TestClient, host: str, path: str) -> None:
    page = client.get(path.rsplit("/", 1)[0], headers={"host": host})
    origin = browser_origin(page.headers["referrer-policy"], f"http://{host}")
    response = client.post(
        path,
        data={"csrf": client.cookies["fin_csrf"]},
        headers={"host": host, "origin": origin},
        follow_redirects=False,
    )
    assert response.text != "Bad origin"
    assert response.status_code in (200, 303, 400)


def test_a_person_added_from_the_people_page_is_saved(client: TestClient) -> None:
    page = client.get("/people")
    origin = browser_origin(page.headers["referrer-policy"], f"http://127.0.0.1:{PORT}")
    response = client.post(
        "/people/add",
        data={"csrf": client.cookies["fin_csrf"], "name": "Kim"},
        headers={"origin": origin},
    )
    assert response.status_code == 200
    assert "<td>Kim</td>" in response.text
