# Verify Phase 16b: the web interface, setup forms

Spec: `docs/phases/phase-16b-web-setup.md`

Do not modify any file in the repository. Do not serve the site against the real database in `data/`, and do not touch the real Keychain or SimpleFIN. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder added form routes to `src/finances/web/app.py` (accounts, owners, people, cardholder names, SimpleFIN link, unlink, map, create and map, sync now), a form token, `run_links` in `sync/runner.py`, an opener that ignores proxy settings in `sync/transport.py`, and one dependency. Templates, the stylesheet, and four test files were given.

Judge the code by what it does, never by how it is written. These are correct and must not be reported: any private helpers; building contexts inline or in helpers; the order of checks inside R5, R12, and R13, as long as each refusal has its message; `Form()` fields with defaults.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

**N** is the passed count before the phase. The coder's entry in `docs/progress.md` states it; it is `1620` when Phase 16a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 133 passed, 0 failed, 0 skipped, 0 xfailed, **no warnings summary**, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_run_links.py tests/unit/test_transport_proxies.py tests/integration/test_web_forms.py tests/integration/test_web_sync_setup.py --no-cov` | exactly `133 passed` |
| the coverage command below | `Required test coverage of 100% reached`, with every module of `finances.web` and `finances.sync` at 100% |
| `.venv/bin/python -c "import multipart; print('ok')"` | `ok` |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.sync --cov-branch --cov-report=term-missing --cov-fail-under=100`

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M pyproject.toml
 M src/finances/sync/runner.py
 M src/finances/sync/transport.py
 M src/finances/web/app.py
 M src/finances/web/static/app.css
 M src/finances/web/templates/accounts.html
 M src/finances/web/templates/error.html
 M src/finances/web/templates/people.html
 M src/finances/web/templates/sync.html
?? src/finances/web/templates/messages.html
?? src/finances/web/templates/sync_accounts.html
?? src/finances/web/templates/sync_run.html
?? tests/integration/test_web_forms.py
?? tests/integration/test_web_sync_setup.py
?? tests/unit/test_run_links.py
?? tests/unit/test_transport_proxies.py
```

- The seven templates, the stylesheet, and the four test files are identical to the blocks in the spec. `layout.html` and `transactions.html` are unchanged.
- `git diff HEAD -- pyproject.toml` adds exactly `"python-multipart>=0.0.9",`.
- `git diff HEAD -- src/finances/sync/transport.py` changes only the line that builds the opener.
- `git diff HEAD -- src/finances/sync/runner.py` only adds `LinkRun`, `run_links`, and their imports.
- No file under `tests/` other than the four new ones is changed.

## 3. Requirement checklist

Probe lines are named by how they start. "Every line starting `x`" passes when each such line ends in `ok`.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 to R4 | form token, origin, POST only | probe script; gate 4 | every line starting `token:`; `security: a form path answers GET with 405` |
| R5, R6 | accounts and owners | probe script; gate 4 | every line starting `accounts:`; `people: owner and cardholder name saved` |
| R7, R8 | people and cardholder names | probe script; gate 4 | every line starting `people:` |
| R9 to R14 | SimpleFIN setup and sync now | probe script; gate 4 | every line starting `simplefin:` |
| R15 | no secret in a page | probe script; the sixth search | every line starting `privacy:`; no output |
| R16 | engines disposed | read `app.py` | every engine a route makes is disposed in a `finally` or by `_reading` |
| R17 | one link at a time | gate 4 (`tests/unit/test_run_links.py`) | passes; read `run_links`: one `session_scope` per link |
| R18 | proxy settings ignored | probe script; gate 4 | `transport: proxy settings are ignored` |
| R19 | thin | the second search | no output |

Run each of these searches. Each must print nothing.

`git grep -n --untracked -E "^ *(import|from) +(requests|httpx|urllib|socket|http|aiohttp|ssl|ftplib|smtplib)" -- src/finances ':!src/finances/sync' ':!src/finances/config.py'`

`git grep -n --untracked -E "select\(|finances\.db\.orm|session\.(add|execute|delete)|keyring" -- src/finances/web`

