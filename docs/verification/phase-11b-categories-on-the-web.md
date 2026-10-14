# Verify Phase 11b: categories on the web

Spec: `docs/phases/phase-11b-categories-on-the-web.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure, the probe, and the verdict.

The coder added a Categories page, a page for each transaction, the forms for categories, rules, and setting a category by hand, date links on the Transactions page, and categorizing after Sync now, on top of Phase 11a's functions. Six templates and one test file were given.

These are correct and must not be reported: helpers inside `web/app.py`; reading the forms with `Form()` fields; one session or several for a page's reads.

## 1. Gates

N is `2200` when Phase 11a was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 37 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/integration/test_web_categories.py --no-cov` | exactly `37 passed` |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.views --cov=finances.db --cov=finances.categorize --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n -E "select\(|session\.(add|execute|delete)|clean_merchant\(|pick_rule" -- src/finances/web` | no output |
| `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/db/repositories.py
 M src/finances/views/categories.py
 M src/finances/web/app.py
 M src/finances/web/static/app.css
 M src/finances/web/templates/layout.html
 M src/finances/web/templates/transactions.html
?? src/finances/web/templates/categories.html
?? src/finances/web/templates/category_select.html
?? src/finances/web/templates/rule_form.html
?? src/finances/web/templates/transactions_one.html
?? tests/integration/test_category_views.py
?? tests/integration/test_web_categories.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R3 | the coder's `tests/integration/test_category_views.py` | each item of the spec's "Tests to write" has a test |
| R4 to R10 | gate 2; probe | passes; every line starting `page:` and `browser:` |
| R11 | `git diff HEAD -- src/finances/web/static/app.css` | exactly the two lines |

## 4. Probe

It starts the real site with uvicorn on `127.0.0.1` at a free port, on a temporary data folder it removes, and adds two synthetic transactions. Beside the site it serves a helper page that fetches a page of the site as the browser does (which sets the form token cookie), copies the token, and posts the form named in its address. With **headless Google Chrome** (or Chromium in `/Applications`) it adds a rule on the Categories page and sets a category by hand on a transaction's page, then checks what the site shows. Chrome may contact Google for its own updates; no data from the site leaves the machine. Without Chrome the line `browser: Chrome or Chromium is installed` fails, which is a finding.

