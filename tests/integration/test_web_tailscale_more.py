import keyring
import pytest
from starlette.requests import Request
from typer.testing import CliRunner

from finances.cli.main import app as cli
from finances.config import Settings, get_settings
from finances.db.migrate import upgrade_to_head
from finances.web.login import set_password
from finances.web.session import over_https
from tests.integration.test_web_tailscale import NAME, RIGHT, Broken, here, remote
from tests.support import WEB_PORT

runner = CliRunner(env={"COLUMNS": "200"})


@pytest.fixture
def named(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("FIN_WEB_HOSTNAME", NAME)
    get_settings.cache_clear()
    upgrade_to_head()
    return get_settings()


def _request(host: str, proto: str | None = None) -> Request:
    headers = [(b"host", host.encode())]
    if proto is not None:
        headers.append((b"x-forwarded-proto", proto.encode()))
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1),
            "server": ("127.0.0.1", WEB_PORT),
        }
    )


def test_over_https_for_the_name_with_a_port_another_name_and_the_header(
    named: Settings,
) -> None:
    assert over_https(_request(f"{NAME}:443")) is True
    assert over_https(_request("other.tail1234.ts.net")) is False
    assert over_https(_request(f"127.0.0.1:{WEB_PORT}", "http")) is False
    assert over_https(_request(f"127.0.0.1:{WEB_PORT}")) is False


def test_a_hostname_with_a_dot_a_space_or_one_label_is_refused(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert Settings(web_hostname=None).web_hostname is None
    assert (
        Settings(web_hostname="mac-studio.tail1234.ts.net").web_hostname
        == "mac-studio.tail1234.ts.net"
    )
    for value in (".mac.tail1234.ts.net", "mac.tail 1234.ts.net", "mac"):
        monkeypatch.setenv("FIN_WEB_HOSTNAME", value)
        get_settings.cache_clear()
        with pytest.raises(ValueError, match="FIN_WEB_HOSTNAME must be a host name such as"):
            get_settings()


def test_the_tailscale_origin_is_refused_with_no_name(tmp_settings: Settings) -> None:
    upgrade_to_head()
    client = here()
    client.get("/login")
    response = client.post(
        "/login",
        data={"csrf": client.cookies["fin_csrf"], "password": RIGHT, "next": "/"},
        headers={"origin": f"https://{NAME}"},
        follow_redirects=False,
    )
    assert (response.status_code, response.text) == (403, "Bad origin")


def test_logout_through_tailscale_ends_the_session(named: Settings) -> None:
    set_password(RIGHT, None)
    client = remote()
    client.get("/login")
    posted = client.post(
        "/login",
        data={"csrf": client.cookies["fin_csrf"], "password": RIGHT, "next": "/"},
        headers={"origin": f"https://{NAME}"},
        follow_redirects=False,
    )
    assert posted.status_code == 303
    client.post(
        "/logout",
        data={"csrf": client.cookies["fin_csrf"]},
        headers={"origin": f"https://{NAME}"},
        follow_redirects=False,
    )
    next_page = client.get("/", follow_redirects=False)
    assert next_page.status_code == 303
    assert next_page.headers["location"].startswith("/login")


def test_doctor_shows_another_web_port(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIN_WEB_PORT", "9001")
    get_settings.cache_clear()
    assert runner.invoke(cli, ["db", "upgrade"]).exit_code == 0
    result = runner.invoke(cli, ["doctor"])
    assert "http://127.0.0.1:9001 (loopback only)" in result.stdout


def test_post_login_with_a_broken_keychain(named: Settings) -> None:
    client = remote()
    client.get("/login")
    token = client.cookies["fin_csrf"]
    previous = keyring.get_keyring()
    keyring.set_keyring(Broken())
    try:
        response = client.post(
            "/login",
            data={"csrf": token, "password": RIGHT, "next": "/"},
            headers={"origin": f"https://{NAME}"},
            follow_redirects=False,
        )
        assert (response.status_code, response.text) == (
            503,
            "could not use the system keychain",
        )
    finally:
        keyring.set_keyring(previous)
