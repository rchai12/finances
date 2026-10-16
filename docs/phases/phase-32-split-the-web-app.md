# Phase 32: split the web app

## Goal

`src/finances/web/app.py` holds about 1700 lines and 50 routes in one module. Phase 20 (login) will touch every route, and Phases 27 and 19 add pages, so it is split first, with **no change in behaviour**: one router module per area, shared helpers in their own modules, and `app.py` left with the application, its security, and what other code and tests rely on.

Every page, form, message, status, header, and redirect stays exactly as it is. Every earlier test passes unchanged.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/web/app.py`, whole
- The tests that reach into it: `tests/unit/test_web_security.py`, `tests/integration/test_backups_page_more.py` (`_RESTORE_GATE`), `tests/integration/test_statements_more.py` (`_upload_name`), and every test that replaces `finances.web.app._today` or `_now`, or `finances.sync.transport.urllib_transport`

## Starting state

N is `2895` when Phase 31 is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/app.py` | keeps the application and its contract (R2); the routes leave |
| `src/finances/web/routes/__init__.py` and the eleven area modules | new (R1) |
| `src/finances/web/*.py` (new shared modules, names of your choice) | new (R3) |
| `tests/unit/test_web_split.py` | new: given |
| `docs/architecture.md` | the `web/` line of the package layout (R6) |
| `docs/progress.md` | one new entry |

Templates, static files, and every other module stay as they are.

## Out of scope

- Any change a person or a test could see; renaming a route, template, notice, or message.
- Login, new pages, or anything from Phases 19, 20, or 27.

## Dependencies

None new. No migration.

## Requirements

- **R1.** `src/finances/web/routes/` has one module per area, each defining `router = APIRouter()` with these routes and no others:

  | Module | Routes |
  |---|---|
  | `home` | `GET /` |
  | `accounts` | `/accounts`, `/account`, and `/accounts/...` |
  | `people` | `/people` and `/people/...` |
  | `transactions` | `/transactions`, `/transactions/bulk`, `/transactions/{transaction_id}...` |
  | `statements` | `/statements` and `/statements/upload` |
  | `categories` | `/categories` and `/categories/...`, rules included |
  | `reports` | `/reports` and `/insights` |
  | `transfers` | `/transfers` and `/transfers/...` |
  | `budgets` | `/budgets` and `/budgets/...` |
  | `sync` | `/sync` and `/sync/...` |
  | `backups` | `/backups` and `/backups/...` |

- **R2.** `finances.web.app` keeps, as module attributes: `create_app`, `HOST`, `SECURITY_HEADERS`, the clock hooks `_today`, `_utc_today`, and `_now`, the lock `_RESTORE_GATE`, and `_upload_name`. Every route reads the clock through these hooks **looked up on `finances.web.app` when called**, so a test that replaces `finances.web.app._today` or `_now` changes what every route reads; every route and the engine helper use the one `_RESTORE_GATE`; the SimpleFIN transport is still called as `transport.urllib_transport` (looked up when called), so tests that replace it keep working.
- **R3.** Shared code (rendering and notices, the form checks for origin and token, the database check, field readers, page builders shared by several areas) lives in modules under `src/finances/web/`, imported by the routers. No module under `src/finances/web/` (routes included) is longer than 400 lines.
- **R4.** `create_app(port)` builds the same application: the same middleware (`_Guard`), the static mount, no documentation routes, and the routers included in an order that keeps `POST /categories/rules/add` and `/categories/rules/delete` before `/categories/rules/{rule_id}` (and `GET` on those two still answering `405`, as Phase 16f arranged). The origins accepted for forms still depend on the port given to `create_app`.
- **R5.** No behaviour change: every earlier test passes **unchanged**, and the templates and static files are untouched.
- **R6.** `docs/architecture.md`'s package layout line for `web/` becomes: `web/                        FastAPI app (thin): app.py (application, security, clock hooks), routes/ (one router per area), shared page and form helpers, templates, static files, vendored Chart.js`.

## Given tests

`tests/unit/test_web_split.py` (16 tests). The route set, the rule-id order, and the module contract already hold and must keep holding; the rest fail until the split is done.

