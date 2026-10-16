import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.web.app import HOST, SECURITY_HEADERS, create_app

PORT = 8765


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")


def test_the_host_is_this_machine_only() -> None:
    assert HOST == "127.0.0.1"


def test_the_security_headers() -> None:
    assert SECURITY_HEADERS == {
        "content-security-policy": (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        ),
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "same-origin",
        "cache-control": "no-store",
    }


@pytest.mark.parametrize("host", [f"127.0.0.1:{PORT}", f"localhost:{PORT}"])
def test_requests_for_this_machine_are_answered(client: TestClient, host: str) -> None:
    response = client.get("/static/app.css", headers={"host": host})
    assert response.status_code == 200


@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        f"evil.example:{PORT}",
        "127.0.0.1",
        "localhost",
        "127.0.0.1:9999",
        f"127.0.0.2:{PORT}",
        f"[::1]:{PORT}",
        f"LOCALHOST:{PORT}x",
        "",
    ],
)
def test_any_other_host_is_refused(client: TestClient, host: str) -> None:
    response = client.get("/accounts", headers={"host": host})
    assert (response.status_code, response.text) == (400, "Bad host")
    assert (
        response.headers["content-security-policy"] == SECURITY_HEADERS["content-security-policy"]
    )


@pytest.mark.parametrize(
    "path", ["/", "/accounts", "/static/app.css", "/nowhere", "/static/none.css"]
)
def test_every_answer_carries_the_security_headers(client: TestClient, path: str) -> None:
    response = client.get(path, follow_redirects=False)
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_no_api_documentation_is_served(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_the_stylesheet_is_served_from_this_app() -> None:
    from pathlib import Path

    import finances.web

    css = (Path(finances.web.__file__).parent / "static" / "app.css").read_text()
    assert "@import" not in css and "url(" not in css


def test_the_server_start_and_stop_messages_pass_through(tmp_settings: Settings) -> None:
    with TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}") as started:
        assert started.get("/static/app.css").status_code == 200
