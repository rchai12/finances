# Verify Phase 16c: forms that work in a real browser

Spec: `docs/phases/phase-16c-browser-origin.md`

Do not modify any file in the repository, and do not serve the site against the real database in `data/`. Report findings only. The work under review is uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

The coder changed one header value (`Referrer-Policy` from `no-referrer` to `same-origin`), the one test line that pins it, and added a given test file. The point of the phase is that forms work in a **real browser**, so this guide drives one.

## 1. Gates

Run each command on its own line from the repository root, exactly as written. Do not activate the virtual environment.

**N** is the passed count before the phase; the coder's entry in `docs/progress.md` states it. It is `1856` when Phase 9 was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | exit code 0, at least N + 21 passed, 0 failed, 0 skipped, 0 xfailed, no warnings summary, `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/integration/test_web_browser_origin.py --no-cov` | exactly `21 passed` |
| the coverage command below | `Required test coverage of 100% reached` |
| `git grep -n "no-referrer" -- src` | no output |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov-branch --cov-report=term-missing --cov-fail-under=100`

## 2. Scope audit

- `git status --short` shows exactly these paths. Report any other.

```
 M docs/progress.md
 M src/finances/web/app.py
 M tests/unit/test_web_security.py
?? tests/integration/test_web_browser_origin.py
```

- `git diff HEAD -- src/finances/web/app.py` changes only the `referrer-policy` value. `git diff HEAD -- tests/unit/test_web_security.py` changes only the line of R2.
- The given file is identical to the block in the spec.

## 3. Requirement checklist

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | the header | probe; the search | `headers: the site sends Referrer-Policy same-origin`; no output |
| R2 | the pinned value | section 2 | one line changed |
| R3 | a real browser's form is accepted; others refused | probe; gate 4; `tests/integration/test_web_forms.py` passes unchanged | every line starting `browser:` |

## 4. Independent probe

This script starts the real site with uvicorn on `127.0.0.1` at a free port, on a temporary data folder that it removes. Beside the site it serves one helper page. The helper fetches the People page the way the browser does (which sets the form token cookie), copies the token, and posts the Add person form. It sends the same `Referrer-Policy` header the site sends, because that header decides the `Origin` the browser attaches. The site's own pages forbid scripts and framing, so the helper does what a person would do by hand. The script then opens the helper in **headless Google Chrome** (or Chromium) with a fresh profile, once at `127.0.0.1` and once at `localhost`, and checks the page Chrome ends on and the people stored.

It needs Google Chrome or Chromium in `/Applications`; without one the line `browser: Chrome or Chromium is installed` fails, which is a finding to report, not a reason to skip. Chrome may contact Google for its own updates while it runs; no data from the site leaves the machine.

Save the script in a temporary directory **outside the repository**, run it from the repository root with `.venv/bin/python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`. Before the fix, the three `browser:` lines about adding people fail with `Bad origin`.

```python
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

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
fetch('/people', {credentials: 'same-origin'}).then(r => r.text()).then(html => {
  const page = new DOMParser().parseFromString(html, 'text/html');
  const form = document.createElement('form');
  form.method = 'post';
  form.action = '/people/add';
  for (const [name, value] of [['csrf', page.querySelector('input[name=csrf]').value], ['name', new URLSearchParams(location.search).get('name')]]) {
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
    from finances.db.repositories import list_people
    from finances.web.app import HOST, SECURITY_HEADERS, create_app

    upgrade_to_head()
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
    with opener.open(f"http://127.0.0.1:{port}/people", timeout=5) as answer:
        policy["value"] = answer.headers.get("referrer-policy", "")
    check("headers: the site sends Referrer-Policy same-origin", policy["value"] == "same-origin")

    chrome = next((path for path in CHROME_PATHS if Path(path).exists()), None)
    check("browser: Chrome or Chromium is installed", chrome is not None)
    if chrome is not None:
        for host, name in (("127.0.0.1", "Probe One"), ("localhost", "Probe Two")):
            page = open_in_chrome(
                chrome, f"http://{host}:{port}/helper?name={name.replace(' ', '+')}"
            )
            check(
                f"browser: Add person from a real browser at {host} is accepted",
                "Person added." in page
                and "Bad origin" not in page
                and "Bad form token" not in page,
            )
        engine = get_engine()
        with session_scope(engine) as session:
            names = [person.name for person in list_people(session)]
        engine.dispose()
        check("browser: each person is stored once", sorted(names) == ["Probe One", "Probe Two"])
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

## 5. Project rules

- **Loopback only.** The site still listens on `127.0.0.1` only (the probe connects there and to `localhost`).
- **The origin check stands.** `tests/integration/test_web_forms.py` is unchanged and passes, including its refusals of `null` and of other sites.

## 6. Out of scope

Each of these must be absent. Report any that is present.

- `Origin: null` accepted, or the origin check removed or loosened.
- Any other header changed.
- A browser started by the test suite.

## 7. Progress log

`docs/progress.md` ends with an entry headed `## Phase 16c: forms that work in a real browser (YYYY-MM-DD)` with a real date, N, and the passed count.

## Verdict

`PASS`, or `FAIL` followed by one line per finding:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then: `Total passed: <the count from section 1>`

## If the verdict is FAIL

Send the coder each finding as: the requirement, what was observed, and what is required. Do not prescribe the code.
