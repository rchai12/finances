# Phase 16c: forms that work in a real browser

## Goal

Every form on the web site works in a real browser. Today each one is refused with `Bad origin`.

Phase 16a sends `Referrer-Policy: no-referrer` with every page. Phase 16b refuses a form whose `Origin` header is anything but `http://127.0.0.1:PORT` or `http://localhost:PORT`. A browser follows the page's referrer policy when it builds the `Origin` header: under `no-referrer` it sends `Origin: null` on every form, even one posted to the same site. So the two rules together refuse every form a person submits. The tests did not see it, because the test client sends no `Origin` header unless a test sets one.

The fix is the referrer policy `same-origin`. The browser then names the page's address only in requests to this same site and never to any other, so nothing leaves the machine that did not before. On a form posted to this site it sends the true origin, which the check accepts. The origin check, the form token, and the refusal of `Origin: null` stay exactly as they are.

## Read first

- `docs/phases/phase-16a-web-foundation.md` (R5, the security headers) and `docs/phases/phase-16b-web-setup.md` (R3, the origin check)
- `src/finances/web/app.py`: `SECURITY_HEADERS` and the form check
- `tests/unit/test_web_security.py`

## Starting state

- Phase 9 is committed. `git status --short` prints nothing.
- Run `.venv/bin/python -m pytest` before you start and note the number passed. This spec calls it **N**. It is `1856` when Phase 9 is the last phase built.
- Commands are written for macOS. On Windows, `.\.venv\Scripts\python` replaces `.venv/bin/python`.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/app.py` | `SECURITY_HEADERS["referrer-policy"]` becomes `"same-origin"` |
| `tests/unit/test_web_security.py` | the one expected value of R2 |
| `tests/integration/test_web_browser_origin.py` | new: given, do not change |
| `docs/progress.md` | one new entry |

Change nothing else.

## Out of scope

- Accepting `Origin: null`, removing the origin check, or changing the form token.
- Any other security header.
- A browser in the test suite. A real browser is used only by the verifier.

## Dependencies

None new.

## Requirements

- **R1.** `SECURITY_HEADERS["referrer-policy"]` is `"same-origin"`. Every answer carries it, as R5 of Phase 16a requires for all the headers.
- **R2.** In `tests/unit/test_web_security.py`, in `test_the_security_headers`, the line `"referrer-policy": "no-referrer",` becomes `"referrer-policy": "same-origin",`. No other line of that file changes.
- **R3.** A form posted with the `Origin` a browser sends under the site's own policy is never refused as `Bad origin`, at `127.0.0.1:PORT` and at `localhost:PORT`. A form with `Origin: null` or another site's origin is still refused with `403` and `Bad origin` (the tests of Phase 16b, unchanged).

## Given tests

Create this file exactly as shown and do not change it. It reads the referrer policy from a real answer, works out the `Origin` a browser would send under it, and posts every form with that header. It fails while the policy is `no-referrer`.

`tests/integration/test_web_browser_origin.py`

```python
"""A browser's form reaches the site with the Origin header the site's own policy lets it send.

Browsers send `Origin: null` on every form post from a page whose Referrer-Policy is
`no-referrer`, even to the same site, and the site refuses `null`. These tests read the policy
from a real answer and post the Origin a browser would send under it.
"""

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.migrate import upgrade_to_head
from finances.web.app import SECURITY_HEADERS, create_app

PORT = 8765
POSTS = [
    "/accounts/add",
    "/accounts/owner",
    "/people/add",
    "/people/alias",
    "/sync/link",
    "/sync/unlink",
    "/sync/map",
    "/sync/create",
    "/sync/run",
]
POLICIES = {
    "no-referrer",
    "no-referrer-when-downgrade",
    "same-origin",
    "origin",
    "strict-origin",
    "origin-when-cross-origin",
    "strict-origin-when-cross-origin",
    "unsafe-url",
}


def browser_origin(policy: str, page_origin: str) -> str:
    """The Origin a browser sends with a form posted from a plain-http page to the same site."""
    assert policy in POLICIES
    return "null" if policy == "no-referrer" else page_origin


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    upgrade_to_head()
    return TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")


def test_the_policy_names_this_site_to_itself_only() -> None:
    assert SECURITY_HEADERS["referrer-policy"] == "same-origin"


def test_the_model_of_a_browser() -> None:
    assert browser_origin("no-referrer", "http://127.0.0.1:8765") == "null"
    assert browser_origin("same-origin", "http://127.0.0.1:8765") == "http://127.0.0.1:8765"


@pytest.mark.parametrize("host", [f"127.0.0.1:{PORT}", f"localhost:{PORT}"])
@pytest.mark.parametrize("path", POSTS)
def test_every_form_accepts_what_a_browser_sends(client: TestClient, host: str, path: str) -> None:
    page = client.get(path.rsplit("/", 1)[0], headers={"host": host})
    origin = browser_origin(page.headers["referrer-policy"], f"http://{host}")
    response = client.post(
        path,
        data={"csrf": client.cookies["fin_csrf"]},
        headers={"host": host, "origin": origin},
        follow_redirects=False,
    )
    assert response.text != "Bad origin"
    assert response.status_code in (200, 303, 400)


def test_a_person_added_from_the_people_page_is_saved(client: TestClient) -> None:
    page = client.get("/people")
    origin = browser_origin(page.headers["referrer-policy"], f"http://127.0.0.1:{PORT}")
    response = client.post(
        "/people/add",
        data={"csrf": client.cookies["fin_csrf"], "name": "Kim"},
        headers={"origin": origin},
    )
    assert response.status_code == 200
    assert "<td>Kim</td>" in response.text
```

## Tests to write

None. R1 and R2 are covered by `tests/unit/test_web_security.py`, R3 by the given file and the tests of Phase 16b.

## Rules for this phase

- **The site stays on this machine**, and the policy names the page only to the site itself.
- **Git.** Do not commit, and never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Commands** start with `.venv/bin/python`. Do not activate the virtual environment, and do not create one.
- Do not run `fin web serve` against the real database in `data/`; the owner does that after verification.

## Acceptance

Run each of these before you report, from the repository root.

| Command | Must show |
|---|---|
| `.venv/bin/python -m ruff format --check .` | nothing would be reformatted |
| `.venv/bin/python -m ruff check .` | `All checks passed!` |
| `.venv/bin/python -m pytest` | 0 failed, 0 skipped, 0 xfailed, no warnings summary, at least N + 21 passed, and `Required test coverage of 85.0% reached` |
| `.venv/bin/python -m pytest tests/integration/test_web_browser_origin.py tests/unit/test_web_security.py tests/integration/test_web_forms.py --no-cov` | 0 failed |
| the coverage command below | `Required test coverage of 100% reached` |
| `git grep -n "no-referrer" -- src` | no output |
| `git diff HEAD -- tests/unit/test_web_security.py` | exactly the one line of R2 changed |
| `git status --short` | only the paths in the Scope table |

`.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov-branch --cov-report=term-missing --cov-fail-under=100`

## Report

Add an entry at the end of `docs/progress.md`, in the form of the earlier entries:

```markdown
## Phase 16c: forms that work in a real browser (YYYY-MM-DD)
- Built: ...
- Deviations from spec (and why): ...
- Follow-ups / known issues: ...
```

Under "Built", give N and the final passed count. In your final message, give the output line of each acceptance command.