`git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static`

`git grep -n --untracked -E "0\.0\.0\.0|host=\"" -- src/finances`

`git grep -n --untracked -E "float|(^|[^_a-zA-Z.])print\(|logging" -- src/finances/web`

`git grep -n --untracked -E "\"(token|access_url|access)\": |value=\"\{\{ *(token|access)" -- src/finances/web`

## 4. Independent probe

This script starts the real server with uvicorn on `127.0.0.1` at a free port, in a thread, on a temporary data folder that it removes. It replaces the Keychain with one in memory and SimpleFIN with a fake inside the same process, so it never reads or writes the real Keychain and contacts nothing outside the machine. It then drives every form with a real HTTP client, keeping the cookie as a browser does: it checks the token's refusals, adds an account and two people, sets an owner and a cardholder name, links a fake SimpleFIN subscription, maps one account, creates and maps another, syncs, and unlinks. It also checks that the transport ignores a proxy setting, by asking the probe's own server for its stylesheet with `HTTP_PROXY` pointing at a closed port.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import base64
import importlib
import json
import os
import re
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime

import keyring
import keyring.backend

failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


class MemoryKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.passwords = {}

    def get_password(self, service, username):
        return self.passwords.get((service, username))

    def set_password(self, service, username, password):
        self.passwords[(service, username)] = password

    def delete_password(self, service, username):
        del self.passwords[(service, username)]


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


ACCESS = "https://probe-user:probe-pass@bridge.simplefin.org/simplefin"
TOKEN = base64.b64encode(b"https://bridge.simplefin.org/simplefin/claim/PROBE").decode()
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects)
cookie = {}
bodies = []


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def send(port, path, fields=None, origin=None, with_cookie=True):
    headers = {}
    if with_cookie and cookie:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookie.items())
    if origin:
        headers["Origin"] = origin
    data = None if fields is None else urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers)
    try:
        with OPENER.open(request, timeout=10) as response:
            status, answer, body = response.status, response.headers, response.read().decode()
    except urllib.error.HTTPError as error:
        status, answer, body = error.code, error.headers, error.read().decode()
    for value in answer.get_all("set-cookie") or []:
        name, _, rest = value.partition("=")
        cookie[name] = rest.split(";")[0]
    bodies.append(body)
    return status, answer, body


def stamp(days_ago):
    today = datetime.now(UTC).date()
    return int(datetime(today.year, today.month, today.day, 12, tzinfo=UTC).timestamp()) - days_ago * 86400


class Bridge:
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, headers):
        self.calls.append(method)
        if method == "POST":
            return 200, ACCESS.encode()
        accounts = [
            {"id": "PRB-1", "name": "Probe Card", "conn_id": "C", "currency": "USD", "balance": "-18.75", "balance-date": stamp(0),
             "transactions": [{"id": "T-1", "posted": stamp(2), "amount": "-18.75", "description": "PROBE STORE"}]},
            {"id": "PRB-2", "name": "Probe Savings", "conn_id": "C", "currency": "USD", "balance": "500.00", "balance-date": stamp(0),
             "transactions": [{"id": "T-2", "posted": stamp(1), "amount": "500.00", "description": "PROBE DEPOSIT"}]},
        ]
        body = {"errlist": [], "connections": [{"conn_id": "C", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}], "accounts": accounts}
        return 200, json.dumps(body).encode()


