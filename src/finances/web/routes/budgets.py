"""The Budgets page and its forms."""

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import Response

from finances.analysis.budgets import budget_report
from finances.db.repositories import remove_budget, set_budget
from finances.domain.budgets import AMOUNT_MESSAGE
from finances.domain.money import parse_money
from finances.domain.spending import month_bounds, month_range
from finances.views.budgets import budget_rows, budgets_summary
from finances.views.categories import category_choices
from finances.web import app as web_app
from finances.web.access import _reading
from finances.web.forms import _REFUSALS, _Field, refused
from finances.web.render import _done, _not_migrated, _render

router = APIRouter()


def _budgets_page(
    request: Request,
    *,
    month_text: str = "",
    form: dict[str, str] | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> Response:
    today = web_app._today()
    month_label: str | None = None
    start: date | None = None
    end: date | None = None
    rows: list = []
    summary = ""
    try:
        start, end = month_range(month_text) if month_text else month_bounds(today)
        month_label = start.isoformat()[:7]
    except ValueError as month_error:
        error = str(month_error)
        status_code = 400
    with _reading() as session:
        choices = category_choices(session)
        if month_label is not None and start is not None:
            lines = budget_report(session, start, today)
            rows = budget_rows(lines)
            summary = budgets_summary(lines)
    context = {
        "month_text": month_text,
        "month_label": month_label,
        "start": start.isoformat() if start is not None else "",
        "end": end.isoformat() if end is not None else "",
        "rows": rows,
        "summary": summary,
        "choices": choices,
        "form": form if form is not None else {"name": "", "amount": ""},
        "error": error,
    }
    return _render(request, "budgets", context, status_code)


@router.get("/budgets")
def budgets(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    return _budgets_page(request, month_text=request.query_params.get("month", ""))


@router.post("/budgets/set")
def set_budget_route(
    request: Request, csrf: _Field = "", name: _Field = "", amount: _Field = ""
) -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    form = {"name": name, "amount": amount}
    try:
        cents = parse_money(amount)
    except ValueError:
        return _budgets_page(request, form=form, error=AMOUNT_MESSAGE, status_code=400)
    try:
        with _reading() as session:
            set_budget(session, name, cents)
    except _REFUSALS as error:
        return _budgets_page(request, form=form, error=str(error), status_code=400)
    return _done("/budgets?notice=budget-set")


@router.post("/budgets/remove")
def remove_budget_route(request: Request, csrf: _Field = "", name: _Field = "") -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    try:
        with _reading() as session:
            remove_budget(session, name)
    except _REFUSALS as error:
        return _budgets_page(request, error=str(error), status_code=400)
    return _done("/budgets?notice=budget-removed")
