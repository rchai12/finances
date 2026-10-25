"""The login and logout pages."""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response

from finances.views.login import lock_text
from finances.web import app as web_app
from finances.web.forms import forged
from finances.web.login import attempt, has_password, session_key
from finances.web.render import _render
from finances.web.session import COOKIE, cookie_flags, make_cookie, safe_next

router = APIRouter()
_UNSET = "no password is set; run fin web password"
_WRONG = "wrong password"
_KEYCHAIN = "could not use the system keychain"


@router.get("/login")
def login_page(request: Request, next: str = "/") -> Response:
    try:
        ready = has_password()
    except ValueError:
        return PlainTextResponse(_KEYCHAIN, status_code=503)
    return _render(request, "login", {"ready": ready, "next": safe_next(next)})


@router.post("/login")
def submit_login(
    request: Request,
    csrf: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
    next: Annotated[str, Form()] = "/",
) -> Response:
    stopped = forged(request, csrf)
    if stopped is not None:
        return stopped
    target = safe_next(next)
    try:
        ready = has_password()
    except ValueError:
        return PlainTextResponse(_KEYCHAIN, status_code=503)
    if not ready:
        return _page(request, ready=False, next_page=target, error=_UNSET)
    now = web_app._now()
    result = attempt(password, now)
    if result.ok:
        key = session_key() or ""
        response = RedirectResponse(target, status_code=303)
        response.set_cookie(COOKIE, make_cookie(key, now, now), **cookie_flags(request))
        return response
    error = lock_text(result.locked_until) if result.locked_until is not None else _WRONG
    return _page(request, ready=True, next_page=target, error=error)


@router.post("/logout")
def logout(request: Request, csrf: Annotated[str, Form()] = "") -> Response:
    stopped = forged(request, csrf)
    if stopped is not None:
        return stopped
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE, **cookie_flags(request))
    return response


def _page(request: Request, *, ready: bool, next_page: str, error: str) -> Response:
    return _render(
        request, "login", {"ready": ready, "next": next_page, "error": error}, status_code=400
    )
