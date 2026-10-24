"""The Shared page and the share forms on a transaction's page."""

from fastapi import APIRouter, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from finances.analysis.shared import owed_report
from finances.db.repositories import (
    delete_settlement,
    list_people,
    list_settlements,
    list_shares,
    record_settlement,
    share_transaction,
    unshare_transaction,
)
from finances.domain.money import parse_money
from finances.views.shared import owed_text, settlement_rows, share_rows
from finances.web import app as web_app
from finances.web.access import _reading
from finances.web.forms import _REFUSALS, _Field, refused
from finances.web.helpers import _day, _id
from finances.web.render import _done, _not_migrated, _render
from finances.web.routes.transactions import (
    _known_transaction,
    _missing_transaction,
    _transaction_page,
)

router = APIRouter()


def _names(session: Session) -> list[str]:
    return [person.name for person in list_people(session)]


def _empty_settle() -> dict[str, str]:
    return {"payer": "", "payee": "", "amount": "", "day": web_app._today().isoformat()}


def _shared_page(
    request: Request,
    *,
    error: str | None = None,
    status_code: int = 200,
    settle_form: dict[str, str] | None = None,
) -> Response:
    with _reading() as session:
        context = {
            "owed": [owed_text(item) for item in owed_report(session)],
            "shares": share_rows(list_shares(session)),
            "settlements": settlement_rows(list_settlements(session)),
            "people": _names(session),
            "settle_form": settle_form if settle_form is not None else _empty_settle(),
            "error": error,
        }
    return _render(request, "shared", context, status_code)


@router.get("/shared")
def shared(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    return _shared_page(request)


@router.post("/shared/settle")
def settle(
    request: Request,
    csrf: _Field = "",
    payer: _Field = "",
    payee: _Field = "",
    amount: _Field = "",
    day: _Field = "",
) -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    form = {"payer": payer, "payee": payee, "amount": amount, "day": day}
    try:
        cents = parse_money(amount)
        when = _day(day, "date")
        if when is None:
            when = web_app._today()
        with _reading() as session:
            record_settlement(session, payer, payee, cents, when)
    except _REFUSALS as error:
        return _shared_page(request, error=str(error), status_code=400, settle_form=form)
    return _done("/shared?notice=settled")


@router.post("/shared/settlements/delete")
def remove_settlement(request: Request, csrf: _Field = "", settlement: _Field = "") -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    try:
        settlement_id = _id(settlement)
        if settlement_id is None:
            raise ValueError("settlement not found")
        with _reading() as session:
            delete_settlement(session, settlement_id)
    except _REFUSALS as error:
        return _shared_page(request, error=str(error), status_code=400)
    return _done("/shared?notice=settlement-deleted")


@router.post("/transactions/{transaction_id}/share")
def share(
    request: Request,
    transaction_id: str,
    csrf: _Field = "",
    debtor: _Field = "",
    payer: _Field = "",
    share: _Field = "",
) -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    found = _known_transaction(transaction_id)
    if found is None:
        return _missing_transaction(request)
    form = {"debtor": debtor, "payer": payer, "share": share}
    try:
        size_cents = None if share == "" else parse_money(share)
        with _reading() as session:
            share_transaction(session, found, debtor, payer=payer, size_cents=size_cents)
    except _REFUSALS as error:
        return _transaction_page(
            request, transaction_id, error=str(error), status_code=400, share_form=form
        )
    return _done(f"/transactions/{found}?notice=share-saved")


@router.post("/transactions/{transaction_id}/share/clear")
def clear_share(request: Request, transaction_id: str, csrf: _Field = "") -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    found = _known_transaction(transaction_id)
    if found is None:
        return _missing_transaction(request)
    try:
        with _reading() as session:
            unshare_transaction(session, found)
    except _REFUSALS as error:
        return _transaction_page(request, transaction_id, error=str(error), status_code=400)
    return _done(f"/transactions/{found}?notice=share-removed")
