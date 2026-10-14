"""The web application: read-only pages behind a host check and strict security headers."""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from finances.analysis.people import (
    JOINT_FILTER,
    UNASSIGNED_FILTER,
    list_transactions_with_people,
    load_attribution,
)
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import current_revision, head_revision
from finances.db.repositories import (
    get_account_by_name,
    latest_feed_pull,
    list_account_owners,
    list_accounts,
    list_cardholder_aliases,
    list_feed_accounts,
    list_people,
)
from finances.domain.models import FeedPull, Transaction
from finances.domain.money import format_cents
from finances.sync.links import load_access_url
from finances.sync.simplefin import SyncError

HOST = "127.0.0.1"
SECURITY_HEADERS = {
    "content-security-policy": (
        "default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self'; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    ),
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cache-control": "no-store",
}
NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"

_HERE = Path(__file__).parent
_TEMPLATES = Jinja2Templates(directory=_HERE / "templates")
_HEADER_BYTES = [(name.encode(), value.encode()) for name, value in SECURITY_HEADERS.items()]
_BULLETS = "\u2022\u2022"
_DEFAULT_LIMIT = "50"
_LIMIT_MAX = 1000
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_WHOLE = re.compile(r"[0-9]+")


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


@contextmanager
def _reading() -> Iterator[Session]:
    engine = get_engine()
    try:
        with session_scope(engine) as session:
            yield session
    finally:
        engine.dispose()


def _render(request: Request, name: str, context: dict, status_code: int = 200) -> Response:
    return _TEMPLATES.TemplateResponse(
        request, f"{name}.html", {"section": name, **context}, status_code=status_code
    )


def _not_migrated(request: Request) -> Response | None:
    if current_revision() != head_revision():
        return _render(request, "error", {"message": NOT_MIGRATED}, status_code=503)
    return None


def _day(text: str, name: str) -> date | None:
    if not text:
        return None
    if _DATE.fullmatch(text) is not None:
        try:
            return date.fromisoformat(text)
        except ValueError:
            pass
    raise ValueError(f"{name} must be a date as YYYY-MM-DD")


def _limit(text: str) -> int:
    if _WHOLE.fullmatch(text) is not None and 1 <= int(text) <= _LIMIT_MAX:
        return int(text)
    raise ValueError("limit must be a whole number from 1 to 1000")


def _find(session: Session, chosen: dict[str, str]) -> list[tuple[Transaction, str | None]]:
    account_id = None
    if chosen["account"]:
        account = get_account_by_name(session, chosen["account"])
        if account is None:
            raise ValueError("account not found")
        account_id = account.id
    start = _day(chosen["from"], "from")
    end = _day(chosen["to"], "to")
    limit = _limit(chosen["limit"])
    return list_transactions_with_people(
        session, account_id, start, end, limit, chosen["person"] or None
    )


def _transaction_row(item: Transaction, who: str | None, names: dict[int, str]) -> dict:
    return {
        "date": item.posted_date.isoformat(),
        "account": names[item.account_id],
        "description": item.description,
        "amount": format_cents(item.amount_cents),
        "card": f"{_BULLETS}{item.card_last4}" if item.card_last4 else "",
        "section": item.section or "",
        "person": who or "",
    }


def _keychain(link: str) -> str:
    try:
        return "no" if load_access_url(link) is None else "yes"
    except SyncError:
        return "unknown"


def _sync_row(
    link: str,
    account: str,
    feed_account: str,
    keychain: str,
    last: FeedPull | None,
    balanced: FeedPull | None,
) -> dict:
    return {
        "link": link,
        "account": account,
        "feed_account": feed_account,
        "keychain": keychain,
        "last_pull": "never" if last is None else last.pulled_at.strftime("%Y-%m-%d %H:%M UTC"),
        "balance_date": ""
        if balanced is None or balanced.balance_date is None
        else balanced.balance_date.isoformat(),
        "drift": ""
        if balanced is None or balanced.drift_cents is None
        else format_cents(balanced.drift_cents),
    }


def create_app(port: int) -> ASGIApp:
    """Return the web application for a server listening on HOST at this port."""
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    api.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")

    @api.get("/")
    def home() -> Response:
        return RedirectResponse("/accounts", status_code=303)

    @api.get("/accounts")
    def accounts(request: Request) -> Response:
        refused = _not_migrated(request)
        if refused is not None:
            return refused
        closed = request.query_params.get("closed") == "true"
        with _reading() as session:
            found = list_accounts(session, include_inactive=closed)
            attribution = load_attribution(session)
        rows = [
            {
                "name": account.name,
                "institution": account.institution,
                "type": account.type.value,
                "last4": f"{_BULLETS}{account.last4}" if account.last4 else "",
                "active": "yes" if account.is_active else "no",
                "owner": attribution.owner(account.id) or "",
            }
            for account in found
        ]
        return _render(request, "accounts", {"rows": rows, "closed": closed})

    @api.get("/people")
    def people(request: Request) -> Response:
        refused = _not_migrated(request)
        if refused is not None:
            return refused
        with _reading() as session:
            found = list_people(session)
            every_account = list_accounts(session, include_inactive=True)
            owners = list_account_owners(session)
            aliases = list_cardholder_aliases(session)
        rows = [
            {
                "name": person.name,
                "owns": ", ".join(
                    account.name for account in every_account if owners.get(account.id) == person.id
                ),
                "cardholders": ", ".join(
                    sorted(name for name, owner in aliases.items() if owner == person.id)
                ),
            }
            for person in found
        ]
        return _render(request, "people", {"rows": rows})

    @api.get("/transactions")
    def transactions(request: Request) -> Response:
        refused = _not_migrated(request)
        if refused is not None:
            return refused
        query = request.query_params
        chosen = {key: query.get(key, "") for key in ("account", "person", "from", "to")}
        chosen["limit"] = query.get("limit") or _DEFAULT_LIMIT
        error = None
        with _reading() as session:
            every_account = list_accounts(session, include_inactive=True)
            choices = {
                "accounts": [account.name for account in every_account],
                "people": [person.name for person in list_people(session)],
            }
            try:
                found = _find(session, chosen)
            except ValueError as refusal:
                found, error = [], str(refusal)
        names = {account.id: account.name for account in every_account}
        context = {
            "choices": choices,
            "special": (JOINT_FILTER, UNASSIGNED_FILTER),
            "chosen": chosen,
            "rows": [_transaction_row(item, who, names) for item, who in found],
            "error": error,
        }
        return _render(request, "transactions", context, 200 if error is None else 400)

    @api.get("/sync")
    def sync(request: Request) -> Response:
        refused = _not_migrated(request)
        if refused is not None:
            return refused
        with _reading() as session:
            mappings = list_feed_accounts(session)
            names = {item.id: item.name for item in list_accounts(session, include_inactive=True)}
            pulls = {
                item.account_id: (
                    latest_feed_pull(session, item.account_id),
                    latest_feed_pull(session, item.account_id, with_balance=True),
                )
                for item in mappings
            }
        keychain = {link: _keychain(link) for link in {item.link for item in mappings}}
        rows = [
            _sync_row(
                item.link,
                names[item.account_id],
                item.provider_account_id,
                keychain[item.link],
                *pulls[item.account_id],
            )
            for item in mappings
        ]
        return _render(request, "sync", {"rows": rows})

    return _Guard(api, port)
