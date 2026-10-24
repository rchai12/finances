"""The web application: pages and setup forms behind a host check, a form token, and headers."""

import threading
from datetime import UTC, date, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from finances import clock

HOST = "127.0.0.1"
SECURITY_HEADERS = {
    "content-security-policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    ),
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "same-origin",
    "cache-control": "no-store",
}

_HERE = Path(__file__).parent
_HEADER_BYTES = [(name.encode(), value.encode()) for name, value in SECURITY_HEADERS.items()]
_RESTORE_GATE = threading.Lock()


class _Guard:
    """Refuse requests not addressed to this server by name, and add the security headers."""

    def __init__(self, app: ASGIApp, port: int) -> None:
        self.app = app
        self.hosts = {f"{HOST}:{port}".encode(), f"localhost:{port}".encode()}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                kept = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower().decode("latin-1") not in SECURITY_HEADERS
                ]
                message = {**message, "headers": kept + _HEADER_BYTES}
            await send(message)

        hosts = [value for name, value in scope["headers"] if name.lower() == b"host"]
        if len(hosts) != 1 or hosts[0] not in self.hosts:
            refused = PlainTextResponse("Bad host", status_code=400)
            await refused(scope, receive, send_with_headers)
            return
        await self.app(scope, receive, send_with_headers)


def _today() -> date:
    return clock.today()


def _utc_today() -> date:
    return datetime.now(UTC).date()


def _now() -> datetime:
    return datetime.now(UTC)


def _upload_name(sent: str) -> str:
    """The file name after its last folder separator, cut to 255 characters."""
    name = sent.replace("\\", "/").rpartition("/")[2]
    return name[:255]


def create_app(port: int) -> ASGIApp:
    """Return the web application for a server listening on HOST at this port."""
    from finances.web.forms import configure_origins
    from finances.web.routes import (
        accounts,
        backups,
        budgets,
        categories,
        history,
        home,
        people,
        reports,
        review,
        shared,
        statements,
        sync,
        transactions,
        transfers,
    )

    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    api.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")
    configure_origins(api, port)
    for area in (
        home,
        budgets,
        accounts,
        people,
        transactions,
        statements,
        categories,
        reports,
        transfers,
        sync,
        backups,
        history,
        review,
        shared,
    ):
        api.router.routes.extend(area.router.routes)
    return _Guard(api, port)
