"""Form checks: the origin, the token, and the database, plus the form field type."""

import hmac
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import PlainTextResponse, Response

from finances.db.repositories import AccountExistsError, CategoryExistsError, PersonExistsError
from finances.sync.simplefin import SyncError
from finances.web import app as web_app
from finances.web.render import _TOKEN, CSRF_COOKIE, _not_migrated

_REFUSALS = (ValueError, SyncError, AccountExistsError, PersonExistsError, CategoryExistsError)
_Field = Annotated[str, Form()]


def configure_origins(api: FastAPI, port: int) -> None:
    """Record the origins this application accepts for forms, from its port."""
    api.state.origins = {
        f"http://{web_app.HOST}:{port}",
        f"http://localhost:{port}",
    }


def forged(request: Request, csrf: str) -> Response | None:
    """Check a form's origin and token, on any database."""
    origin = request.headers.get("origin")
    if origin is not None and origin not in request.app.state.origins:
        return PlainTextResponse("Bad origin", status_code=403)
    cookie = request.cookies.get(CSRF_COOKIE, "")
    if _TOKEN.fullmatch(cookie) is None or not hmac.compare_digest(cookie.encode(), csrf.encode()):
        return PlainTextResponse("Bad form token", status_code=403)
    return None


def refused(request: Request, csrf: str) -> Response | None:
    """Check a form before it is used: its origin, its token, then the database."""
    return forged(request, csrf) or _not_migrated(request)