```python
import importlib
import threading
from pathlib import Path

import pytest
from fastapi import APIRouter
from fastapi.routing import APIRoute
from starlette.routing import Mount

import finances.web
from finances.web import app as web_app

WEB = Path(finances.web.__file__).parent
AREAS = [
    "accounts",
    "backups",
    "budgets",
    "categories",
    "home",
    "people",
    "reports",
    "statements",
    "sync",
    "transactions",
    "transfers",
]
ROUTES = {
    ("GET", "/"),
    ("GET", "/budgets"),
    ("POST", "/budgets/set"),
    ("POST", "/budgets/remove"),
    ("GET", "/accounts"),
    ("GET", "/account"),
    ("POST", "/accounts/add"),
    ("POST", "/accounts/owner"),
    ("POST", "/accounts/rename"),
    ("POST", "/accounts/active"),
    ("GET", "/people"),
    ("POST", "/people/add"),
    ("POST", "/people/alias"),
    ("GET", "/transactions"),
    ("POST", "/transactions/bulk"),
    ("GET", "/transactions/{transaction_id}"),
    ("POST", "/transactions/{transaction_id}/category"),
    ("POST", "/transactions/{transaction_id}/category/clear"),
    ("GET", "/statements"),
    ("POST", "/statements/upload"),
    ("GET", "/categories"),
    ("POST", "/categories/add"),
    ("POST", "/categories/rules/add"),
    ("POST", "/categories/rules/delete"),
    ("POST", "/categories/rename"),
    ("POST", "/categories/delete"),
    ("GET", "/categories/rules/{rule_id}"),
    ("POST", "/categories/rules/{rule_id}"),
    ("GET", "/reports"),
    ("GET", "/insights"),
    ("GET", "/transfers"),
    ("POST", "/transfers/find"),
    ("POST", "/transfers/confirm"),
    ("POST", "/transfers/reject"),
    ("POST", "/transfers/unpair"),
    ("GET", "/sync"),
    ("POST", "/sync/link"),
    ("POST", "/sync/unlink"),
    ("GET", "/sync/accounts"),
    ("POST", "/sync/map"),
    ("POST", "/sync/create"),
    ("POST", "/sync/ignore"),
    ("POST", "/sync/track"),
    ("POST", "/sync/run"),
    ("GET", "/backups"),
    ("POST", "/backups/run"),
    ("GET", "/backups/delete"),
    ("POST", "/backups/delete"),
    ("GET", "/backups/restore"),
    ("POST", "/backups/restore"),
}


def inner_routes() -> list:
    api = web_app.create_app(8765)
    while not hasattr(api, "routes"):
        api = api.app
    return list(api.routes)


def test_the_same_routes_as_before_the_split() -> None:
    routes = inner_routes()
    found = [
        (method, route.path)
        for route in routes
        if isinstance(route, APIRoute)
        for method in route.methods
    ]
    assert len(found) == len(ROUTES)
    assert set(found) == ROUTES
    assert [route.path for route in routes if isinstance(route, Mount)] == ["/static"]


def test_fixed_paths_come_before_the_rule_id() -> None:
    order = [route.path for route in inner_routes() if isinstance(route, APIRoute)]
    assert order.index("/categories/rules/add") < order.index("/categories/rules/{rule_id}")
    assert order.index("/categories/rules/delete") < order.index("/categories/rules/{rule_id}")


def test_what_other_code_and_tests_use_from_the_app_module_is_still_there() -> None:
    for name in (
        "create_app",
        "HOST",
        "SECURITY_HEADERS",
        "_today",
        "_utc_today",
        "_now",
        "_upload_name",
    ):
        assert hasattr(web_app, name), name
    assert isinstance(web_app._RESTORE_GATE, type(threading.Lock()))


@pytest.mark.parametrize("area", AREAS)
def test_one_router_module_per_area(area: str) -> None:
    module = importlib.import_module(f"finances.web.routes.{area}")
    assert isinstance(module.router, APIRouter)


def test_the_routes_package_holds_only_the_areas() -> None:
    names = sorted(path.stem for path in (WEB / "routes").glob("*.py") if path.stem != "__init__")
    assert names == AREAS


def test_no_web_module_is_longer_than_400_lines() -> None:
    sizes = {
        str(path.relative_to(WEB)): len(path.read_text(encoding="utf-8").splitlines())
        for path in WEB.rglob("*.py")
    }
    assert {name: size for name, size in sizes.items() if size > 400} == {}
```

## Tests to write

None. If coverage shows an unreached branch in a new module, add `tests/integration/test_web_split_more.py` and list it in your report.

## Rules for this phase

- Move code; do not rewrite it. A helper may change only where it is imported from.
- **Thin** as before: no query or rule in `web/`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/unit/test_web_split.py`, 16 tests;
- every earlier test passes unchanged: `git diff --stat HEAD -- tests` lists nothing (the given file is new, so it is not in the diff);
- `git status --short src/finances/web/templates src/finances/web/static` prints nothing;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.web --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|sum\(|timedelta" -- src/finances/web` and `git grep -n --untracked -E "from finances\.web\.app import [^\n]*(_today|_now|_utc_today)|from finances\.sync\.transport import" -- src/finances/web` (both no output).

## Report

As in `docs/phase-conventions.md`, headed `## Phase 32: split the web app (YYYY-MM-DD)`.
