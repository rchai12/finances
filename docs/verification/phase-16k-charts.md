# Verify Phase 16k: charts

Spec: `docs/phases/phase-16k-charts.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure, the probe, and the verdict.

The coder changed the security policy to allow the site's own scripts, added the chart data to the account page, and the owner added Chart.js 4.4.6. The templates, `charts.js`, and two test files were given; no migration.

These are correct and must not be reported: `json.dumps` with or without spaces; the chart functions taking the page's lists.

## 1. Gates

N is `2813` when Phase 16i was the last phase built.

| Command | Expected |
|---|---|
| `shasum -a 256 src/finances/web/static/vendor/chart.umd.js` | `3850656abbdc319141e6e8ce8eacde2622fc767c30e20d81704af2bf3159f92d` |
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 13 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_chart_library.py tests/integration/test_web_charts.py --no-cov` | exactly `13 passed` |
| `.venv/bin/python -m pytest tests/unit/test_web_security.py tests/integration/test_web_account_page.py --no-cov` | all passed |
| `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov=finances.views --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git grep -n --untracked -E "<script>|<script [^>]*>[^<]+</script>|on(click|load|error)=" -- src/finances/web/templates` | no output |
| `git grep -n --untracked -E "https?://|//cdn|integrity=" -- src/finances/web/templates src/finances/web/static/charts.js src/finances/web/static/app.css` | no output |

## 2. Scope paths

```
 M docs/progress.md
 M src/finances/web/app.py
 M src/finances/web/static/app.css
 M src/finances/web/templates/account.html
 M src/finances/web/templates/layout.html
 M tests/unit/test_web_security.py
?? src/finances/views/charts.py
?? src/finances/web/static/charts.js
?? src/finances/web/static/vendor/chart.umd.js
?? tests/integration/test_web_charts.py
?? tests/unit/test_chart_library.py
?? tests/unit/test_chart_views.py
```

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 to R4 | gates 3 and 4 | pass |
| R2 (edges) | the coder's `tests/unit/test_chart_views.py` | each item of the spec's "Tests to write" has a test |
| R1 | `git diff HEAD -- src/finances/web/app.py` | only `script-src` changed in the headers |
| browser | probe | every line `ok` |

## 4. Probe

It starts the real site with uvicorn on `127.0.0.1` at a free port, on a temporary data folder it removes, adds a synthetic account with two purchases and two balances this month, and loads the account page in **headless Google Chrome** (or Chromium). `charts.js` marks each canvas it draws with `data-drawn="yes"`; Chrome's log must hold no policy refusal. Without Chrome the line `browser: Chrome or Chromium is installed` fails, which is a finding.

```python
# Phase 16k probe: the account page's three charts draw in a real browser under the site's own
# security policy. It starts the site with uvicorn on 127.0.0.1 at a free port, on a temporary
# data folder it removes, with synthetic data, and loads the page in headless Google Chrome.
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from datetime import UTC, date, datetime

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
    "--metrics-recording-only",
    "--virtual-time-budget=8000",
    "--enable-logging=stderr",
    "--v=0",
]


def check(label: str, ok: bool) -> None:
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


folder = tempfile.mkdtemp()
os.environ["FIN_DATA_DIR"] = folder
server = None
try:
    import uvicorn

    from finances.config import get_settings

    get_settings.cache_clear()
    from finances.db.engine import get_engine, session_scope
    from finances.db.migrate import upgrade_to_head
    from finances.db.orm import TransactionRow
    from finances.db.repositories import add_balance_snapshot, create_account
    from finances.domain.models import DataSource
    from finances.web.app import HOST, create_app

    upgrade_to_head()
    today = datetime.now(UTC).date()
    with session_scope(get_engine()) as session:
        card = create_account(session, "Probe Card", "Probe Bank", "credit_card")
        add_balance_snapshot(
            session, card.id, date(today.year, today.month, 1), -12345, DataSource.STATEMENT
        )
        add_balance_snapshot(session, card.id, today, -23456, DataSource.STATEMENT)
        for number, cents in enumerate((-675, -2210), start=1):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=date(today.year, today.month, 1),
                    amount_cents=cents,
                    description=f"PROBE SHOP {number}",
                    source="statement",
                    fingerprint=f"p{number:02d}".ljust(64, "0"),
                )
            )
    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(port), host=HOST, port=port, log_level="warning", access_log=False
        )
    )
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    check("site: started on 127.0.0.1", server.started)
    chrome = next((path for path in CHROME_PATHS if os.path.exists(path)), None)
    check("browser: Chrome or Chromium is installed", chrome is not None)
    if chrome is not None:
        profile = tempfile.mkdtemp()
        try:
            done = subprocess.run(
                [
                    chrome,
                    *CHROME_FLAGS,
                    f"--user-data-dir={profile}",
                    "--dump-dom",
                    f"http://127.0.0.1:{port}/account?name=Probe%20Card",
                ],
                capture_output=True,
                text=True,
                timeout=90,
            )
            dom, log = done.stdout, done.stderr
        except subprocess.TimeoutExpired:
            subprocess.run(["pkill", "-f", profile], check=False)
            dom, log = "", ""
        finally:
            shutil.rmtree(profile, ignore_errors=True)
        drawn = re.findall(r'data-drawn="([^"]*)"', dom)
        check("browser: three charts drawn", drawn == ["yes", "yes", "yes"])
        check(
            "browser: no security policy refusals",
            "Refused" not in log and "Content Security Policy" not in log,
        )
except Exception as error:  # noqa: BLE001
    check(f"probe: raised {type(error).__name__}", False)
finally:
    if server is not None:
        server.should_exit = True
        time.sleep(0.3)
    shutil.rmtree(folder, ignore_errors=True)
print(f"FAILURES {failures}")
```

## 5. Spot checks

Each line names the given input that decides it. Make the change, run the given tests (and the probe where named), and see one fail; if none does, that is a finding.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. An inline `<script>` is added to the account page | the page's script tags | exactly the two `src` tags | three tags |
| 2. The policy keeps `script-src 'none'` | the probe | three charts drawn | none drawn, a refusal logged |
| 3. The pie keeps a negative line | May's Shopping refund (net -$20.00) | labels `Food`, `Uncategorized` | `Shopping` added |
| 4. The chart data carries dollars | May's Food | `20000` | `200.0` |
| 5. The scripts go in the layout for every page | `/reports` | no `<script` | two scripts |

## 6. Out of scope

Each must be absent: charts on other pages; any file loaded from another site; a change to `chart.umd.js`; another library.
