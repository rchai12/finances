# Phase 17d: a user agent for SimpleFIN

## Goal

Make `fin sync link` work against the real SimpleFIN Bridge.

The owner's first `fin sync link` failed three times with `setup token was already used or does not exist`. The token was not the problem. SimpleFIN Bridge sits behind Cloudflare, and Cloudflare refuses any request whose `User-Agent` is Python's default (`Python-urllib/3.12`) with status `403`, the same status SimpleFIN uses for a used token. The request never reached SimpleFIN. The architect confirmed this against SimpleFIN's public page `GET https://beta-bridge.simplefin.org/simplefin/info`, which needs no token: Python's default agent gets `403` from Cloudflare, and the agent `finances/0.1.0` gets `200`.

After this phase, every request the transport sends names the app: `User-Agent: finances/<version>`.

## Read first

- `src/finances/sync/transport.py` and `tests/unit/test_transport.py`
- `src/finances/__init__.py`: `__version__`

## Starting state

- Phase 17c is committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `1449` when Phase 17c is the last phase built.
- `urllib_transport` sends the caller's headers and nothing else, so `urllib` adds its default `User-Agent`.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/sync/transport.py` | `USER_AGENT` added; every request carries it |
| `tests/unit/test_transport_user_agent.py` | given, do not change |
| `docs/progress.md` | one new entry |

Nothing else changes. Do not edit any existing test.

## Out of scope

- Any other header, a retry, or a different HTTP library.
- Any change to the messages of the client. A `403` from Cloudflare and one from SimpleFIN cannot be told apart, and the message stays as it is.
- Contacting SimpleFIN or any other host, in code or in tests, and running any `fin sync` command. The owner tries `fin sync link` after verification.

## Dependencies

None new.

## Design

```python
# sync/transport.py
USER_AGENT = f"finances/{__version__}"   # __version__ from the package finances
```

## Requirements

- **R1.** `USER_AGENT` is `"finances/"` followed by `finances.__version__`.
- **R2.** Every request `urllib_transport` sends carries the header `User-Agent: USER_AGENT`, for `GET` and `POST` alike, alongside the caller's headers.
- **R3.** When the caller's headers already contain `User-Agent`, the caller's value is sent instead.
- **R4.** The caller's dictionary of headers is not changed.
- **R5.** Everything else about the transport is as in Phase 17c: one opener that refuses redirects, the timeout, the empty `POST` body, error statuses returned without a body, and the one connection error.

## Given tests

Create this file exactly as shown and do not change it. Its tests run the transport against a server on `127.0.0.1` that each test starts and stops.

`tests/unit/test_transport_user_agent.py`

```python
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
```

## Rules for this phase

- **The network.** Tests never leave the machine (the guard in `tests/conftest.py` stays as it is). Do not contact SimpleFIN.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, at least N + 5 passed, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_transport_user_agent.py tests/unit/test_transport.py --no-cov` | `17 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.sync --cov-branch --cov-report=term-missing --cov-fail-under=100`

## Report

Add an entry at the end of `docs/progress.md`:

```markdown
## Phase 17d: a user agent for SimpleFIN (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count.
