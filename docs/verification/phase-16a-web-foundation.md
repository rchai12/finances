# Verify Phase 16a: the web interface, foundation

Spec: `docs/phases/phase-16a-web-foundation.md`

Do not modify any file in the repository, and do not serve the site against the real database in `data/`. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder added `src/finances/web/` (an app with a host check, security headers, and four read-only pages over the existing functions), `fin web serve`, a `web_port` setting, three dependencies, and a dev dependency. Templates, the stylesheet, and three test files were given.

Judge the code by what it serves, never by how it is written. These are correct and must not be reported: middleware written as a plain ASGI class or with Starlette's helpers; any private helpers; building the page rows inline or in helpers.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment. (On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.)

**N** is the passed count before the phase. The coder's entry in `docs/progress.md` states it; it is `1528` when Phase 21 was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 68 passed, 0 failed, 0 skipped, 0 xfailed, **no warnings summary**, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_web_security.py tests/integration/test_web_pages.py tests/e2e/test_cli_web.py --no-cov` | exactly `68 passed` |
| the coverage command below | `Required test coverage of 100% reached`, with every module of `finances.web` at 100% |
| `.venv/bin/python -c "import fastapi, uvicorn, jinja2, httpx2; print('ok')"` | `ok` |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.cli --cov=finances.config --cov-branch --cov-report=term-missing --cov-fail-under=100`

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M pyproject.toml
 M src/finances/cli/main.py
 M src/finances/config.py
?? src/finances/cli/web.py
?? src/finances/web/
?? tests/e2e/test_cli_web.py
?? tests/integration/test_web_pages.py
?? tests/unit/test_web_security.py
```

- `src/finances/web/` holds `__init__.py` (a docstring), `app.py`, `templates/` with the six given templates, and `static/app.css`. The templates, the stylesheet, and the three test files are identical to the blocks in the spec.
- `git diff HEAD -- pyproject.toml` adds exactly the three dependencies, `httpx2` in `dev`, and the package-data table.
- `git diff HEAD -- src/finances/config.py` adds only `web_port: int = 8765`; `git diff HEAD -- src/finances/cli/main.py` adds only the import and `app.add_typer(web_app, name="web")`.

## 3. Requirement checklist

Probe lines are named by how they start. "Every line starting `x`" passes when each such line ends in `ok`.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 to R3 | serving | probe script; gate 4 | the two lines starting `command:`; `server: started on 127.0.0.1` |
| R4 | host check | probe script | the lines starting `security: another Host` and `security: a rebound name` |
| R5 | headers | probe script; gate 4 | `pages: security headers on a real answer` |
| R6 | no API description | probe script | `security: no API description` |
| R7 | no script, escaping | probe script; the third search | `pages: transactions of one person, with text escaped`; no output |
| R8 to R13 | pages | probe script; gate 4 | every line starting `pages:` and `server: before db upgrade ...` |
| one address | not reachable from the network | probe script | `security: the server cannot be reached on the machine's network address` |
| R14 | thin | the second search | no output |

Run each of these searches. Each must print nothing.

`git grep -n --untracked -E "^ *(import|from) +(requests|httpx|urllib|socket|http|aiohttp|ssl|ftplib|smtplib)" -- src/finances ':!src/finances/sync' ':!src/finances/config.py'`

`git grep -n --untracked -E "select\(|finances\.db\.orm|session\.(add|execute|delete)|keyring|@app\.(post|put|patch|delete)" -- src/finances/web src/finances/cli/web.py`

`git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static`

`git grep -n --untracked -E "0\.0\.0\.0|host=\"" -- src/finances`

`git grep -n --untracked -E "float|(^|[^_a-zA-Z.])print\(|logging" -- src/finances/web src/finances/cli/web.py`

## 4. Independent probe

This script starts the real server with uvicorn on `127.0.0.1` at a free port, in a thread, on a temporary data folder that it removes, and fetches pages with a real HTTP client from this machine. It then tries to connect to the same port on the machine's own network address, which must be refused, and runs `fin web serve` with `uvicorn.run` replaced to check the address and the log setting. It contacts nothing outside the machine.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import os
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import date

failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def fetch(port, path, host=None):
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers={"Host": host or f"127.0.0.1:{port}"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=5) as response:
            return response.status, dict(response.headers), response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read().decode()


def lan_address():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("10.255.255.255", 1))
        return probe.getsockname()[0]