memory = MemoryKeyring()
keyring.set_keyring(memory)
folder = tempfile.TemporaryDirectory()
saved = {key: os.environ.get(key) for key in ("FIN_DATA_DIR", "HTTP_PROXY", "http_proxy", "NO_PROXY", "no_proxy")}
os.environ["FIN_DATA_DIR"] = folder.name
server = None
try:
    import uvicorn

    from finances.config import get_settings

    get_settings.cache_clear()
    from finances.db.migrate import upgrade_to_head
    from finances.sync import transport
    from finances.web.app import HOST, create_app

    upgrade_to_head()
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(port), host=HOST, port=port, log_level="warning", access_log=False))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    check("server: started on 127.0.0.1", server.started)

    for key in ("HTTP_PROXY", "http_proxy"):
        os.environ[key] = "http://127.0.0.1:9"
    for key in ("NO_PROXY", "no_proxy"):
        os.environ.pop(key, None)
    importlib.reload(transport)
    try:
        status, _ = transport.urllib_transport("GET", f"http://127.0.0.1:{port}/static/app.css", {})
    except Exception:  # noqa: BLE001
        status = None
    check("transport: proxy settings are ignored", status == 200)
    for key in ("HTTP_PROXY", "http_proxy", "NO_PROXY", "no_proxy"):
        os.environ.pop(key, None)
    importlib.reload(transport)
    bridge = Bridge()
    transport.urllib_transport = bridge

    status, answer, body = send(port, "/accounts")
    raw = " ".join(answer.get_all("set-cookie") or [])
    token = cookie.get("fin_csrf", "")
    check("token: a page sets an HttpOnly, SameSite=Strict form token", re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is not None and "HttpOnly" in raw and "samesite=strict" in raw.lower())
    check("token: every form on the page carries it", body.count(f'name="csrf" value="{token}"') == body.count('method="post"') >= 1)
    fields = {"csrf": token, "name": "Probe Visa", "institution": "Probe Bank", "type": "credit_card", "last4": "4242"}
    status, _, body = send(port, "/accounts/add", {**fields, "csrf": ""})
    check("token: a form without it is refused with 403", (status, body) == (403, "Bad form token"))
    status, _, body = send(port, "/accounts/add", fields, with_cookie=False)
    check("token: a form without the cookie is refused with 403", (status, body) == (403, "Bad form token"))
    status, _, body = send(port, "/accounts/add", fields, origin="http://evil.example")
    check("token: a form sent from another site is refused with 403", (status, body) == (403, "Bad origin"))
    status, _, body = send(port, "/accounts")
    check("token: refused forms changed nothing", "Probe Visa" not in body)
    status, answer, _ = send(port, "/accounts/add", fields, origin=f"http://127.0.0.1:{port}")
    check("accounts: add an account", (status, answer.get("location")) == (303, "/accounts?notice=account-added"))
    status, _, body = send(port, "/accounts?notice=account-added")
    check("accounts: the new account and the notice", "<td>Probe Visa</td><td>Probe Bank</td><td>credit_card</td><td>••4242</td>" in body and '<p class="notice">Account added.</p>' in body)
    status, _, body = send(port, "/accounts/add", fields)
    check("accounts: a duplicate is a 400 with its message", status == 400 and "an account with this name already exists" in body)
    status, _, _ = send(port, "/people/add", {"csrf": token, "name": "Kim"})
    status2, _, _ = send(port, "/people/add", {"csrf": token, "name": "Lee"})
    check("people: add two people", (status, status2) == (303, 303))
    send(port, "/accounts/owner", {"csrf": token, "account": "Probe Visa", "owner": "Kim"})
    send(port, "/people/alias", {"csrf": token, "person": "Lee", "cardholder": "lee  probe"})
    status, _, body = send(port, "/people")
    check("people: owner and cardholder name saved", "<td>Kim</td><td>Probe Visa</td><td></td>" in body and "<td>Lee</td><td></td><td>LEE PROBE</td>" in body)

    status, answer, _ = send(port, "/sync/link", {"csrf": token, "link": "kim", "token": TOKEN})
    check("simplefin: link by pasting the setup token", (status, answer.get("location")) == (303, "/sync/accounts?link=kim&notice=linked"))
    check("simplefin: the access is kept in the keychain under the link", memory.passwords == {("finances-simplefin", "kim"): ACCESS})
    status, _, body = send(port, "/sync/accounts?link=kim&notice=linked")
    check("simplefin: the link's accounts are listed", status == 200 and "<td>PRB-1</td>" in body and "<td>PRB-2</td>" in body)
    status, answer, _ = send(port, "/sync/map", {"csrf": token, "link": "kim", "feed_account": "PRB-1", "account": "Probe Visa"})
    check("simplefin: map an account from the list", (status, answer.get("location")) == (303, "/sync/accounts?link=kim&notice=mapped"))
    status, _, _ = send(port, "/sync/create", {"csrf": token, "link": "kim", "feed_account": "PRB-2", "account": "Probe Savings", "institution": "Probe Bank", "type": "savings", "last4": ""})
    status, _, body = send(port, "/sync/accounts?link=kim")
    check("simplefin: create an account and map it", status == 200 and "<td>Probe Visa</td></tr>" in body and "<td>Probe Savings</td></tr>" in body)
    status, _, body = send(port, "/sync/run", {"csrf": token})
    check("simplefin: sync now pulls the link", status == 200 and "<td>kim</td><td>Probe Visa</td><td>PRB-1</td><td>1</td>" in body and "<td>kim</td><td>Probe Savings</td><td>PRB-2</td><td>1</td>" in body)
    status, _, body = send(port, "/transactions?account=Probe+Savings")
    check("simplefin: the pulled transactions are stored", "PROBE DEPOSIT" in body and "$500.00" in body)
    status, _, body = send(port, "/sync/link", {"csrf": token, "link": "kim", "token": TOKEN})
    check("simplefin: linking again needs Replace", status == 400 and "tick Replace" in body)
    status, answer, _ = send(port, "/sync/unlink", {"csrf": token, "link": "kim"})
    status2, _, body = send(port, "/sync")
    check("simplefin: unlink forgets the access and keeps the mapping", status == 303 and memory.passwords == {} and "<td>kim</td><td>Probe Visa</td><td>PRB-1</td><td>no</td>" in body)
    check("privacy: no page showed the access URL or the setup token", not any("probe-pass" in text or TOKEN in text for text in bodies))
    check("privacy: only the fake bridge was called", bridge.calls[0] == "POST" and set(bridge.calls) == {"POST", "GET"})
    status, _, _ = send(port, "/sync/run")
    check("security: a form path answers GET with 405", status == 405)