```python
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

failures = 0
CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
CHROME_FLAGS = [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-component-update",
    "--disable-sync",
    "--disable-client-side-phishing-detection",
    "--disable-domain-reliability",
    "--no-pings",
    "--metrics-recording-only",
    "--virtual-time-budget=8000",
]
# A helper page served next to the real site. It fetches the People page as the browser does
# (which also sets the form token cookie), copies the token, and posts the Add person form.
# The site's own pages forbid scripts and framing, so the helper does what a person would.
# Two Chrome switches, --disable-background-networking and --disable-extensions, make headless
# Chrome hang on this page, so they are not used.
HELPER = """<!doctype html><title>helper</title><body><script>
const ask = new URLSearchParams(location.search);
fetch(ask.get('from'), {credentials: 'same-origin'}).then(r => r.text()).then(html => {
  const page = new DOMParser().parseFromString(html, 'text/html');
  const form = document.createElement('form');
  form.method = 'post';
  form.action = ask.get('to');
  const fields = [['csrf', page.querySelector('input[name=csrf]').value]];
  for (const [name, value] of ask.entries()) {
    if (name !== 'from' && name !== 'to') fields.push([name, value]);
  }
  for (const [name, value] of fields) {
    const field = document.createElement('input');
    field.name = name;
    field.value = value;
    form.appendChild(field);
  }
  document.body.appendChild(form);
  form.submit();
});
</script></body>"""


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def open_in_chrome(chrome, url):
    """Load the page in a new headless Chrome profile and return the final page, or ''."""
    profile = tempfile.mkdtemp()
    try:
        result = subprocess.run(
            [chrome, *CHROME_FLAGS, f"--user-data-dir={profile}", "--dump-dom", url],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        subprocess.run(["pkill", "-f", profile], check=False)
        return ""
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


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
    from finances.db.repositories import create_account
    from finances.web.app import HOST, SECURITY_HEADERS, create_app

    upgrade_to_head()
    with session_scope(get_engine()) as session:
        card = create_account(session, "Probe Card", "Probe Bank", "credit_card")
        for day, cents, text in (
            (5, -675, "TST* PROBE NOODLES 03-04 OAKVILLE"),
            (6, -2210, "PROBE MARKET #12"),
        ):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=date(2027, 3, day),
                    amount_cents=cents,
                    description=text,
                    source="statement",
                    fingerprint=f"p{day}".ljust(64, "0"),
                )
            )
    port = free_port()
    site = create_app(port)
    policy = {"value": SECURITY_HEADERS["referrer-policy"]}

    async def with_helper(scope, receive, send):
        if scope["type"] == "http" and scope["path"] == "/helper":
            headers = [
                (b"content-type", b"text/html; charset=utf-8"),
                (b"referrer-policy", policy["value"].encode()),
            ]
            await send({"type": "http.response.start", "status": 200, "headers": headers})
            await send({"type": "http.response.body", "body": HELPER.encode()})
            return
        await site(scope, receive, send)

    server = uvicorn.Server(
        uvicorn.Config(with_helper, host=HOST, port=port, log_level="warning", access_log=False)
    )
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    check("server: started on 127.0.0.1", server.started)

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(path):
        """The page's text, or the error status: a missing page is a failed check, not a stop."""
        try:
            with opener.open(f"http://127.0.0.1:{port}{path}", timeout=5) as answer:
                return answer.read().decode()
        except urllib.error.HTTPError as error:
            return f"HTTP {error.code}"

    categories_page = get("/categories")
    check(
        "page: the categories page lists both transactions as uncategorized",
        "PROBE NOODLES" in categories_page and "PROBE MARKET" in categories_page,
    )
    listing = get("/transactions")
    check(
        "page: each transaction's date opens its own page",
        'href="/transactions/1"' in listing and 'href="/transactions/2"' in listing,
    )
    chrome = next((path for path in CHROME_PATHS if Path(path).exists()), None)
    check("browser: Chrome or Chromium is installed", chrome is not None)
    if chrome is not None:
        rule = urlencode(
            {
                "from": "/categories",
                "to": "/categories/rules/add",
                "pattern": "probe noodles",
                "match": "contains",
                "priority": "0",
                "category": "Dining",
            }
        )
        page = open_in_chrome(chrome, f"http://127.0.0.1:{port}/helper?{rule}")
        check(
            "browser: adding a rule in a real browser runs the rules",
            "Rule added, and the rules were run again." in page
            and "PROBE NOODLES" not in page.split("<h2>Rules</h2>")[0],
        )
        hand = urlencode(
            {"from": "/transactions/2", "to": "/transactions/2/category", "category": "Groceries"}
        )
        page = open_in_chrome(chrome, f"http://127.0.0.1:{port}/helper?{hand}")
        check(
            "browser: setting a category by hand in a real browser",
            "Category saved." in page and "by hand" in page and "Groceries" in page,
        )
    one = get("/transactions/1")
    check(
        "page: the noodles transaction shows the rule that set it",
        "Dining" in one and "by rule 1" in one,
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

## 5. Spot checks

For each change, say which given test would fail. If none would, that is a finding.

1. Adding a rule does not run the rules again.
2. The "Leave it to the rules" form shows for a category set by a rule.
3. `/transactions/abc` answers `422` (FastAPI's own check of an `int` path) instead of `404`.
4. A refused rule form loses the pattern that was typed.
5. Sync now does not categorize.

## 6. Out of scope

Each must be absent: a category column on the Transactions page; renaming or deleting categories; JavaScript.
