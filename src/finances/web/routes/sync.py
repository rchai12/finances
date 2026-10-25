"""The Sync pages and forms: links, account mapping, and the run."""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import Response

from finances.analysis.simplefin import (
    mapping_status,
    setup_offers,
    unmapped_accounts,
    waiting_counts,
)
from finances.categorize.service import categorize
from finances.categorize.transfers import pair_transfers
from finances.db.engine import session_scope
from finances.db.repositories import (
    account_names,
    get_account_by_name,
    list_feed_accounts,
    list_feed_links,
    list_new_feed_accounts,
    list_people,
    map_feed_account,
    resolve_owner,
    set_account_owner,
    set_feed_account_ignored,
)
from finances.domain.feed_setup import new_accounts
from finances.sync import transport
from finances.sync.links import (
    delete_access_url,
    keychain_state,
    load_access_url,
    save_access_url,
    validate_link_name,
)
from finances.sync.runner import run_links
from finances.sync.simplefin import SyncError, claim_access_url, fetch_accounts
from finances.views.sync import run_rows, simplefin_messages, status_rows
from finances.web import app as web_app
from finances.web.access import _engine, _reading
from finances.web.forms import _REFUSALS, _Field, refused
from finances.web.helpers import ACCOUNT_TYPES, _add_account
from finances.web.login import has_password
from finances.web.render import _done, _not_migrated, _render
from finances.web.session import recheck

router = APIRouter()


def _mapped(link: str, next_page: str) -> Response:
    if next_page == "sync":
        return _done("/sync?notice=mapped")
    return _done(f"/sync/accounts?link={link}&notice=mapped")


def _sync_page(
    request: Request, *, link: str = "", error: str | None = None, status_code: int = 200
) -> Response:
    with _reading() as session:
        rows = status_rows(mapping_status(session, keychain_state))
        offers = setup_offers(session)
        ignored = list_new_feed_accounts(session, ignored=True)
        people = [person.name for person in list_people(session)]
        unmapped = [account.name for account in unmapped_accounts(session)]
        links = sorted({row.link for row in rows} | set(list_feed_links(session)))
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
        "reauth": has_password(),
    }
    return _render(request, "sync", context, status_code)


def _error_page(request: Request, message: str) -> Response:
    return _render(request, "error", {"message": message, "back": "/sync"}, status_code=400)


def tracking(request: Request, csrf: str, link: str, feed_account: str, ignored: bool) -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    try:
        with _reading() as session:
            set_feed_account_ignored(session, link.strip(), feed_account.strip(), ignored)
    except _REFUSALS as error:
        return _error_page(request, str(error))
    return _done(f"/sync?notice={'ignored' if ignored else 'tracked'}")


@router.get("/sync")
def sync(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    return _sync_page(request)


@router.post("/sync/link")
def link(
    request: Request,
    csrf: _Field = "",
    link: _Field = "",
    token: _Field = "",
    replace: _Field = "",
    password: _Field = "",
) -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    denied = recheck(password)
    if denied is not None:
        return _sync_page(request, link=link, error=denied, status_code=400)
    try:
        validate_link_name(link)
        if load_access_url(link) is not None and replace != "on":
            raise ValueError(f"link {link} is already set up; tick Replace to set it up again")
        save_access_url(link, claim_access_url(token, transport.urllib_transport))
    except _REFUSALS as error:
        return _sync_page(request, link=link, error=str(error), status_code=400)
    return _done(f"/sync/accounts?link={link}&notice=linked")


def _unlink_page(request: Request, link: str, error: str | None = None) -> Response:
    return _render(
        request,
        "sync_unlink",
        {"link": link, "reauth": has_password(), "error": error},
        200 if error is None else 400,
    )


@router.get("/sync/unlink")
def unlink_confirm(request: Request) -> Response:
    if "link" not in request.query_params:
        return Response(status_code=405)
    link = request.query_params["link"]
    try:
        validate_link_name(link)
    except ValueError as error:
        return _sync_page(request, error=str(error), status_code=400)
    return _unlink_page(request, link)


@router.post("/sync/unlink")
def unlink(
    request: Request, csrf: _Field = "", link: _Field = "", password: _Field = ""
) -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    denied = recheck(password)
    if denied is not None:
        return _unlink_page(request, link, denied)
    try:
        if not delete_access_url(link):
            raise ValueError(f"link {link} is not set up")
    except _REFUSALS as error:
        return _sync_page(request, error=str(error), status_code=400)
    return _done("/sync?notice=unlinked")


@router.get("/sync/accounts")
def sync_accounts(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    link = request.query_params.get("link", "")
    context: dict = {
        "link": link,
        "accounts": [],
        "types": ACCOUNT_TYPES,
        "rows": [],
        "unlinkable": False,
    }
    context["messages"] = []
    try:
        validate_link_name(link)
        found = load_access_url(link)
        if found is None:
            raise ValueError(f"link {link} is not set up")
        context["unlinkable"] = True
        answer = fetch_accounts(
            found, web_app._utc_today(), web_app._utc_today(), transport.urllib_transport
        )
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


@router.post("/sync/map")
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


@router.post("/sync/create")
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


@router.post("/sync/ignore")
def ignore(
    request: Request, csrf: _Field = "", link: _Field = "", feed_account: _Field = ""
) -> Response:
    return tracking(request, csrf, link, feed_account, True)


@router.post("/sync/track")
def track(
    request: Request, csrf: _Field = "", link: _Field = "", feed_account: _Field = ""
) -> Response:
    return tracking(request, csrf, link, feed_account, False)


@router.post("/sync/run")
def run(request: Request, csrf: _Field = "") -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    with _engine() as engine:
        with session_scope(engine) as session:
            links = list_feed_links(session)
        runs = run_links(
            engine, links, today=web_app._utc_today(), transport=transport.urllib_transport
        )
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
