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

from finances.analysis.balances import balance_report
from finances.analysis.months import month_report
from finances.analysis.people import (
    JOINT_FILTER,
    UNASSIGNED_FILTER,
    list_transactions_with_people,
)
from finances.analysis.spending import spending_report
from finances.categorize.service import categorize
from finances.categorize.transfers import pair_transfers
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import current_revision, head_revision
from finances.db.repositories import (
    AccountExistsError,
    CategoryExistsError,
    PersonExistsError,
    account_names,
    clear_category_by_hand,
    create_account,
    create_category,
    create_person,
    create_rule,
    create_transfer_pair,
    delete_rule,
    get_account_by_name,
    get_person_by_name,
    get_transaction,
    list_feed_accounts,
    list_feed_links,
    list_new_feed_accounts,
    list_people,
    map_feed_account,
    reject_transfer,
    resolve_owner,
    set_account_owner,
    set_cardholder_alias,
    set_category_by_hand,
    set_feed_account_ignored,
    unpair_transfer,
)
from finances.domain.feed_setup import new_accounts
from finances.domain.models import CONFIRMED, Account, AccountType, Transaction
from finances.domain.rules import MATCHES
from finances.domain.spending import BY, month_bounds, month_range
from finances.domain.transfers import TRANSFER_MAX_DAYS
from finances.sync import transport
from finances.sync.links import (
    delete_access_url,
    load_access_url,
    save_access_url,
    validate_link_name,
)
from finances.sync.runner import run_links
from finances.sync.simplefin import SyncError, claim_access_url, fetch_accounts
from finances.views.accounts import account_rows
from finances.views.balances import balance_rows, balance_summary
from finances.views.categories import (
    category_choices,
    category_lines,
    rule_lines,
    transaction_detail,
    uncategorized_lines,
)
from finances.views.months import month_notes, month_rows
from finances.views.people import people_rows
from finances.views.spending import spending_heading, spending_rows, spending_summary
from finances.views.sync import (
    run_rows,
    setup_offers,
    simplefin_messages,
    status_rows,
    unmapped_accounts,
    waiting_counts,
)
from finances.views.transactions import transaction_row
from finances.views.transfers import suggestion_lines, transfer_lines, transfer_of

