"""The Accounts pages and their forms."""

import json
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import Response

from finances.analysis.account_page import account_page
from finances.analysis.listings import account_listing
from finances.db.repositories import (
    account_names,
    get_account_by_name,
    list_people,
    rename_account,
    resolve_owner,
    set_account_active,
    set_account_owner,
)
from finances.domain.spending import month_bounds, month_range
from finances.views.account_page import (
    account_detail_rows,
    account_month_rows,
    balance_history_rows,
    group_rows,
)
from finances.views.accounts import account_rows
from finances.views.charts import balance_chart, months_chart, pie_chart
from finances.views.transactions import found_rows
from finances.web import app as web_app
from finances.web.access import _reading
from finances.web.forms import _REFUSALS, _Field, refused
from finances.web.helpers import ACCOUNT_TYPES, _add_account
from finances.web.render import _done, _not_migrated, _render

router = APIRouter()


def _blank_account_form() -> dict[str, str]:
    return {"name": "", "institution": "", "type": "credit_card", "last4": ""}


def _missing_account(request: Request, message: str) -> Response:
    context = {"message": message, "back": "/accounts"}
    return _render(request, "error", context, status_code=404)


def _accounts_page(
    request: Request,
    *,
    closed: bool = False,
    form: dict[str, str] | None = None,
    rename_form: dict[str, str] | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> Response:
    with _reading() as session:
        rows = account_rows(account_listing(session, include_inactive=closed))
        every_account = list(account_names(session).values())
        people = [person.name for person in list_people(session)]
    context = {
        "rows": rows,
        "closed": closed,
        "types": ACCOUNT_TYPES,
        "every_account": every_account,
        "people": people,
        "form": form if form is not None else _blank_account_form(),
        "rename_form": rename_form or {"account": "", "to": ""},
        "error": error,
    }
    return _render(request, "accounts", context, status_code)


@router.get("/accounts")
def accounts(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    return _accounts_page(request, closed=request.query_params.get("closed") == "true")


@router.get("/account")
def one_account(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    name = request.query_params.get("name", "")
    card = request.query_params.get("card", "")
    month_text = request.query_params.get("month", "")
    today = web_app._today()
    month_error: str | None = None
    try:
        start, end = month_range(month_text) if month_text else month_bounds(today)
    except ValueError as error:
        month_error = str(error)
        start, end = month_bounds(today)
    with _reading() as session:
        found = get_account_by_name(session, name) if name.strip() else None
        if found is None:
            return _missing_account(request, "account not found")
        try:
            page = account_page(session, found, card, start, end, today)
        except ValueError as error:
            return _missing_account(request, str(error))
        names = account_names(session)
        spending = [] if month_error is not None else group_rows(page)
        pie = pie_chart(page.spending) if spending else None
        months_data = months_chart(page.months)
        balance_data = balance_chart(page.balances)
        context = {
            "section": "accounts",
            "name": found.name,
            "card": card,
            "cards": page.cards,
            "detail": account_detail_rows(page),
            "month_label": start.isoformat()[:7],
            "month_text": month_text,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "spending": spending,
            "months": account_month_rows(page),
            "balances": balance_history_rows(page),
            "transactions": found_rows(page.latest, names),
            "pie_chart": None if pie is None else json.dumps(pie),
            "months_chart": json.dumps(months_data),
            "balance_chart": None if balance_data is None else json.dumps(balance_data),
            "error": month_error,
        }
    return _render(request, "account", context, status_code=400 if month_error is not None else 200)


@router.post("/accounts/add")
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


@router.post("/accounts/owner")
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


@router.post("/accounts/rename")
def rename_account_route(
    request: Request, csrf: _Field = "", account: _Field = "", to: _Field = ""
) -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    try:
        with _reading() as session:
            found = get_account_by_name(session, account)
            if found is None:
                raise ValueError("account not found")
            rename_account(session, found.id, to)
    except _REFUSALS as error:
        form = {"account": account, "to": to}
        return _accounts_page(request, rename_form=form, error=str(error), status_code=400)
    return _done("/accounts?notice=account-renamed")


@router.post("/accounts/active")
def set_active(
    request: Request, csrf: _Field = "", account: _Field = "", active: _Field = ""
) -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    try:
        if active not in ("true", "false"):
            raise ValueError("choose Close or Reopen")
        with _reading() as session:
            found = get_account_by_name(session, account)
            if found is None:
                raise ValueError("account not found")
            set_account_active(session, found.id, active == "true")
    except _REFUSALS as error:
        return _accounts_page(request, error=str(error), status_code=400)
    notice = "account-reopened" if active == "true" else "account-closed"
    return _done(f"/accounts?notice={notice}")
