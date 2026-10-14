# Verify Phase 16d: new SimpleFIN accounts

Spec: `docs/phases/phase-16d-new-simplefin-accounts.md`

Do not modify any file in the repository. Do not run `fin` against the real database in `data/`, the real Keychain, or SimpleFIN. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder added migration `0007` (`feed_seen_accounts`), a pure guessing module, four repository functions, recording in `run_sync`, a line in `fin sync run`, and on the SimpleFIN page a section to set up new accounts with Don't track and Track again. Two templates and five test files were given.

Judge the code by what it does, never by how it is written. These are correct and must not be reported: regular expressions written differently, as long as R1's words and whole-word rule hold; building the page context inline or in helpers; one session or several for the page's reads.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment.

**N** is the passed count before the phase; the coder's entry in `docs/progress.md` states it. It is `1877` when Phase 16c was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 84 passed, 0 failed, 0 skipped, 0 xfailed, no warnings summary, `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/unit/test_feed_setup.py tests/integration/test_migration_0007.py tests/integration/test_seen_feed_accounts.py tests/e2e/test_cli_sync_new_accounts.py tests/integration/test_web_new_accounts.py --no-cov` | exactly `84 passed` |
| the coverage command below | `Required test coverage of 100% reached` |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.cli --cov=finances.sync --cov=finances.db --cov=finances.domain --cov-branch --cov-report=term-missing --cov-fail-under=100`

## 2. Scope audit

- `git status --short` shows only these paths. Report every other one.

```
 M docs/progress.md
 M src/finances/cli/sync.py
 M src/finances/db/orm.py
 M src/finances/db/repositories.py
 M src/finances/domain/models.py
 M src/finances/sync/runner.py
 M src/finances/web/app.py
 M src/finances/web/static/app.css
 M src/finances/web/templates/sync.html
 M src/finances/web/templates/sync_run.html
