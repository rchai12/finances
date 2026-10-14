import importlib
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from finances.sync import transport

PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


class Answer(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b"direct"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server() -> Iterator[int]:
    """A web server on this machine that answers every GET with 200 and `direct`."""
    httpd = HTTPServer(("127.0.0.1", 0), Answer)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def proxied(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Proxy settings that point at a port where nothing listens, read as the module loads."""
    for name in PROXY_KEYS:
        monkeypatch.setenv(name, "http://127.0.0.1:9")
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
    importlib.reload(transport)
    yield
    monkeypatch.undo()
    importlib.reload(transport)


def test_proxy_settings_are_ignored(server: int, proxied: None) -> None:
    url = f"http://127.0.0.1:{server}/accounts"
    assert transport.urllib_transport("GET", url, {}) == (200, b"direct")
