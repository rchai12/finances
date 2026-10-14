import io
import urllib.error
import urllib.request

import pytest

from finances.sync import transport as transport_module
from finances.sync.simplefin import SyncError
from finances.sync.transport import TIMEOUT_SECONDS, urllib_transport

URL = "https://bridge.simplefin.org/simplefin/accounts?pending=1"


class FakeResponse(io.BytesIO):
    def __init__(self, status: int, body: bytes) -> None:
        super().__init__(body)
        self.status = status


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list:
    """Replace urlopen so that no request leaves the machine; remember what it was given."""
    calls: list = []

    def fake(request: urllib.request.Request, timeout: float) -> FakeResponse:
        calls.append((request, timeout))
        return FakeResponse(200, b'{"accounts": []}')

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return calls


def test_the_timeout_is_a_minute() -> None:
    assert TIMEOUT_SECONDS == 60


def test_a_get_returns_status_and_body(opened: list) -> None:
    status, body = urllib_transport("GET", URL, {"Authorization": "Basic abc"})
    assert (status, body) == (200, b'{"accounts": []}')
    request, timeout = opened[0]
    assert (request.get_method(), request.full_url, request.data, timeout) == ("GET", URL, None, 60)
    assert request.get_header("Authorization") == "Basic abc"


def test_a_post_sends_an_empty_body(opened: list) -> None:
    urllib_transport("POST", URL, {"Content-Length": "0"})
    request, _ = opened[0]
    assert (request.get_method(), request.data) == ("POST", b"")
    assert request.get_header("Content-length") == "0"


@pytest.mark.parametrize("code", [402, 403, 404, 500])
def test_an_http_error_is_returned_as_its_status_with_no_body(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    def fake(request, timeout):
        raise urllib.error.HTTPError(URL, code, "no", {}, io.BytesIO(b"SECRET BODY"))

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert urllib_transport("GET", URL, {}) == (code, b"")


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
    def fake(request, timeout):
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    with pytest.raises(SyncError) as caught:
        urllib_transport("GET", URL, {})
    assert str(caught.value) == "could not reach the aggregator"
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


def test_the_module_uses_the_standard_library_only() -> None:
    names = set(vars(transport_module))
    assert {"urllib", "urllib_transport", "TIMEOUT_SECONDS", "SyncError"} <= names
    assert not names & {"requests", "httpx", "aiohttp", "ssl"}
