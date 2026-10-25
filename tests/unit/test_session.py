import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.views.login import lock_text
from finances.web.app import create_app
from finances.web.login import set_password
from finances.web.session import COOKIE, IDLE, LONGEST, make_cookie, read_cookie, safe_next
from tests.integration.test_web_login import RIGHT, Clock, log_in
from tests.support import WEB_PORT, Page, texts

KEY = "a" * 64
OTHER = "b" * 64
ISSUED = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
LAST = datetime(2026, 10, 24, 12, 10, tzinfo=UTC)


def independent(issued: datetime, last: datetime, key: str = KEY) -> str:
    body = f"{int(issued.timestamp())}.{int(last.timestamp())}"
    digest = hmac.new(key.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{digest}"


def test_make_cookie_has_three_signed_parts() -> None:
    value = make_cookie(KEY, ISSUED, LAST)
    expected = independent(ISSUED, LAST)
    assert value == expected
    assert value.split(".") == expected.split(".")


def test_read_cookie_refuses_a_bad_value() -> None:
    good = independent(ISSUED, LAST)
    flipped = good[:-1] + ("0" if good[-1] != "0" else "1")
    moved = f"{int(ISSUED.timestamp()) + 1}.{int(LAST.timestamp())}.{good.rsplit('.', 1)[1]}"
    for value in (
        flipped,
        moved,
        f"{int(ISSUED.timestamp())}.{int(LAST.timestamp())}",
        "ab.cd.00",
        independent(ISSUED, LAST, OTHER),
    ):
        assert read_cookie(value, KEY, LAST) is None


def test_read_cookie_refuses_an_unreadable_time() -> None:
    issued_text = last_text = "9" * 30
    body = f"{issued_text}.{last_text}"
    digest = hmac.new(KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
    assert read_cookie(f"{body}.{digest}", KEY, LAST) is None


def test_read_cookie_accepts_the_idle_and_longest_edges() -> None:
    idle_value = independent(ISSUED, LAST)
    idle_end = LAST + IDLE
    assert read_cookie(idle_value, KEY, idle_end) == ISSUED
    assert read_cookie(idle_value, KEY, idle_end + timedelta(seconds=1)) is None
    longest_last = ISSUED + LONGEST
    longest_value = independent(ISSUED, longest_last)
    longest_end = ISSUED + LONGEST
    assert read_cookie(longest_value, KEY, longest_end) == ISSUED
    assert read_cookie(longest_value, KEY, longest_end + timedelta(seconds=1)) is None


@pytest.mark.parametrize(
    ("text", "target"),
    [
        ("/a?b=c", "/a?b=c"),
        ("/", "/"),
        ("//x", "/"),
        ("/\\x", "/"),
        ("x", "/"),
        ("", "/"),
    ],
)
def test_safe_next(text: str, target: str) -> None:
    assert safe_next(text) == target


def test_lock_text_uses_london_local_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TZ", "Europe/London")
    time.tzset()
    try:
        until = datetime(2026, 10, 24, 20, 30, tzinfo=UTC)
        assert lock_text(until) == (
            "Too many wrong passwords: the login is locked until 21:30 on 24 October."
        )
    finally:
        monkeypatch.undo()
        time.tzset()


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


def test_head_without_a_session_is_sent_to_the_login(guarded: TestClient) -> None:
    response = guarded.head("/reports?month=2026-05", follow_redirects=False)
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/login?next=/reports%3Fmonth%3D2026-05",
    )


def test_login_and_static_need_no_session_and_logout_is_post(guarded: TestClient) -> None:
    assert guarded.get("/login", follow_redirects=False).status_code == 200
    assert guarded.get("/static/charts.js", follow_redirects=False).status_code == 200
    log_in(guarded)
    assert guarded.get("/logout").status_code == 405


def test_a_keychain_error_on_session_key_is_503(
    guarded: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> str | None:
        raise ValueError("could not use the system keychain")

    monkeypatch.setattr("finances.web.session.session_key", boom)
    response = guarded.get("/", follow_redirects=False)
    assert (response.status_code, response.text) == (503, "could not use the system keychain")


def test_a_keychain_error_on_has_password_closes_the_site(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> bool:
        raise ValueError("could not use the system keychain")

    monkeypatch.setattr("finances.web.session.has_password", boom)
    response = client.get("/", follow_redirects=False)
    assert (response.status_code, response.text) == (503, "could not use the system keychain")


def test_a_cookie_from_before_a_password_change_is_refused(guarded: TestClient) -> None:
    log_in(guarded)
    old = guarded.cookies.get(COOKIE)
    assert old is not None
    set_password("another long password", RIGHT)
    guarded.cookies.set(COOKIE, old)
    assert guarded.get("/", follow_redirects=False).status_code == 303


def test_login_without_a_password_set(client: TestClient) -> None:
    client.get("/login")
    response = client.post(
        "/login",
        data={"csrf": client.cookies["fin_csrf"], "password": RIGHT, "next": "/"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["no password is set; run fin web password"]


def test_logout_without_the_form_token(guarded: TestClient) -> None:
    log_in(guarded)
    response = guarded.post("/logout", data={}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")
