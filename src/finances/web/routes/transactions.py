"""The Transactions pages, the bulk form, and the per-transaction category forms."""

from collections.abc import Callable
from urllib.parse import parse_qsl, urlencode

from fastapi import APIRouter, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from finances.analysis.categories import category_tree, transaction_facts
from finances.analysis.people import JOINT_FILTER, UNASSIGNED_FILTER
from finances.analysis.refunds import refund_facts
from finances.analysis.search import TransactionQuery, search_transactions
from finances.analysis.transfers import pair_of
from finances.categorize.service import categorize
from finances.db.repositories import (
    account_names,
    add_tags,
    clear_categories_by_hand,
    clear_category_by_hand,
    clear_split,
    get_transaction,
    list_categories,
    list_people,
    list_tags,
    note_of,
    remove_tags,
    set_categories_by_hand,
    set_category_by_hand,
    set_note,
    share_of,
    split_by_sizes,
    splits_for,
    tags_for,
)
from finances.domain.rules import MATCHES
from finances.domain.splits import parse_parts
from finances.views.categories import category_choices, transaction_detail
from finances.views.refunds import refund_view, refunded_lines
from finances.views.shared import share_text
from finances.views.transactions import found_rows, part_lines
from finances.views.transfers import transfer_line
from finances.web.access import _reading
from finances.web.forms import _REFUSALS, _Field, refused
from finances.web.helpers import _WHOLE, _day, _id, _rule_form
from finances.web.render import _done, _not_migrated, _render

router = APIRouter()
_DEFAULT_LIMIT = "50"
_LIMIT_MAX = 1000
TRANSACTION_NOT_FOUND = "transaction not found"
_SEARCH_FIELDS = (
    "text",
    "account",
    "person",
    "category",
    "merchant",
    "group",
    "bank",
    "card",
    "tag",
)
_FILTER_FIELDS = (*_SEARCH_FIELDS, "kind", "from", "to", "limit")
_KEPT = ("group", "bank", "card", "kind")


def _limit(text: str) -> int:
    if _WHOLE.fullmatch(text) is not None and 1 <= int(text) <= _LIMIT_MAX:
        return int(text)
    raise ValueError("limit must be a whole number from 1 to 1000")


def _search_query(chosen: dict[str, str]) -> TransactionQuery:
    start = _day(chosen["from"], "from")
    end = _day(chosen["to"], "to")
    limit = _limit(chosen["limit"])
    labels = {key: chosen[key] for key in _SEARCH_FIELDS}
    return TransactionQuery(**labels, kind=chosen["kind"], start=start, end=end, limit=limit)


def _filter_query(values: dict[str, str]) -> str:
    """The page's filter fields that are set, in field order, URL-encoded."""
    return urlencode([(key, values[key]) for key in _FILTER_FIELDS if values.get(key)])


def _back_filters(back: str) -> dict[str, str]:
    """The filter fields kept from a bulk form's back value, in field order."""
    allowed = set(_FILTER_FIELDS)
    got = {key: value for key, value in parse_qsl(back) if key in allowed and value}
    return {key: got[key] for key in _FILTER_FIELDS if key in got}


def _transactions_page(
    request: Request,
    filters: dict[str, str] | None = None,
    *,
    error: str | None = None,
    status_code: int = 200,
) -> Response:
    query = request.query_params if filters is None else filters
    chosen = {key: query.get(key, "") for key in _FILTER_FIELDS if key != "limit"}
    chosen["limit"] = query.get("limit") or _DEFAULT_LIMIT
    sent = {key: query.get(key, "") for key in _FILTER_FIELDS}
    back = _filter_query(sent)
    select_all_query = f"{back}&select=all" if back else "select=all"
    select_all = (request.query_params if filters is None else {}).get("select") == "all"
    if filters is not None:
        select_all = False
    with _reading() as session:
        names = account_names(session)
        choices = {
            "accounts": list(names.values()),
            "people": [person.name for person in list_people(session)],
            "categories": category_choices(category_tree(session)),
        }
        tag_choices = [item.tag for item in list_tags(session)]
        try:
            found = search_transactions(session, _search_query(chosen))
        except ValueError as refusal:
            found, error = [], str(refusal) if error is None else error
            status_code = 400
    context = {
        "choices": choices,
        "tag_choices": tag_choices,
        "special": (JOINT_FILTER, UNASSIGNED_FILTER),
        "chosen": chosen,
        "kept": [key for key in _KEPT if chosen[key]],
        "back": back,
        "select_all_query": select_all_query,
        "select_all": select_all,
        "rows": found_rows(found, names),
        "error": error,
    }
    return _render(request, "transactions", context, status_code)


def _missing_transaction(request: Request) -> Response:
    context = {"message": TRANSACTION_NOT_FOUND, "back": "/transactions"}
    return _render(request, "error", context, status_code=404)


