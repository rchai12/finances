"""The web application: pages and setup forms behind a host check, a form token, and headers."""

import hmac
import re
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import Engine
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
    AccountExistsError,
    PersonExistsError,
    create_account,
    create_person,
    get_account_by_name,
    get_person_by_name,
    latest_feed_pull,
    list_account_owners,
    list_accounts,
    list_cardholder_aliases,
    list_feed_accounts,
    list_people,
    map_feed_account,
    set_account_owner,
    set_cardholder_alias,
)
from finances.domain.models import Account, AccountType, FeedPull, Transaction
from finances.domain.money import format_cents
from finances.sync import transport
from finances.sync.links import (
    delete_access_url,
    load_access_url,
    save_access_url,
    validate_link_name,
)
from finances.sync.runner import AccountSync, run_links
from finances.sync.simplefin import SyncError, claim_access_url, fetch_accounts

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
CSRF_COOKIE = "fin_csrf"
NOTICES = {
    "account-added": "Account added.",
    "owner-set": "Owner saved.",
    "person-added": "Person added.",
    "alias-set": "Cardholder name saved.",
    "linked": "Link saved. Map each SimpleFIN account below.",
    "unlinked": "Link removed from the Keychain.",
    "mapped": "Account mapped.",
}
ACCOUNT_TYPES = tuple(item.value for item in AccountType)

_HERE = Path(__file__).parent
_TEMPLATES = Jinja2Templates(directory=_HERE / "templates")
_HEADER_BYTES = [(name.encode(), value.encode()) for name, value in SECURITY_HEADERS.items()]
_BULLETS = "\u2022\u2022"
_DEFAULT_LIMIT = "50"
_LIMIT_MAX = 1000
_FEED_ID_LIMIT = 200
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_WHOLE = re.compile(r"[0-9]+")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
_REFUSALS = (ValueError, SyncError, AccountExistsError, PersonExistsError)
_Field = Annotated[str, Form()]


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
def _engine() -> Iterator[Engine]:
    engine = get_engine()
    try:
        yield engine
    finally:
        engine.dispose()


@contextmanager
def _reading() -> Iterator[Session]:
    with _engine() as engine, session_scope(engine) as session:
        yield session


def _today() -> date:
    return datetime.now(UTC).date()


def _render(request: Request, name: str, context: dict, status_code: int = 200) -> Response:
    cookie = request.cookies.get(CSRF_COOKIE, "")
    fresh = _TOKEN.fullmatch(cookie) is None
    token = secrets.token_urlsafe(32) if fresh else cookie
    shared = {
        "section": name.split("_")[0],
        "csrf": token,
        "notice": NOTICES.get(request.query_params.get("notice", "")),
        "error": None,
    }
    response = _TEMPLATES.TemplateResponse(
        request, f"{name}.html", {**shared, **context}, status_code=status_code
    )
    if fresh:
        response.set_cookie(CSRF_COOKIE, token, httponly=True, samesite="strict", path="/")
    return response


def _not_migrated(request: Request) -> Response | None:
    if current_revision() != head_revision():
        return _render(request, "error", {"message": NOT_MIGRATED}, status_code=503)
    return None


def _done(path: str) -> Response:
    return RedirectResponse(path, status_code=303)


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


def _drift(pull: FeedPull | None) -> str:
    return "" if pull is None or pull.drift_cents is None else format_cents(pull.drift_cents)


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
        "drift": _drift(balanced),
    }


def _run_row(link: str, item: AccountSync, names: dict[int, str]) -> dict:
    pull = item.pull
    counts = (
        ("", "", "", "")
        if pull is None
        else (str(pull.inserted), str(pull.updated), str(pull.removed), str(pull.unchanged))
    )
    return {
        "link": link,
        "account": "" if item.account_id is None else names[item.account_id],
        "feed_account": item.provider_account_id,
        **dict(zip(("new", "changed", "removed", "same"), counts, strict=True)),
        "drift": _drift(pull),
        "problem": item.problem or "",
    }


def _blank_account_form() -> dict[str, str]:
    return {"name": "", "institution": "", "type": "credit_card", "last4": ""}


def _add_account(session: Session, name: str, institution: str, kind: str, last4: str) -> Account:
    if kind not in ACCOUNT_TYPES:
        raise ValueError(f"type must be one of: {', '.join(ACCOUNT_TYPES)}")
    return create_account(session, name, institution, kind, last4=last4.strip() or None)


def _feed_id(feed_account: str) -> str:
    feed_id = feed_account.strip()
    if not 1 <= len(feed_id) <= _FEED_ID_LIMIT:
        raise ValueError("feed account id must be 1 to 200 characters")
    return feed_id


