"""The Transfers page and its forms."""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import Response

from finances.categorize.transfers import pair_transfers
from finances.db.repositories import create_transfer_pair, reject_transfer, unpair_transfer
from finances.domain.models import CONFIRMED
from finances.domain.transfers import TRANSFER_MAX_DAYS
from finances.views.transfers import suggestion_lines, transfer_lines
from finances.web.access import _reading
from finances.web.forms import _REFUSALS, _Field, refused
from finances.web.helpers import _WHOLE, _id
from finances.web.render import _done, _not_migrated, _render

router = APIRouter()


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


@router.get("/transfers")
def transfers(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    return _transfers_page(request)


@router.post("/transfers/find")
def find_transfers(request: Request, csrf: _Field = "") -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    with _reading() as session:
        pair_transfers(session)
    return _done("/transfers?notice=transfers-found")


@router.post("/transfers/confirm")
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


@router.post("/transfers/reject")
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


@router.post("/transfers/unpair")
def unpair(request: Request, csrf: _Field = "", pair: _Field = "", back: _Field = "") -> Response:
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
