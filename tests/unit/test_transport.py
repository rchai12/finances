import http.server
import socketserver
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from finances.sync.simplefin import SyncError
from finances.sync.transport import TIMEOUT_SECONDS, urllib_transport


class Handler(http.server.BaseHTTPRequestHandler):
    """A local server: /moved redirects to /target, /fail answers 403 with a body, / answers 200."""

    seen: list[tuple[str, str, str | None]] = []

    def _answer(self) -> None:
        Handler.seen.append((self.command, self.path, self.headers.get("Authorization")))
        if self.path == "/moved":
            self.send_response(302)
            self.send_header("Location", "/target")
            self.end_headers()
        elif self.path == "/fail":
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"SECRET BODY")
        else:
            body = b'{"accounts": []}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    do_GET = _answer
    do_POST = _answer

    def log_message(self, *args: object) -> None:
        return


class LocalServer(http.server.HTTPServer):
    """An HTTP server that skips the reverse name lookup HTTPServer makes when it starts."""

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "127.0.0.1", self.server_address[1]


@pytest.fixture
def server() -> Iterator[str]:
    """A server on 127.0.0.1 only, for this test; nothing leaves the machine."""
    Handler.seen = []
    httpd = LocalServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01})
    thread.daemon = True
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def test_the_timeout_is_a_minute() -> None:
    assert TIMEOUT_SECONDS == 60


def test_a_get_returns_status_and_body(server: str) -> None:
    assert urllib_transport("GET", server + "/", {"Authorization": "Basic abc"}) == (
        200,
        b'{"accounts": []}',
    )
    assert Handler.seen == [("GET", "/", "Basic abc")]


def test_a_post_is_sent_as_a_post(server: str) -> None:
    status, _ = urllib_transport("POST", server + "/claim", {"Content-Length": "0"})
    assert status == 200
    assert Handler.seen == [("POST", "/claim", None)]


def test_a_redirect_is_not_followed_and_the_credentials_go_nowhere_else(server: str) -> None:
    assert urllib_transport("GET", server + "/moved", {"Authorization": "Basic abc"}) == (302, b"")
    assert Handler.seen == [("GET", "/moved", "Basic abc")]


def test_an_error_status_is_returned_without_its_body(server: str) -> None:
    assert urllib_transport("GET", server + "/fail", {}) == (403, b"")


def test_the_timeout_is_passed_to_the_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = []

    class Reply:
        status = 200

        def read(self) -> bytes:
            return b"x"

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_open(self, request, data=None, timeout=None):
        seen.append((request.get_method(), request.data, timeout))
        return Reply()

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)
    assert urllib_transport("GET", "https://bridge.simplefin.org/x", {}) == (200, b"x")
    assert urllib_transport("POST", "https://bridge.simplefin.org/x", {}) == (200, b"x")
    assert seen == [("GET", None, 60), ("POST", b"", 60)]


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("unreachable bridge.simplefin.org user:secret"),
        TimeoutError("timed out"),
        ConnectionResetError("reset"),
        OSError("no route"),
    ],
)
def test_a_failure_to_connect_is_one_constant_error(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def fake_open(self, request, data=None, timeout=None):
        raise error

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)
    with pytest.raises(SyncError) as caught:
        urllib_transport("GET", "https://bridge.simplefin.org/x", {})
    assert str(caught.value) == "could not reach the aggregator"
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


def test_urlopen_is_not_used(monkeypatch: pytest.MonkeyPatch, server: str) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("urlopen follows redirects; the transport must not use it")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    assert urllib_transport("GET", server + "/", {})[0] == 200


def test_conftest_keeps_tests_off_the_network() -> None:
    with pytest.raises(AssertionError) as caught:
        urllib_transport("GET", "https://bridge.simplefin.org/x", {})
    assert str(caught.value) == "a test tried to use the network"
