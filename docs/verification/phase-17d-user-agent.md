# Verify Phase 17d: a user agent for SimpleFIN

Spec: `docs/phases/phase-17d-user-agent.md`

Do not modify any file in the repository, do not contact SimpleFIN or any other host, and do not run any `fin sync` command. Report findings only.

## 1. Gates

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 5 passed (N is in the coder's progress entry; `1449` when 17c was the last phase), 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_transport_user_agent.py tests/unit/test_transport.py --no-cov` | `17 passed` |
| the coverage command below | `Required test coverage of 100% reached`, `transport.py` at 100% |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.sync --cov-branch --cov-report=term-missing --cov-fail-under=100`

## 2. Scope audit

`git status --short` shows only:

```
 M docs/progress.md
 M src/finances/sync/transport.py
?? tests/unit/test_transport_user_agent.py
```

The test file is identical to the block in the spec. `git diff HEAD -- src/finances/sync/transport.py` adds the import of `__version__`, the constant `USER_AGENT`, and the header; the redirect handler, the opener, the timeout, and the error handling are unchanged. No existing test is changed.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | probe | `user agent: names the app and its version` |
| R2 | probe | the `GET` and `POST` lines |
| R3 | probe | `user agent: the caller's own value wins` |
| R4 | probe | `user agent: the caller's dictionary is unchanged` |
| R5 | probe; gate 4 | `redirects: still refused`; `tests/unit/test_transport.py` passes unchanged |

## 4. Independent probe

It starts a server on `127.0.0.1`, which it stops at the end, and contacts nothing else. Save it outside the repository, run it from the repository root with `.venv/bin/python <path>`, and delete it. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import http.server
import socketserver
import threading

failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


class Handler(http.server.BaseHTTPRequestHandler):
    seen = []

    def _answer(self):
        Handler.seen.append((self.command, self.path, self.headers.get("User-Agent"), self.headers.get("Authorization")))
        if self.path == "/away":
            self.send_response(302)
            self.send_header("Location", "/elsewhere")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", "5")
        self.end_headers()
        self.wfile.write(b"probe")

    do_GET = _answer
    do_POST = _answer

    def log_message(self, *args):
        return


class LocalServer(http.server.HTTPServer):
    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "127.0.0.1", self.server_address[1]


try:
    import finances
    from finances.sync import transport

    check("user agent: names the app and its version", transport.USER_AGENT == f"finances/{finances.__version__}")
    server = LocalServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        given = {"Authorization": "Basic probe"}
        check("user agent: a GET carries it, with the caller's headers", transport.urllib_transport("GET", base + "/one", given) == (200, b"probe") and Handler.seen[-1] == ("GET", "/one", transport.USER_AGENT, "Basic probe"))
        check("user agent: a POST carries it", transport.urllib_transport("POST", base + "/two", {}) == (200, b"probe") and Handler.seen[-1][2] == transport.USER_AGENT)
        check("user agent: the caller's own value wins", transport.urllib_transport("GET", base + "/three", {"User-Agent": "probe/2"}) == (200, b"probe") and Handler.seen[-1][2] == "probe/2")
        check("user agent: the caller's dictionary is unchanged", given == {"Authorization": "Basic probe"})
        before = len(Handler.seen)
        check("redirects: still refused", transport.urllib_transport("GET", base + "/away", {}) == (302, b"") and len(Handler.seen) == before + 1)
    finally:
        server.shutdown()
        server.server_close()
except Exception as exc:  # noqa: BLE001
    check(f"probe ran to the end (stopped by {type(exc).__name__}: {exc})", False)
print("FAILURES", failures)
```

## Verdict

`PASS`, or `FAIL` with one line per finding: `<requirement id or section> | <file>:<line> | expected <...> | found <...>`. Then `Total passed: <count>`.