?? src/finances/db/migrations/versions/0007_feed_seen_accounts.py
?? src/finances/domain/feed_setup.py
?? tests/e2e/test_cli_sync_new_accounts.py
?? tests/integration/test_migration_0007.py
?? tests/integration/test_seen_feed_accounts.py
?? tests/integration/test_web_new_accounts.py
?? tests/unit/test_feed_setup.py
```

- The migration, the two templates, and the five test files are identical to the blocks in the spec. `git diff HEAD -- src/finances/web/static/app.css` adds only the line of R19.
- No earlier migration and no existing test changed.

## 3. Requirement checklist

Probe lines are named by how they start. "Every line starting `x`" passes when each such line ends in `ok`.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 to R4 | guessing | probe; gate 4 | every line starting `page:` |
| R5 to R9 | remembering | gate 4; probe | `tests/integration/test_seen_feed_accounts.py` passes; the line starting `command: a link` |
| R10, R11 | the command | probe; gate 4 | every line starting `command:` |
| R12 to R16 | the page and its forms | probe; gate 4 | every line starting `setup:` and `browser:` |
| R17 | Sync now | probe | every line starting `sync now:` |
| R18, R19 | templates, stylesheet | section 2 | identical; one line |
| R20 | thin | the second and third searches | no output |

Run each of these searches. Each must print nothing.

`git grep -n --untracked -E "^ *(import|from) +(requests|httpx|urllib|socket|http|aiohttp|ssl|ftplib|smtplib)" -- src/finances ':!src/finances/sync' ':!src/finances/config.py'`

`git grep -n --untracked -E "select\(|finances\.db\.orm|session\.(add|execute|delete)|keyring|mastercard|money market|american express" -- src/finances/web/app.py src/finances/cli/sync.py`

`git grep -n --untracked -E "^ *(from|import) finances\.(db|sync|web|cli|ingest|analysis)" -- src/finances/domain`

## 4. Independent probe

This script uses a temporary data folder that it removes, an in-memory keychain, and a fake SimpleFIN inside the same process; it contacts nothing outside the machine. It runs `fin sync run` through Typer's runner, starts the real site with uvicorn on `127.0.0.1` at a free port, and drives the forms with a real HTTP client that sends the `Origin` a browser sends. It then presses **Don't track** in **headless Google Chrome** (or Chromium), through a helper page served beside the site, since the site's own pages forbid scripts. Chrome may contact Google for its own updates while it runs; no data from the site leaves the machine. Without Chrome or Chromium in `/Applications` the line `browser: Chrome or Chromium is installed` fails, which is a finding to report.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
import base64
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import keyring
import keyring.backend

failures = 0
CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
# Two switches, --disable-background-networking and --disable-extensions, make headless Chrome
# hang on a page like the helper below, so they are not used.
CHROME_FLAGS = [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-component-update",
    "--disable-sync",
    "--no-pings",
    "--virtual-time-budget=8000",
]
# Served beside the site: fetches the SimpleFIN page as the browser does (which sets the form
# token cookie) and presses the first "Don't track" button on it. The site forbids scripts.
HELPER = """<!doctype html><title>helper</title><body><script>
fetch('/sync', {credentials: 'same-origin'}).then(r => r.text()).then(html => {
  const page = new DOMParser().parseFromString(html, 'text/html');
  const found = page.querySelector('form[action="/sync/ignore"]');
  const form = document.createElement('form');
  form.method = 'post';
  form.action = '/sync/ignore';
  for (const input of found.querySelectorAll('input')) {
    const field = document.createElement('input');
    field.name = input.name;
    field.value = input.value;
    form.appendChild(field);
  }
  document.body.appendChild(form);
  form.submit();
});
</script></body>"""
KIM = "https://kim-user:kim-pass@bridge.simplefin.org/simplefin"
SAM = "https://sam-user:sam-pass@bridge.simplefin.org/simplefin"


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


def key(access):
    user, password = access.split("//")[1].split("@")[0].split(":")
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


class Bridge:
    def __init__(self):
        self.answers = {}
        self.asked = []

    def __call__(self, method, url, headers):
        self.asked.append(headers["Authorization"])
        noon = int(datetime.now(UTC).replace(hour=12, minute=0, second=0).timestamp())
        accounts = [
            {
                "id": feed_id,
                "name": name,
                "conn_id": "C",
                "currency": "USD",
                "balance": "-1.00",
                "balance-date": noon,
                "transactions": [],
            }
            for feed_id, name in self.answers.get(headers["Authorization"], [])
        ]
        conn = [{"conn_id": "C", "name": "Probe Credit Union", "org_id": "O", "sfin_url": "x"}]
        return 200, json.dumps({"errlist": [], "connections": conn, "accounts": accounts}).encode()


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects)
cookie = {}


def send(port, path, fields=None):
    headers = {"Origin": f"http://127.0.0.1:{port}"} if fields is not None else {}
    if cookie:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookie.items())
    data = (
        None
        if fields is None
        else urllib.parse.urlencode({"csrf": cookie.get("fin_csrf", ""), **fields}).encode()
    )
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers)
    try:
        with OPENER.open(request, timeout=10) as answer:
            status, got, body = answer.status, answer.headers, answer.read().decode()
    except urllib.error.HTTPError as error:
        status, got, body = error.code, error.headers, error.read().decode()
    for value in got.get_all("set-cookie") or []:
        name, _, rest = value.partition("=")
        cookie[name] = rest.split(";")[0]
    return status, got.get("location"), body


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


memory = MemoryKeyring()
keyring.set_keyring(memory)
memory.passwords[("finances-simplefin", "kim")] = KIM
memory.passwords[("finances-simplefin", "sam")] = SAM
folder = tempfile.TemporaryDirectory()
saved = os.environ.get("FIN_DATA_DIR")
os.environ["FIN_DATA_DIR"] = folder.name
server = None
try:
    import uvicorn
    from typer.testing import CliRunner

    from finances.config import get_settings

    get_settings.cache_clear()
    from finances.cli.main import app as cli
    from finances.db.engine import get_engine, session_scope
    from finances.db.migrate import upgrade_to_head
    from finances.db.repositories import create_account, create_person, map_feed_account
    from finances.sync import transport
    from finances.web.app import HOST, create_app

    upgrade_to_head()
    with session_scope(get_engine()) as session:
        card = create_account(
            session, "Probe Card", "Probe Credit Union", "credit_card", last4="1111"
        )
        map_feed_account(session, card.id, "PCU-1", "kim")
        create_account(
            session, "Probe Joint Checking", "Probe Credit Union", "checking", last4="1357"
        )
        create_person(session, "Kim")
    bridge = Bridge()
    bridge.answers[key(KIM)] = [
        ("PCU-1", "Card"),
        ("PCU-2", "Rewards  Visa Signature (...2468)"),
        ("PCU-3", "Joint Checking 1357"),
        ("PCU-4", "Brokerage Sweep"),
    ]
    bridge.answers[key(SAM)] = [("SAM-1", "Sam Online Savings")]
    transport.urllib_transport = bridge

    result = CliRunner(env={"COLUMNS": "200"}).invoke(cli, ["sync", "run"])
    check(
        "command: fin sync run names the new accounts of the link",
        result.exit_code == 0
        and "SimpleFIN (kim): 3 new accounts to set up (open the SimpleFIN page, or run: fin sync accounts --link kim)"
        in result.stdout,
    )
    check(
        "command: a link with nothing mapped and nothing seen is not asked",
        key(SAM) not in bridge.asked,
    )

    port = free_port()
    site = create_app(port)

    async def with_helper(scope, receive, send_message):
        if scope["type"] == "http" and scope["path"] == "/helper":
            headers = [
                (b"content-type", b"text/html; charset=utf-8"),
                (b"referrer-policy", b"same-origin"),
            ]
            await send_message({"type": "http.response.start", "status": 200, "headers": headers})
            await send_message({"type": "http.response.body", "body": HELPER.encode()})
            return
        await site(scope, receive, send_message)

    server = uvicorn.Server(
        uvicorn.Config(with_helper, host=HOST, port=port, log_level="warning", access_log=False)
    )
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    check("server: started on 127.0.0.1", server.started)

    status, _, body = send(port, "/sync")
    headings = [" ".join(text.split()) for text in re.findall(r"<h3>(.*?)</h3>", body, re.S)]
    check(
        "page: each new account has its own section",
        headings
        == [
            'Probe Credit Union: Rewards Visa Signature (...2468) <span class="hint">link kim</span>',
            'Probe Credit Union: Joint Checking 1357 <span class="hint">link kim</span>',
            'Probe Credit Union: Brokerage Sweep <span class="hint">link kim</span>',
        ],
    )
    check(
        "page: the card is guessed as a credit card ending 2468, owned by Kim",
        'value="2468"' in body
        and '<option value="credit_card" selected>' in body
        and '<option value="Kim" selected>' in body,
    )
    check(
        "page: the checking account is matched to the one you already have",
        "This looks like Probe Joint Checking, which you already have." in body
        and '<option value="Probe Joint Checking" selected>' in body,
    )
    status, location, _ = send(
        port,
        "/sync/create",
        {
            "link": "kim",
            "feed_account": "PCU-2",
            "account": "Kim Rewards Visa",
            "institution": "Probe Credit Union",
            "type": "credit_card",
            "last4": "2468",
            "owner": "Kim",
            "next": "sync",
        },
    )
    status2, _, accounts_page = send(port, "/accounts")
    check(
        "setup: create and map, with an owner, returns to the SimpleFIN page",
        (status, location) == (303, "/sync?notice=mapped")
        and "<td>Kim Rewards Visa</td><td>Probe Credit Union</td><td>credit_card</td><td>••2468</td><td>yes</td><td>Kim</td>"
        in accounts_page,
    )
    status, location, _ = send(
        port,
        "/sync/map",
        {"link": "kim", "feed_account": "PCU-3", "account": "Probe Joint Checking", "next": "sync"},
    )
    status2, _, body = send(port, "/sync")
    check(
        "setup: map to the suggested account",
        (status, location) == (303, "/sync?notice=mapped")
        and "<td>kim</td><td>Probe Joint Checking</td><td>PCU-3</td>" in body,
    )

    chrome = next((path for path in CHROME_PATHS if Path(path).exists()), None)
    check("browser: Chrome or Chromium is installed", chrome is not None)
    if chrome is not None:
        profile = tempfile.mkdtemp()
        try:
            page = subprocess.run(
                [
                    chrome,
                    *CHROME_FLAGS,
                    f"--user-data-dir={profile}",
                    "--dump-dom",
                    f"http://127.0.0.1:{port}/helper",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            ).stdout
        except subprocess.TimeoutExpired:
            subprocess.run(["pkill", "-f", profile], check=False)
            page = ""
        finally:
            shutil.rmtree(profile, ignore_errors=True)
        check(
            "browser: Don't track works from a real browser",
            "That SimpleFIN account will not be tracked." in page
            and "Brokerage Sweep" in page
            and "Track again" in page,
        )
    status, location, _ = send(port, "/sync/track", {"link": "kim", "feed_account": "PCU-4"})
    status2, _, body = send(port, "/sync")
    check(
        "setup: track again offers it for setup again",
        (status, location) == (303, "/sync?notice=tracked")
        and "Brokerage Sweep" in body
        and "Track again" not in body,
    )
    send(port, "/sync/ignore", {"link": "kim", "feed_account": "PCU-4"})
    status, _, body = send(port, "/sync/run", {})
    check("sync now: nothing new is left to set up for kim", status == 200 and "kim: " not in body)
    result = CliRunner(env={"COLUMNS": "200"}).invoke(cli, ["sync", "run", "--link", "sam"])
    bridge.asked.clear()
    status, _, body = send(port, "/sync/run", {})
    check(
        "sync now: a link with only new accounts is synced and its new account named",
        key(SAM) in bridge.asked and "sam: 1 new account to set up." in body,
    )
    check(
        "privacy: no page shows an access URL",
        not any(word in body for word in ("kim-pass", "sam-pass")),
    )
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

There are none to review. Confirm that the coder added no test file other than the five given ones and changed no existing test (section 2). Then, for each change below, say which given test would fail, by reading the tests. If none would, that is a finding.

1. `guess_account` checks card words before `checking`.
2. `list_new_feed_accounts` treats an account mapped under another link as not new.
3. `record_seen_feed_account` sets `last_seen` to `day` even when `day` is earlier.
4. `fin sync run` prints the new-accounts line after SimpleFIN's messages.
5. `POST /sync/run` runs only links with a mapping.
6. `POST /sync/track` sets the flag to true.

## 6. Project rules that apply to this phase

- **Migrations.** `0007` is the only new migration; `git diff HEAD -- src/finances/db/migrations` shows no change to an earlier file.
- **Text fits its column.** SimpleFIN's names are cut to 100 characters (`test_long_text_is_cut_to_fit`).
- **No new network.** The first search; the page never contacts SimpleFIN (the probe's fake counts every request).
- **Layering.** The second and third searches.

## 7. Out of scope

Each of these must be absent. Report any that is present.

- An account created or mapped without a form being sent.
- A `GET` route that records seen accounts, or a fetch from SimpleFIN when a page is opened.
- Edit or delete of accounts, people, owners, or mappings; a link-to-person setting.

## 8. Progress log

`docs/progress.md` ends with an entry headed `## Phase 16d: new SimpleFIN accounts (YYYY-MM-DD)` with a real date, N, and the passed count. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then three lines:

`Total passed: <the count from section 1>`

`Parts that needed a repair: <none, or Part 1 to Part 5>`

`Built beyond the spec: <none, or what>`

## If the verdict is FAIL

Send the coder each finding as: the requirement or rule, what was observed (the probe line, the test, or the file and line), and what is required. Do not prescribe the code.
