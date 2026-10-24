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
    "history",
    "home",
    "people",
    "reports",
    "review",
    "shared",
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
    ("POST", "/transactions/{transaction_id}/tags/add"),
    ("POST", "/transactions/{transaction_id}/tags/remove"),
    ("POST", "/transactions/{transaction_id}/note"),
    ("POST", "/transactions/{transaction_id}/split"),
    ("POST", "/transactions/{transaction_id}/split/clear"),
    ("GET", "/shared"),
    ("POST", "/shared/settle"),
    ("POST", "/shared/settlements/delete"),
    ("POST", "/transactions/{transaction_id}/share"),
    ("POST", "/transactions/{transaction_id}/share/clear"),
    ("GET", "/statements"),
    ("POST", "/statements/upload"),
    ("GET", "/categories"),
    ("POST", "/categories/add"),
    ("POST", "/categories/rules/add"),
    ("POST", "/categories/rules/preview"),
    ("POST", "/categories/rules/delete"),
    ("POST", "/categories/aliases/add"),
    ("POST", "/categories/aliases/delete"),
    ("POST", "/categories/rename"),
    ("POST", "/categories/delete"),
    ("GET", "/categories/rules/{rule_id}"),
    ("POST", "/categories/rules/{rule_id}"),
    ("GET", "/reports"),
    ("GET", "/insights"),
    ("GET", "/ahead"),
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
    ("GET", "/history"),
    ("GET", "/review"),
    ("POST", "/review"),
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
    assert order.index("/categories/rules/preview") < order.index("/categories/rules/{rule_id}")
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
