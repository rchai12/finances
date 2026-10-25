import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.web.app import create_app
from finances.web.login import set_password
from tests.support import WEB_PORT, Page, texts

RIGHT = "correct horse battery"
T0 = datetime(2026, 10, 24, 19, 30, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    found = Clock()
    monkeypatch.setattr("finances.web.app._now", found)
    return found


@pytest.fixture
def client(tmp_settings: Settings, clock: Clock) -> TestClient:
    upgrade_to_head()
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def guarded(client: TestClient) -> TestClient:
    set_password(RIGHT, None)
    return client


def log_in(client: TestClient, password: str = RIGHT, next_page: str = "/"):
    client.get("/login")
    return client.post(
        "/login",
        data={"csrf": client.cookies["fin_csrf"], "password": password, "next": next_page},
        follow_redirects=False,
    )


def test_no_password_means_no_login(client: TestClient) -> None:
    assert client.get("/reports").status_code == 200
    assert texts(Page(client.get("/login").text), "hint") == [
        "No password is set. On the Mac, run fin web password, then serve the site again."
    ]


def test_a_page_needs_the_login(guarded: TestClient) -> None:
    response = guarded.get("/reports?month=2026-05", follow_redirects=False)
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/login?next=/reports%3Fmonth%3D2026-05",
    )
    posted = guarded.post("/sync/run", data={"csrf": "x"}, follow_redirects=False)
    assert (posted.status_code, posted.headers["location"]) == (303, "/login")
    assert guarded.get("/static/app.css").status_code == 200


def test_logging_in_returns_to_the_page(guarded: TestClient) -> None:
    response = log_in(guarded, next_page="/reports?month=2026-05")
    assert (response.status_code, response.headers["location"]) == (303, "/reports?month=2026-05")
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("fin_session=")
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert guarded.get("/reports").status_code == 200


@pytest.mark.parametrize("next_page", ["//evil.example/x", "https://evil.example/", "reports", ""])
def test_only_this_sites_pages(guarded: TestClient, next_page: str) -> None:
    assert log_in(guarded, next_page=next_page).headers["location"] == "/"


def test_a_wrong_password(guarded: TestClient) -> None:
    response = log_in(guarded, password="not the password")
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["wrong password"]
    assert guarded.get("/", follow_redirects=False).status_code == 303


@pytest.fixture
def chicago(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TZ", "America/Chicago")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_the_lock_says_when_it_ends(guarded: TestClient, chicago: None) -> None:
    for _ in range(4):
        log_in(guarded, password="not the password")
    response = log_in(guarded, password="not the password")
    assert texts(Page(response.text), "error") == [
        "Too many wrong passwords: the login is locked until 15:30 on 24 October."
    ]
    locked = log_in(guarded)
    assert locked.status_code == 400
    assert texts(Page(locked.text), "error") == [
        "Too many wrong passwords: the login is locked until 15:30 on 24 October."
    ]


def test_the_idle_and_the_longest_time(guarded: TestClient, clock: Clock) -> None:
    log_in(guarded)
    clock.now = T0 + timedelta(minutes=29)
    assert guarded.get("/", follow_redirects=False).status_code == 200
    clock.now = T0 + timedelta(minutes=59)
    assert guarded.get("/", follow_redirects=False).status_code == 200
    clock.now = T0 + timedelta(minutes=89, seconds=1)
    assert guarded.get("/", follow_redirects=False).status_code == 303
    log_in(guarded)
    for minutes in range(20, 24 * 60 + 1, 20):
        clock.now = T0 + timedelta(minutes=89, seconds=1) + timedelta(minutes=minutes)
        assert guarded.get("/", follow_redirects=False).status_code == 200
    clock.now = clock.now + timedelta(minutes=20)
    assert guarded.get("/", follow_redirects=False).status_code == 303


def test_logging_out(guarded: TestClient) -> None:
    log_in(guarded)
    response = guarded.post(
        "/logout", data={"csrf": guarded.cookies["fin_csrf"]}, follow_redirects=False
    )
    assert (response.status_code, response.headers["location"]) == (303, "/login")
    assert guarded.get("/", follow_redirects=False).status_code == 303


def test_a_new_password_ends_every_session(guarded: TestClient) -> None:
    log_in(guarded)
    set_password("another long password", RIGHT)
    assert guarded.get("/", follow_redirects=False).status_code == 303


def test_a_login_without_the_form_token(guarded: TestClient) -> None:
    response = guarded.post("/login", data={"password": RIGHT}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")


def test_the_menu_logs_out_before_sync_now(guarded: TestClient) -> None:
    log_in(guarded)
    html = guarded.get("/").text
    menu = html[html.index("<nav>") : html.index("</nav>")]
    assert 0 < menu.index('action="/logout"') < menu.index('action="/sync/run"')