except Exception as exc:  # noqa: BLE001
    check(f"probe ran to the end (stopped by {type(exc).__name__}: {exc})", False)
finally:
    if server is not None:
        server.should_exit = True
        time.sleep(0.3)
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    folder.cleanup()
print("FAILURES", failures)
```

## 5. The coder's tests

There are none to review. Confirm that the coder added no test file other than the four given ones and changed no existing test (section 2). Then, for each change below, say which given test would fail, by reading the tests. If none would, that is a finding.

1. The form token cookie is set without `HttpOnly`.
2. `POST /accounts/add` is accepted when the `Origin` header is `http://evil.example`.
3. `?notice=<b>hi</b>` is shown on the page as given.
4. `POST /sync/create` saves the new account when its mapping is refused.
5. `POST /sync/link` replaces an existing link without `replace=on`.
6. `run_links` stops at the first link that fails.
7. `GET /sync/accounts` answers `400` when SimpleFIN refuses the access.

## 6. Project rules that apply to this phase

- **Privacy rule 1.** The site listens on `127.0.0.1` only (fourth search); only `src/finances/sync/transport.py` opens a connection (first search).
- **Privacy rule 4.** Nothing logs at INFO or above (fifth search). No setup token or access URL reaches a page (sixth search, probe).
- **Layering.** `web/` is thin: no queries and no `keyring` (second search).

## 7. Out of scope

Each of these must be absent. Report any that is present.

- A route that edits or deletes an account, a person, an owner, a cardholder name, or a mapping, or closes an account.
- A `GET` route that changes data.
- JavaScript or an external asset.
- A login, HTTPS, or a host option.
- Any change to a `fin` command.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 16b: the web interface, setup forms (YYYY-MM-DD)` with a real date. "Built" gives N and the passed count. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then three lines:

`Total passed: <the count from section 1>`

`Parts that needed a repair: <none, or Part 1 to Part 5>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the probe line, or the file and line), and what is required. Do not prescribe the code.