def _accounts_page(
    request: Request,
    *,
    closed: bool = False,
    form: dict[str, str] | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> Response:
    with _reading() as session:
        shown = list_accounts(session, include_inactive=closed)
        every_account = list_accounts(session, include_inactive=True)
        people = [person.name for person in list_people(session)]
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
        for account in shown
    ]
    context = {
        "rows": rows,
        "closed": closed,
        "types": ACCOUNT_TYPES,
        "every_account": [account.name for account in every_account],
        "people": people,
        "form": form if form is not None else _blank_account_form(),
        "error": error,
    }
    return _render(request, "accounts", context, status_code)


def _people_page(request: Request, *, error: str | None = None, status_code: int = 200) -> Response:
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
    context = {"rows": rows, "people": [person.name for person in found], "error": error}
    return _render(request, "people", context, status_code)


def _sync_page(
    request: Request, *, link: str = "", error: str | None = None, status_code: int = 200
) -> Response:
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
    links = sorted({item.link for item in mappings})
    keychain = {name: _keychain(name) for name in links}
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
    context = {"rows": rows, "links": links, "form": {"link": link}, "error": error}
    return _render(request, "sync", context, status_code)


def _error_page(request: Request, message: str) -> Response:
    return _render(request, "error", {"message": message, "back": "/sync"}, status_code=400)