folder = tempfile.TemporaryDirectory()
saved = os.environ.get("FIN_DATA_DIR")
os.environ["FIN_DATA_DIR"] = folder.name
server = None
try:
    import uvicorn

    from finances.config import get_settings

    get_settings.cache_clear()
    from finances.db.engine import get_engine, session_scope
    from finances.db.migrate import upgrade_to_head
    from finances.db.orm import TransactionRow
    from finances.db.repositories import create_account, create_person, set_account_owner, set_cardholder_alias
    from finances.web.app import HOST, create_app

    port = free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(port), host=HOST, port=port, log_level="warning", access_log=False))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    check("server: started on 127.0.0.1", server.started)
    status, headers, body = fetch(port, "/accounts")
    check("server: before db upgrade every page says so, with status 503", status == 503 and "fin db upgrade" in body)
    upgrade_to_head()
    with session_scope(get_engine()) as session:
        visa = create_account(session, "Probe Visa", "Probe Bank", "credit_card", last4="4242")
        joint = create_account(session, "Probe Joint", "Probe Bank", "checking")
        kim = create_person(session, "Kim")
        lee = create_person(session, "Lee")
        set_account_owner(session, visa.id, kim.id)
        set_account_owner(session, joint.id, None)
        set_cardholder_alias(session, "LEE PROBE", lee.id)
        for day, cents, who, account in ((12, -1875, "LEE PROBE", visa.id), (11, -5230, None, visa.id), (10, 90000, None, joint.id)):
            session.add(TransactionRow(account_id=account, posted_date=date(2027, 4, day), amount_cents=cents, description=f"PROBE <script>alert({day})</script>", cardholder=who, source="statement", fingerprint=f"q{day}".ljust(64, "0")))
    status, headers, body = fetch(port, "/", None)
    check("pages: / leads to the accounts page", status == 200 and "<h1>Accounts</h1>" in body)
    status, headers, body = fetch(port, "/accounts")
    check("pages: accounts with owners", status == 200 and "<td>Probe Visa</td>" in body and "<td>Kim</td>" in body and "<td>Joint</td>" in body)
    check("pages: security headers on a real answer", headers.get("content-security-policy", "").startswith("default-src 'self'; script-src 'none'") and headers.get("x-frame-options") == "DENY")
    status, headers, body = fetch(port, "/people")
    check("pages: people", "<td>Kim</td><td>Probe Visa</td><td></td>" in body and "<td>Lee</td><td></td><td>LEE PROBE</td>" in body)
    status, headers, body = fetch(port, "/transactions?person=lee")
    check("pages: transactions of one person, with text escaped", status == 200 and body.count("<tr>") == 2 and "&lt;script&gt;" in body and "<script>alert" not in body)
    status, headers, body = fetch(port, "/transactions?person=joint")
    check("pages: the joint filter", "$900.00" in body and "-$18.75" not in body)
    status, headers, body = fetch(port, "/transactions?limit=0")
    check("pages: a bad filter is a 400 with its message", status == 400 and "limit must be a whole number from 1 to 1000" in body)
    status, headers, body = fetch(port, "/sync")
    check("pages: SimpleFIN status with nothing mapped", status == 200 and "No mapped accounts." in body)
    status, headers, body = fetch(port, "/accounts", host="evil.example")
    check("security: another Host is refused", (status, body) == (400, "Bad host"))
    status, headers, body = fetch(port, "/accounts", host=f"attacker.example:{port}")
    check("security: a rebound name with the right port is refused", status == 400)
    status, headers, body = fetch(port, "/openapi.json")
    check("security: no API description", status == 404)
    try:
        address = lan_address()
    except OSError:
        address = None
    if address and address != "127.0.0.1":
        refused = False
        try:
            with socket.create_connection((address, port), timeout=2):
                pass
        except OSError:
            refused = True
        check("security: the server cannot be reached on the machine's network address", refused)
    else:
        check("security: no network address to try (skipped, counts as ok)", True)
    from typer.testing import CliRunner

    from finances.cli import web as web_command
    from finances.cli.main import app as cli

    calls = []
    real_run = web_command.uvicorn.run
    web_command.uvicorn.run = lambda application, **options: calls.append(options)
    try:
        served = CliRunner().invoke(cli, ["web", "serve", "--port", str(port + 1)])
        refused = CliRunner().invoke(cli, ["web", "serve", "--host", "0.0.0.0"])
    finally:
        web_command.uvicorn.run = real_run
    check("command: fin web serve binds 127.0.0.1 only, without an access log", served.exit_code == 0 and calls == [{"host": "127.0.0.1", "port": port + 1, "access_log": False, "log_level": "warning"}])
    check("command: there is no --host option", refused.exit_code == 2 and len(calls) == 1)
except Exception as exc:  # noqa: BLE001
    check(f"probe ran to the end (stopped by {type(exc).__name__}: {exc})", False)
finally:
    if server is not None:
        server.should_exit = True
        time.sleep(0.3)
    if saved is None:
        os.environ.pop("FIN_DATA_DIR", None)
    else:
        os.environ["FIN_DATA_DIR"] = saved
    folder.cleanup()
print("FAILURES", failures)
```

## 5. The coder's tests

There are none to review. Confirm that the coder added no test file and changed no existing test (section 2). Then, for each change below, say which given test would fail, by reading the tests. If none would, that is a finding.

1. `fin web serve` passes `access_log=True`.
2. `--port 80` is accepted.
3. `GET /` redirects with status `302`.
4. `/accounts` shows closed accounts without `closed=true`.
5. `limit=5000` is accepted on `/transactions`.
6. The `400` for a bad host lacks the security headers.
7. `fin people`'s `Owns` on the People page leaves out closed accounts.

## 6. Project rules that apply to this phase

- **Privacy rule 1.** The site listens on `127.0.0.1` only (fourth search, probe).
- **Privacy rule 4.** The access log is off, and nothing logs at INFO or above (fifth search).
- **Layering.** `web/` is thin: no queries, no writes, no `keyring` (second search).

## 7. Out of scope

Each of these must be absent. Report any that is present.

- A form or a route that changes data (any `POST`, `PUT`, `PATCH`, or `DELETE` route).
- JavaScript or an external asset.
- A login, sessions, HTTPS, or a host option.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 16a: the web interface, foundation (YYYY-MM-DD)` with a real date. "Built" gives N and the passed count. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then three lines:

`Total passed: <the count from section 1>`

`Parts that needed a repair: <none, or Part 1 to Part 4>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the probe line, or the file and line), and what is required. Do not prescribe the code.
