"""CSV downloads of the transactions, year, and spending the pages already show."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from finances.analysis.export import export_lines
from finances.analysis.spending import spending_report
from finances.analysis.yearend import year_report
from finances.views.export import spending_csv, transactions_csv, year_csv
from finances.web import app as web_app
from finances.web.access import _reading
from finances.web.helpers import _WHOLE
from finances.web.render import _not_migrated, _render
from finances.web.routes.reports import YEAR_REFUSED, _spending_range
from finances.web.routes.transactions import _DEFAULT_LIMIT, _FILTER_FIELDS, _search_query

router = APIRouter()


def _csv(text: str, name: str) -> Response:
    return Response(
        text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


def _refused(request: Request, message: str, back: str) -> Response:
    return _render(request, "error", {"message": message, "back": back}, 400)


@router.get("/export/transactions")
def transactions(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    query = request.query_params
    chosen = {key: query.get(key, "") for key in _FILTER_FIELDS}
    chosen["limit"] = chosen["limit"] or _DEFAULT_LIMIT
    try:
        wanted = _search_query(chosen)
        with _reading() as session:
            lines = export_lines(session, wanted)
    except ValueError as error:
        return _refused(request, str(error), "/transactions")
    start, end = query.get("from", ""), query.get("to", "")
    name = f"transactions-{start}-to-{end}.csv" if start and end else "transactions.csv"
    return _csv(transactions_csv(lines), name)


@router.get("/export/year")
def year(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    text = request.query_params.get("year", "")
    if not text:
        number = web_app._today().year
    elif _WHOLE.fullmatch(text) is None:
        return _refused(request, YEAR_REFUSED, "/year")
    else:
        number = int(text)
    with _reading() as session:
        try:
            report = year_report(session, number)
        except ValueError as error:
            return _refused(request, str(error), "/year")
    return _csv(year_csv(report), f"year-{number}.csv")


@router.get("/export/spending")
def spending(request: Request) -> Response:
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
    try:
        start, end = _spending_range(form)
        with _reading() as session:
            report = spending_report(session, start, end, form["by"])
    except ValueError as error:
        return _refused(request, str(error), "/reports")
    name = f"spending-by-{report.by}-{start.isoformat()}-to-{end.isoformat()}.csv"
    return _csv(spending_csv(report), name)