def create_app(port: int) -> ASGIApp:
    """Return the web application for a server listening on HOST at this port."""
    api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    api.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")
    origins = {f"http://{HOST}:{port}", f"http://localhost:{port}"}

    def refused(request: Request, csrf: str) -> Response | None:
        """Check a form before it is used: its origin, its token, then the database."""
        origin = request.headers.get("origin")
        if origin is not None and origin not in origins:
            return PlainTextResponse("Bad origin", status_code=403)
        cookie = request.cookies.get(CSRF_COOKIE, "")
        if _TOKEN.fullmatch(cookie) is None or not hmac.compare_digest(
            cookie.encode(), csrf.encode()
        ):
            return PlainTextResponse("Bad form token", status_code=403)
        return _not_migrated(request)

    @api.get("/")
    def home() -> Response:
        return _done("/accounts")

    @api.get("/accounts")
    def accounts(request: Request) -> Response:
        stopped = _not_migrated(request)
        if stopped is not None:
            return stopped
        return _accounts_page(request, closed=request.query_params.get("closed") == "true")

    @api.post("/accounts/add")
    def add_account(
        request: Request,
        csrf: _Field = "",
        name: _Field = "",
        institution: _Field = "",
        kind: Annotated[str, Form(alias="type")] = "",
        last4: _Field = "",
    ) -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            with _reading() as session:
                _add_account(session, name, institution, kind, last4)
        except _REFUSALS as error:
            form = {"name": name, "institution": institution, "type": kind, "last4": last4}
            return _accounts_page(request, form=form, error=str(error), status_code=400)
        return _done("/accounts?notice=account-added")

    @api.post("/accounts/owner")
    def set_owner(
        request: Request, csrf: _Field = "", account: _Field = "", owner: _Field = ""
    ) -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            with _reading() as session:
                found = get_account_by_name(session, account)
                if found is None:
                    raise ValueError("account not found")
                person_id = None
                if owner.strip().lower() != JOINT_FILTER:
                    person = get_person_by_name(session, owner)
                    if person is None:
                        raise ValueError("person not found")
                    person_id = person.id
                set_account_owner(session, found.id, person_id)
        except _REFUSALS as error:
            return _accounts_page(request, error=str(error), status_code=400)
        return _done("/accounts?notice=owner-set")

    @api.get("/people")
    def people(request: Request) -> Response:
        stopped = _not_migrated(request)
        if stopped is not None:
            return stopped
        return _people_page(request)

    @api.post("/people/add")
    def add_person(request: Request, csrf: _Field = "", name: _Field = "") -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            with _reading() as session:
                create_person(session, name)
        except _REFUSALS as error:
            return _people_page(request, error=str(error), status_code=400)
        return _done("/people?notice=person-added")

    @api.post("/people/alias")
    def add_alias(
        request: Request, csrf: _Field = "", person: _Field = "", cardholder: _Field = ""
    ) -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            with _reading() as session:
                found = get_person_by_name(session, person)
                if found is None:
                    raise ValueError("person not found")
                set_cardholder_alias(session, cardholder, found.id)
        except _REFUSALS as error:
            return _people_page(request, error=str(error), status_code=400)
        return _done("/people?notice=alias-set")

    @api.get("/transactions")
    def transactions(request: Request) -> Response:
        stopped = _not_migrated(request)
        if stopped is not None:
            return stopped
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
        stopped = _not_migrated(request)
        if stopped is not None:
            return stopped
        return _sync_page(request)

    @api.post("/sync/link")
    def link(
        request: Request,
        csrf: _Field = "",
        link: _Field = "",
        token: _Field = "",
        replace: _Field = "",
    ) -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            validate_link_name(link)
            if load_access_url(link) is not None and replace != "on":
                raise ValueError(f"link {link} is already set up; tick Replace to set it up again")
            save_access_url(link, claim_access_url(token, transport.urllib_transport))
        except _REFUSALS as error:
            return _sync_page(request, link=link, error=str(error), status_code=400)
        return _done(f"/sync/accounts?link={link}&notice=linked")

    @api.post("/sync/unlink")
    def unlink(request: Request, csrf: _Field = "", link: _Field = "") -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            if not delete_access_url(link):
                raise ValueError(f"link {link} is not set up")
        except _REFUSALS as error:
            return _sync_page(request, error=str(error), status_code=400)
        return _done("/sync?notice=unlinked")

    @api.get("/sync/accounts")
    def sync_accounts(request: Request) -> Response:
        stopped = _not_migrated(request)
        if stopped is not None:
            return stopped
        link = request.query_params.get("link", "")
        context: dict = {"link": link, "accounts": [], "types": ACCOUNT_TYPES, "rows": []}
        context["messages"] = []
        try:
            validate_link_name(link)
            found = load_access_url(link)
            if found is None:
                raise ValueError(f"link {link} is not set up")
            answer = fetch_accounts(found, _today(), _today(), transport.urllib_transport)
        except ValueError as error:
            return _render(request, "sync_accounts", {**context, "error": str(error)}, 400)
        except SyncError as error:
            return _render(request, "sync_accounts", {**context, "error": str(error)}, 502)
        with _reading() as session:
            every_account = list_accounts(session, include_inactive=True)
            names = {account.id: account.name for account in every_account}
            mapped = {
                item.provider_account_id: names[item.account_id]
                for item in list_feed_accounts(session, link)
            }
        context["accounts"] = [account.name for account in every_account]
        context["rows"] = [
            {
                "feed_account": item.provider_account_id,
                "institution": item.institution,
                "name": item.name,
                "currency": item.currency,
                "mapped_to": mapped.get(item.provider_account_id, ""),
            }
            for item in answer.accounts
        ]
        context["messages"] = answer.messages
        return _render(request, "sync_accounts", context)

    @api.post("/sync/map")
    def map_account(
        request: Request,
        csrf: _Field = "",
        link: _Field = "",
        feed_account: _Field = "",
        account: _Field = "",
    ) -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            validate_link_name(link)
            with _reading() as session:
                found = get_account_by_name(session, account)
                if found is None:
                    raise ValueError("account not found")
                map_feed_account(session, found.id, _feed_id(feed_account), link)
        except _REFUSALS as error:
            return _error_page(request, str(error))
        return _done(f"/sync/accounts?link={link}&notice=mapped")

    @api.post("/sync/create")
    def create_and_map(
        request: Request,
        csrf: _Field = "",
        link: _Field = "",
        feed_account: _Field = "",
        account: _Field = "",
        institution: _Field = "",
        kind: Annotated[str, Form(alias="type")] = "",
        last4: _Field = "",
    ) -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            with _reading() as session:
                made = _add_account(session, account, institution, kind, last4)
                validate_link_name(link)
                map_feed_account(session, made.id, _feed_id(feed_account), link)
        except _REFUSALS as error:
            return _error_page(request, str(error))
        return _done(f"/sync/accounts?link={link}&notice=mapped")

    @api.post("/sync/run")
    def run(request: Request, csrf: _Field = "") -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        with _engine() as engine:
            with session_scope(engine) as session:
                links = sorted({item.link for item in list_feed_accounts(session)})
            runs = run_links(engine, links, today=_today(), transport=transport.urllib_transport)
            with session_scope(engine) as session:
                names = {
                    item.id: item.name for item in list_accounts(session, include_inactive=True)
                }
        context = {
            "rows": [
                _run_row(item.link, account, names)
                for item in runs
                if item.report is not None
                for account in item.report.accounts
            ],
            "errors": [item.error for item in runs if item.error is not None],
            "messages": [
                f"{item.link}: {message}"
                for item in runs
                if item.report is not None
                for message in item.report.messages
            ],
            "ran": bool(links),
        }
        return _render(request, "sync_run", context)

    return _Guard(api, port)