def _transaction_page(
    request: Request,
    text: str,
    *,
    error: str | None = None,
    status_code: int = 200,
    split_form: str = "",
    share_form: dict[str, str] | None = None,
) -> Response:
    transaction_id = _id(text)
    with _reading() as session:
        loaded = None if transaction_id is None else transaction_facts(session, transaction_id)
        detail = None if loaded is None else transaction_detail(loaded)
        choices = category_choices(category_tree(session))
        found = None if detail is None else pair_of(session, detail.id)
        transfer = None if found is None else transfer_line(found)
        facts = None if detail is None else refund_facts(session, detail.id)
        tags = [] if detail is None else tags_for(session, [detail.id]).get(detail.id, [])
        note = None if detail is None else note_of(session, detail.id)
        names = {item.id: item.name for item in list_categories(session)}
        stored = [] if detail is None else splits_for(session, [detail.id]).get(detail.id, [])
        parts = part_lines(stored, names)
        people = [person.name for person in list_people(session)]
        stored_share = None if detail is None else share_of(session, detail.id)
        share = None if stored_share is None else share_text(stored_share)
    if detail is None or facts is None:
        return _missing_transaction(request)
    refund = refund_view(facts, detail.amount)
    refunded = refunded_lines(facts)
    context = {
        "detail": detail,
        "transfer": transfer,
        "choices": choices,
        "matches": MATCHES,
        "rule_form": _rule_form(pattern=detail.merchant, category=detail.category),
        "error": error,
        "refund": refund,
        "refunded": refunded,
        "tags": tags,
        "note": note,
        "parts": parts,
        "split_form": split_form,
        "share": share,
        "people": people,
        "share_form": share_form
        if share_form is not None
        else {"debtor": "", "payer": "", "share": ""},
    }
    return _render(request, "transactions_one", context, status_code)


def _known_transaction(text: str) -> int | None:
    transaction_id = _id(text)
    if transaction_id is None:
        return None
    with _reading() as session:
        return transaction_id if get_transaction(session, transaction_id) is not None else None


@router.get("/transactions")
def transactions(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    return _transactions_page(request)


@router.post("/transactions/bulk")
async def bulk_category(request: Request) -> Response:
    form = await request.form(max_fields=1100)
    csrf = str(form.get("csrf") or "")
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    category = str(form.get("category") or "")
    action = str(form.get("action") or "")
    back = str(form.get("back") or "")
    chosen_ids = [str(value) for value in form.getlist("id")]
    filters = _back_filters(back)
    query = urlencode(list(filters.items()))

    def apply() -> str:
        numbers = []
        for text in chosen_ids:
            number = _id(text)
            if number is None:
                raise ValueError("transaction not found")
            numbers.append(number)
        if action not in ("set", "clear"):
            raise ValueError("choose Set category or Leave to the rules")
        with _reading() as session:
            if action == "set":
                set_categories_by_hand(session, numbers, category)
                return "bulk-set"
            clear_categories_by_hand(session, numbers)
            categorize(session)
            return "bulk-cleared"

    try:
        notice = await run_in_threadpool(apply)
    except _REFUSALS as error:
        return _transactions_page(request, filters, error=str(error), status_code=400)
    location = (
        f"/transactions?{query}&notice={notice}" if query else f"/transactions?notice={notice}"
    )
    return _done(location)


@router.get("/transactions/{transaction_id}")
def transaction(request: Request, transaction_id: str) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    return _transaction_page(request, transaction_id)


@router.post("/transactions/{transaction_id}/category")
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


@router.post("/transactions/{transaction_id}/category/clear")
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


def _write_on_transaction(
    request: Request,
    transaction_id: str,
    csrf: str,
    apply: Callable[[int], str],
    *,
    split_form: str = "",
) -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    found = _known_transaction(transaction_id)
    if found is None:
        return _missing_transaction(request)
    try:
        notice = apply(found)
    except _REFUSALS as error:
        return _transaction_page(
            request, transaction_id, error=str(error), status_code=400, split_form=split_form
        )
    return _done(f"/transactions/{found}?notice={notice}")


@router.post("/transactions/{transaction_id}/tags/add")
def add_tag(request: Request, transaction_id: str, csrf: _Field = "", tag: _Field = "") -> Response:
    def apply(found: int) -> str:
        with _reading() as session:
            add_tags(session, [found], tag)
        return "tag-added"

    return _write_on_transaction(request, transaction_id, csrf, apply)


@router.post("/transactions/{transaction_id}/tags/remove")
def remove_tag(
    request: Request, transaction_id: str, csrf: _Field = "", tag: _Field = ""
) -> Response:
    def apply(found: int) -> str:
        with _reading() as session:
            remove_tags(session, [found], tag)
        return "tag-removed"

    return _write_on_transaction(request, transaction_id, csrf, apply)


@router.post("/transactions/{transaction_id}/note")
def save_note(
    request: Request, transaction_id: str, csrf: _Field = "", text: _Field = ""
) -> Response:
    def apply(found: int) -> str:
        with _reading() as session:
            return "note-removed" if set_note(session, found, text) is None else "note-saved"

    return _write_on_transaction(request, transaction_id, csrf, apply)


@router.post("/transactions/{transaction_id}/split")
def split_transaction(
    request: Request, transaction_id: str, csrf: _Field = "", parts: _Field = ""
) -> Response:
    def apply(found: int) -> str:
        with _reading() as session:
            split_by_sizes(session, found, parse_parts(parts))
        return "split-saved"

    return _write_on_transaction(request, transaction_id, csrf, apply, split_form=parts)


@router.post("/transactions/{transaction_id}/split/clear")
def remove_split(request: Request, transaction_id: str, csrf: _Field = "") -> Response:
    def apply(found: int) -> str:
        with _reading() as session:
            clear_split(session, found)
            categorize(session)
        return "split-removed"

    return _write_on_transaction(request, transaction_id, csrf, apply)
