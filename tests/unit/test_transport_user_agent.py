import http.server
import socketserver
import threading
from collections.abc import Iterator

import pytest

import finances
from finances.sync.transport import USER_AGENT, urllib_transport


class Handler(http.server.BaseHTTPRequestHandler):
    """Answers 200 to every request and remembers the User-Agent each one carried."""

    agents: list[tuple[str, str | None]] = []

    def _answer(self) -> None:
        Handler.agents.append((self.command, self.headers.get("User-Agent")))
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

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
    Handler.agents = []
    httpd = LocalServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01})
    thread.daemon = True
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def test_the_user_agent_names_the_app_and_its_version() -> None:
    assert USER_AGENT == f"finances/{finances.__version__}"
    assert not USER_AGENT.startswith("Python-urllib")


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_every_request_carries_the_user_agent(server: str, method: str) -> None:
    assert urllib_transport(method, server + "/simplefin/x", {"Authorization": "Basic abc"}) == (
        200,
        b"ok",
    )
    assert Handler.agents == [(method, USER_AGENT)]


def test_a_user_agent_given_by_the_caller_is_kept(server: str) -> None:
    urllib_transport("GET", server + "/", {"User-Agent": "probe/9"})
    assert Handler.agents == [("GET", "probe/9")]


def test_the_callers_headers_are_not_changed(server: str) -> None:
    headers = {"Authorization": "Basic abc"}
    urllib_transport("GET", server + "/", headers)
    assert headers == {"Authorization": "Basic abc"}
