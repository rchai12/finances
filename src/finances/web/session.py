"""The signed session cookie and the gate in front of every page."""

import hashlib
import hmac
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from fastapi import Request, Response
from fastapi.responses import PlainTextResponse, RedirectResponse

from finances.config import get_settings
from finances.web import app as web_app
from finances.web.login import has_password, session_key

COOKIE = "fin_session"
IDLE = timedelta(minutes=30)
LONGEST = timedelta(days=1)
_KEYCHAIN = "could not use the system keychain"


def make_cookie(key: str, issued: datetime, last: datetime) -> str:
    body = f"{int(issued.timestamp())}.{int(last.timestamp())}"
    signature = hmac.new(key.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def read_cookie(value: str, key: str, now: datetime) -> datetime | None:
    parts = value.split(".")
    if len(parts) != 3:
        return None
    issued_text, last_text, signature = parts
    if not issued_text.isdigit() or not last_text.isdigit():
        return None
    body = f"{issued_text}.{last_text}"
    expected = hmac.new(key.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        issued = datetime.fromtimestamp(int(issued_text), tz=UTC)
        last = datetime.fromtimestamp(int(last_text), tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None
    if now > last + IDLE or now > issued + LONGEST:
        return None
    return issued


def safe_next(text: str) -> str:
    if text.startswith("/") and not text.startswith("//") and "\\" not in text:
        return text
    return "/"


def over_https(request: Request) -> bool:
    host = request.headers.get("host", "").partition(":")[0]
    name = get_settings().web_hostname
    if name is not None and host == name:
        return True
    return request.headers.get("x-forwarded-proto") == "https"


def cookie_flags(request: Request) -> dict[str, str | bool]:
    flags: dict[str, str | bool] = {"httponly": True, "samesite": "strict", "path": "/"}
    if over_https(request):
        flags["secure"] = True
    return flags


async def gate(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    path = request.url.path
    if path == "/login" or path.startswith("/static/"):
        return await call_next(request)
    try:
        if not has_password():
            return await call_next(request)
        key = session_key() or ""
        now = web_app._now()
        issued = read_cookie(request.cookies.get(COOKIE, ""), key, now)
    except ValueError:
        return PlainTextResponse(_KEYCHAIN, status_code=503)
    if issued is None:
        return _send_to_login(request)
    response = await call_next(request)
    if path != "/logout":
        response.set_cookie(COOKIE, make_cookie(key, issued, now), **cookie_flags(request))
    return response


def _send_to_login(request: Request) -> Response:
    if request.method in {"GET", "HEAD"}:
        target = request.url.path
        if request.url.query:
            target = f"{target}?{request.url.query}"
        location = f"/login?next={quote(target, safe='/')}"
    else:
        location = "/login"
    return RedirectResponse(location, status_code=303)