HOST = "127.0.0.1"
SECURITY_HEADERS = {
    "content-security-policy": (
        "default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self'; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    ),
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "same-origin",
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
    "ignored": "That SimpleFIN account will not be tracked.",
    "tracked": "That SimpleFIN account is offered for setup again.",
    "category-added": "Category added.",
    "rule-added": "Rule added, and the rules were run again.",
    "rule-deleted": "Rule deleted, and the rules were run again.",
    "category-set": "Category saved.",
    "category-cleared": "Category left to the rules.",
    "transfers-found": "Clear transfers were paired; the rest wait for review.",
    "transfer-confirmed": "Transfer saved.",
    "transfer-rejected": "Those two will not be paired.",
    "transfer-removed": "Transfer removed; those two will not be paired again.",
}
ACCOUNT_TYPES = tuple(item.value for item in AccountType)

_HERE = Path(__file__).parent
_TEMPLATES = Jinja2Templates(directory=_HERE / "templates")
_HEADER_BYTES = [(name.encode(), value.encode()) for name, value in SECURITY_HEADERS.items()]
_DEFAULT_LIMIT = "50"
_UNCATEGORIZED_LIMIT = 50
_REPORT_MONTHS = 6
_LIMIT_MAX = 1000
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_WHOLE = re.compile(r"[0-9]+")
_ID = re.compile(r"[0-9]{1,18}")
_PRIORITY = re.compile(r"-?[0-9]{1,6}")
TRANSACTION_NOT_FOUND = "transaction not found"
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
_REFUSALS = (ValueError, SyncError, AccountExistsError, PersonExistsError, CategoryExistsError)
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


def _spending_range(form: dict[str, str]) -> tuple[date, date]:
    """The days the Reports page's spending covers, refusing a form that does not fit."""
    if form["month"] and (form["start"] or form["end"]):
        raise ValueError("give a month, or from and to, not both")
    if bool(form["start"]) != bool(form["end"]):
        raise ValueError("give both from and to")
    start, end = _day(form["start"], "from"), _day(form["end"], "to")
    if start is not None and end is not None:
        return start, end
    if form["month"]:
        return month_range(form["month"])
    return month_bounds(_today())


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


def _blank_account_form() -> dict[str, str]:
    return {"name": "", "institution": "", "type": "credit_card", "last4": ""}


def _add_account(session: Session, name: str, institution: str, kind: str, last4: str) -> Account:
    return create_account(session, name, institution, kind, last4=last4.strip() or None)


def _mapped(link: str, next_page: str) -> Response:
    if next_page == "sync":
        return _done("/sync?notice=mapped")
    return _done(f"/sync/accounts?link={link}&notice=mapped")


def _accounts_page(
    request: Request,
    *,
    closed: bool = False,
    form: dict[str, str] | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> Response:
    with _reading() as session:
        rows = account_rows(session, include_inactive=closed)
        every_account = list(account_names(session).values())
        people = [person.name for person in list_people(session)]
    context = {
        "rows": rows,
        "closed": closed,
        "types": ACCOUNT_TYPES,
        "every_account": every_account,
        "people": people,
        "form": form if form is not None else _blank_account_form(),
        "error": error,
    }
    return _render(request, "accounts", context, status_code)


def _people_page(request: Request, *, error: str | None = None, status_code: int = 200) -> Response:
    with _reading() as session:
        rows = people_rows(session)
    context = {"rows": rows, "people": [row.name for row in rows], "error": error}
    return _render(request, "people", context, status_code)


def _sync_page(
    request: Request, *, link: str = "", error: str | None = None, status_code: int = 200
) -> Response:
    with _reading() as session:
        rows = status_rows(session)
        offers = setup_offers(session)
        ignored = list_new_feed_accounts(session, ignored=True)
        people = [person.name for person in list_people(session)]
        unmapped = [account.name for account in unmapped_accounts(session)]
    offered = [
        {
            "link": offer.link,
            "feed_account": offer.feed_account,
            "name": offer.name,
            "institution": offer.institution,
            "guess": {
                "name": offer.guess.name,
                "institution": offer.guess.institution,
                "type": offer.guess.type.value,
                "last4": offer.guess.last4 or "",
            },
            "owner": offer.owner or "",
            "suggestion": offer.suggestion or "",
        }
        for offer in offers
    ]
    links = sorted({row.link for row in rows})
    context = {
        "rows": rows,
        "links": links,
        "form": {"link": link},
        "error": error,
        "new_accounts": offered,
        "ignored_accounts": [
            {
                "link": item.link,
                "feed_account": item.provider_account_id,
                "name": item.name,
                "institution": item.institution,
            }
            for item in ignored
        ],
        "people": people,
        "types": ACCOUNT_TYPES,
        "unmapped": unmapped,
    }
    return _render(request, "sync", context, status_code)


def _error_page(request: Request, message: str) -> Response:
    return _render(request, "error", {"message": message, "back": "/sync"}, status_code=400)


def _id(text: str) -> int | None:
    return int(text) if _ID.fullmatch(text) is not None else None


def _priority(text: str) -> int:
    if not text:
        return 0
    if _PRIORITY.fullmatch(text) is None:
        raise ValueError("priority must be a whole number")
    return int(text)


def _rule_form(
    pattern: str = "", match: str = "contains", priority: str = "0", category: str = ""
) -> dict[str, str]:
    return {"pattern": pattern, "match": match, "priority": priority, "category": category}


def _categories_page(
    request: Request,
    *,
    rule_form: dict[str, str] | None = None,
    category_form: dict[str, str] | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> Response:
    with _reading() as session:
        choices = category_choices(session)
        context = {
            "uncategorized": uncategorized_lines(session, _UNCATEGORIZED_LIMIT),
            "limit": _UNCATEGORIZED_LIMIT,
            "rules": rule_lines(session),
            "matches": MATCHES,
            "choices": choices,
            "rule_form": rule_form if rule_form is not None else _rule_form(),
            "tree": category_lines(session),
            "groups": [group for group, _ in choices],
            "category_form": category_form or {"name": "", "group": ""},
            "error": error,
        }
    return _render(request, "categories", context, status_code)


def _missing_transaction(request: Request) -> Response:
    context = {"message": TRANSACTION_NOT_FOUND, "back": "/transactions"}
    return _render(request, "error", context, status_code=404)


def _transaction_page(
    request: Request, text: str, *, error: str | None = None, status_code: int = 200
) -> Response:
    transaction_id = _id(text)
    with _reading() as session:
        detail = None if transaction_id is None else transaction_detail(session, transaction_id)
        choices = category_choices(session)
        transfer = None if detail is None else transfer_of(session, detail.id)
    if detail is None:
        return _missing_transaction(request)
    context = {
        "detail": detail,
        "transfer": transfer,
        "choices": choices,
        "matches": MATCHES,
        "rule_form": _rule_form(pattern=detail.merchant, category=detail.category),
        "error": error,
    }
    return _render(request, "transactions_one", context, status_code)


def _transfers_page(
    request: Request, *, error: str | None = None, status_code: int = 200
) -> Response:
    with _reading() as session:
        context = {
            "suggestions": suggestion_lines(session),
            "pairs": transfer_lines(session),
            "max_days": TRANSFER_MAX_DAYS,
            "error": error,
        }
    return _render(request, "transfers", context, status_code)


def _transfer_sides(out: str, into: str) -> tuple[int, int]:
    out_id, in_id = _id(out), _id(into)
    if out_id is None or in_id is None:
        raise ValueError("transaction not found")
    return out_id, in_id


def _known_transaction(text: str) -> int | None:
    transaction_id = _id(text)
    if transaction_id is None:
        return None
    with _reading() as session:
        return transaction_id if get_transaction(session, transaction_id) is not None else None


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
                person = resolve_owner(session, owner)
                set_account_owner(session, found.id, None if person is None else person.id)
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
            names = account_names(session)
            choices = {
                "accounts": list(names.values()),
                "people": [person.name for person in list_people(session)],
            }
            try:
                found = _find(session, chosen)
            except ValueError as refusal:
                found, error = [], str(refusal)
        context = {
            "choices": choices,
            "special": (JOINT_FILTER, UNASSIGNED_FILTER),
            "chosen": chosen,
            "rows": [(item.id, transaction_row(item, who, names)) for item, who in found],
            "error": error,
        }
        return _render(request, "transactions", context, 200 if error is None else 400)

    @api.get("/transactions/{transaction_id}")
    def transaction(request: Request, transaction_id: str) -> Response:
        stopped = _not_migrated(request)
        if stopped is not None:
            return stopped
        return _transaction_page(request, transaction_id)

    @api.post("/transactions/{transaction_id}/category")
    def set_category(
        request: Request, transaction_id: str, csrf: _Field = "", category: _Field = ""
    ) -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        found = _known_transaction(transaction_id)
        if found is None:
            return _missing_transaction(request)
        try:
            with _reading() as session:
                set_category_by_hand(session, found, category)
        except _REFUSALS as error:
            return _transaction_page(request, transaction_id, error=str(error), status_code=400)
        return _done(f"/transactions/{found}?notice=category-set")

    @api.post("/transactions/{transaction_id}/category/clear")
    def clear_category(request: Request, transaction_id: str, csrf: _Field = "") -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        found = _known_transaction(transaction_id)
        if found is None:
            return _missing_transaction(request)
        with _reading() as session:
            clear_category_by_hand(session, found)
            categorize(session)
        return _done(f"/transactions/{found}?notice=category-cleared")

    @api.get("/categories")
    def categories(request: Request) -> Response:
        stopped = _not_migrated(request)
        if stopped is not None:
            return stopped
        return _categories_page(request)

    @api.post("/categories/add")
    def add_category(
        request: Request, csrf: _Field = "", name: _Field = "", group: _Field = ""
    ) -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            with _reading() as session:
                create_category(session, name, group)
        except _REFUSALS as error:
            form = {"name": name, "group": group}
            return _categories_page(request, category_form=form, error=str(error), status_code=400)
        return _done("/categories?notice=category-added")

    @api.post("/categories/rules/add")
    def add_rule(
        request: Request,
        csrf: _Field = "",
        pattern: _Field = "",
        match: _Field = "",
        priority: _Field = "",
        category: _Field = "",
        back: _Field = "",
    ) -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            number = _priority(priority)
            with _reading() as session:
                create_rule(session, pattern, category, match, number)
                categorize(session)
        except _REFUSALS as error:
            form = _rule_form(pattern, match, priority, category)
            return _categories_page(request, rule_form=form, error=str(error), status_code=400)
        if _WHOLE.fullmatch(back) is not None:
            return _done(f"/transactions/{back}?notice=rule-added")
        return _done("/categories?notice=rule-added")

    @api.post("/categories/rules/delete")
    def remove_rule(request: Request, csrf: _Field = "", rule: _Field = "") -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            rule_id = _id(rule)
            if rule_id is None:
                raise ValueError("rule not found")
            with _reading() as session:
                delete_rule(session, rule_id)
                categorize(session)
        except _REFUSALS as error:
            return _categories_page(request, error=str(error), status_code=400)
        return _done("/categories?notice=rule-deleted")

    @api.get("/reports")
    def reports(request: Request) -> Response:
        stopped = _not_migrated(request)
        if stopped is not None:
            return stopped
        query = request.query_params
        form = {
            "month": query.get("month", ""),
            "start": query.get("from", ""),
            "end": query.get("to", ""),
            "by": query.get("by") or "category",
        }
        spending, error, last = None, None, _today()
        with _reading() as session:
            balances = balance_report(session)
            try:
                start, end = _spending_range(form)
                report = spending_report(session, start, end, form["by"])
            except ValueError as refusal:
                error = str(refusal)
            else:
                spending = {
                    "heading": spending_heading(report),
                    "by": report.by,
                    "rows": spending_rows(report),
                    "summary": spending_summary(report),
                }
                last = report.end
            lines = month_report(session, last, _REPORT_MONTHS)
        context = {
            "balances": balance_rows(balances),
            "balance_summary": balance_summary(balances),
            "months": month_rows(lines),
            "month_notes": month_notes(lines),
            "spending": spending,
            "form": form,
            "bys": BY,
            "error": error,
        }
        return _render(request, "reports", context, 200 if error is None else 400)

    @api.get("/transfers")
    def transfers(request: Request) -> Response:
        stopped = _not_migrated(request)
        if stopped is not None:
            return stopped
        return _transfers_page(request)

    @api.post("/transfers/find")
    def find_transfers(request: Request, csrf: _Field = "") -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        with _reading() as session:
            pair_transfers(session)
        return _done("/transfers?notice=transfers-found")

    @api.post("/transfers/confirm")
    def confirm_transfer(
        request: Request,
        csrf: _Field = "",
        out: _Field = "",
        into: Annotated[str, Form(alias="in")] = "",
    ) -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            out_id, in_id = _transfer_sides(out, into)
            with _reading() as session:
                create_transfer_pair(session, out_id, in_id, CONFIRMED)
        except _REFUSALS as error:
            return _transfers_page(request, error=str(error), status_code=400)
        return _done("/transfers?notice=transfer-confirmed")

    @api.post("/transfers/reject")
    def reject(
        request: Request,
        csrf: _Field = "",
        out: _Field = "",
        into: Annotated[str, Form(alias="in")] = "",
    ) -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            out_id, in_id = _transfer_sides(out, into)
            with _reading() as session:
                reject_transfer(session, out_id, in_id)
        except _REFUSALS as error:
            return _transfers_page(request, error=str(error), status_code=400)
        return _done("/transfers?notice=transfer-rejected")

    @api.post("/transfers/unpair")
    def unpair(
        request: Request, csrf: _Field = "", pair: _Field = "", back: _Field = ""
    ) -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            pair_id = _id(pair)
            if pair_id is None:
                raise ValueError("transfer not found")
            with _reading() as session:
                unpair_transfer(session, pair_id)
        except _REFUSALS as error:
            return _transfers_page(request, error=str(error), status_code=400)
        if _WHOLE.fullmatch(back) is not None:
            return _done(f"/transactions/{back}?notice=transfer-removed")
        return _done("/transfers?notice=transfer-removed")

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
            names = account_names(session)
            mapped = {
                item.provider_account_id: names[item.account_id]
                for item in list_feed_accounts(session, link)
            }
        context["accounts"] = list(names.values())
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
        next_page: Annotated[str, Form(alias="next")] = "",
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
                map_feed_account(session, found.id, feed_account, link)
        except _REFUSALS as error:
            return _error_page(request, str(error))
        return _mapped(link, next_page)

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
        owner: _Field = "",
        next_page: Annotated[str, Form(alias="next")] = "",
    ) -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            with _reading() as session:
                made = _add_account(session, account, institution, kind, last4)
                validate_link_name(link)
                map_feed_account(session, made.id, feed_account, link)
                if owner.strip():
                    person = resolve_owner(session, owner)
                    set_account_owner(session, made.id, None if person is None else person.id)
        except _REFUSALS as error:
            return _error_page(request, str(error))
        return _mapped(link, next_page)

    def tracking(
        request: Request, csrf: str, link: str, feed_account: str, ignored: bool
    ) -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        try:
            with _reading() as session:
                set_feed_account_ignored(session, link.strip(), feed_account.strip(), ignored)
        except _REFUSALS as error:
            return _error_page(request, str(error))
        return _done(f"/sync?notice={'ignored' if ignored else 'tracked'}")

    @api.post("/sync/ignore")
    def ignore(
        request: Request, csrf: _Field = "", link: _Field = "", feed_account: _Field = ""
    ) -> Response:
        return tracking(request, csrf, link, feed_account, True)

    @api.post("/sync/track")
    def track(
        request: Request, csrf: _Field = "", link: _Field = "", feed_account: _Field = ""
    ) -> Response:
        return tracking(request, csrf, link, feed_account, False)

    @api.post("/sync/run")
    def run(request: Request, csrf: _Field = "") -> Response:
        stopped = refused(request, csrf)
        if stopped is not None:
            return stopped
        with _engine() as engine:
            with session_scope(engine) as session:
                links = list_feed_links(session)
            runs = run_links(engine, links, today=_today(), transport=transport.urllib_transport)
            if any(item.report is not None for item in runs):
                with session_scope(engine) as session:
                    categorize(session)
                    pair_transfers(session)
            with session_scope(engine) as session:
                rows = run_rows(runs, account_names(session))
                waiting = waiting_counts(session, runs)
        context = {
            "rows": rows,
            "errors": [item.error for item in runs if item.error is not None],
            "messages": [f"{link}: {message}" for link, message in simplefin_messages(runs)],
            "ran": bool(links),
            "waiting": [f"{link}: {new_accounts(count)} to set up." for link, count in waiting],
        }
        return _render(request, "sync_run", context)

    return _Guard(api, port)
