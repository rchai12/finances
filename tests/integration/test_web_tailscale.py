import keyring
import keyring.backend
import keyring.errors
import pytest
from fastapi.testclient import TestClient

from finances.config import Settings, get_settings
from finances.db.migrate import upgrade_to_head
from finances.web.app import create_app
from finances.web.login import set_password
from tests.support import WEB_PORT

NAME = "mac.tail1234.ts.net"
RIGHT = "correct horse battery"


@pytest.fixture
def named(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("FIN_WEB_HOSTNAME", NAME)
    get_settings.cache_clear()
    upgrade_to_head()
    return get_settings()


def remote() -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"https://{NAME}")


def here() -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


def cookies(response) -> list[str]:
    return response.headers.get_list("set-cookie")


def test_the_name_is_served_only_when_set(tmp_settings: Settings) -> None:
    upgrade_to_head()
    refused = remote().get("/login")
    assert (refused.status_code, refused.text) == (400, "Bad host")


def test_the_name_and_no_other(named: Settings) -> None:
    client = remote()
    assert client.get("/login").status_code == 200
    assert client.get("/login", headers={"host": f"{NAME}:443"}).status_code == 200
    assert client.get("/login", headers={"host": "other.tail1234.ts.net"}).status_code == 400


def test_cookies_are_secure_over_tailscale(named: Settings) -> None:
    set_password(RIGHT, None)
    client = remote()
    page = client.get("/login")
    assert [c for c in cookies(page) if c.startswith("fin_csrf=")][0].count("Secure") == 1
    login = client.post(
        "/login",
        data={"csrf": client.cookies["fin_csrf"], "password": RIGHT, "next": "/"},
        headers={"origin": f"https://{NAME}"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert "Secure" in [c for c in cookies(login) if c.startswith("fin_session=")][0]
    again = client.get("/", follow_redirects=False)
    assert again.status_code == 200
    assert "Secure" in [c for c in cookies(again) if c.startswith("fin_session=")][0]


def test_cookies_on_this_mac_are_not_secure(named: Settings) -> None:
    page = here().get("/login")
    assert all("Secure" not in c for c in cookies(page))


def test_a_request_forwarded_over_https(named: Settings) -> None:
    page = here().get("/login", headers={"x-forwarded-proto": "https"})
    assert "Secure" in [c for c in cookies(page) if c.startswith("fin_csrf=")][0]


def test_the_form_origin(named: Settings) -> None:
    set_password(RIGHT, None)
    client = remote()
    client.get("/login")
    data = {"csrf": client.cookies["fin_csrf"], "password": RIGHT, "next": "/"}
    good = client.post(
        "/login", data=data, headers={"origin": f"https://{NAME}"}, follow_redirects=False
    )
    assert good.status_code == 303
    bad = client.post(
        "/login", data=data, headers={"origin": "https://evil.example"}, follow_redirects=False
    )
    assert (bad.status_code, bad.text) == (403, "Bad origin")


class Broken(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringLocked("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.PasswordSetError("no")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.PasswordDeleteError("no")


def test_a_broken_keychain_closes_the_site(named: Settings) -> None:
    previous = keyring.get_keyring()
    keyring.set_keyring(Broken())
    try:
        client = remote()
        for path in ("/", "/reports", "/login"):
            response = client.get(path, follow_redirects=False)
            assert (response.status_code, response.text) == (
                503,
                "could not use the system keychain",
            ), path
        assert client.get("/static/app.css").status_code == 200
    finally:
        keyring.set_keyring(previous)


def test_the_setting_is_a_host_name(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert Settings(web_hostname="Mac.Tail1234.TS.NET").web_hostname == NAME
    monkeypatch.setenv("FIN_WEB_HOSTNAME", "not a host!")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="FIN_WEB_HOSTNAME must be a host name such as"):
        get_settings()
