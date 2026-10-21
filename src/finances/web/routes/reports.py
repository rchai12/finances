"""The Reports and Insights pages."""

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import Response

from finances.analysis.balances import balance_report
from finances.analysis.insights import insights_report
from finances.analysis.months import month_report
from finances.analysis.recurring import recurring_charges
from finances.analysis.spending import spending_report
from finances.domain.spending import BY, month_bounds, month_range
from finances.views.balances import balance_rows, balance_summary
from finances.views.insights import (
    finding_rows,
    findings_summary,
    insights_heading,
    merchant_rows,
)
from finances.views.months import month_notes, month_rows
from finances.views.recurring import recurring_rows, recurring_summary
from finances.views.spending import spending_heading, spending_rows, spending_summary
from finances.web import app as web_app
from finances.web.access import _reading
from finances.web.helpers import _day
from finances.web.render import _not_migrated, _render

router = APIRouter()
_REPORT_MONTHS = 6


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
    return month_bounds(web_app._today())


def _month_start(text: str) -> date:
    """The first day of the month typed, or of this month when nothing was typed."""
    if not text:
        return month_bounds(web_app._today())[0]
    return month_range(text)[0]


@router.get("/reports")
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
    spending, error, last = None, None, web_app._today()
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
                "start": report.start.isoformat(),
                "end": report.end.isoformat(),
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


@router.get("/insights")
def insights(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    form = {"month": request.query_params.get("month", "")}
    try:
        first = _month_start(form["month"])
    except ValueError as refusal:
        context = {"form": form, "report": None, "error": str(refusal)}
        return _render(request, "insights", context, 400)
    with _reading() as session:
        found = insights_report(session, first)
        end = month_bounds(first)[1]
        series = recurring_charges(session, end)
    report = {
        "heading": insights_heading(found),
        "findings": finding_rows(found),
        "findings_summary": findings_summary(found),
        "recurring": recurring_rows(series),
        "recurring_summary": recurring_summary(series),
        "merchants": merchant_rows(found),
        "start": first.isoformat(),
        "end": end.isoformat(),
    }
    return _render(request, "insights", {"form": form, "report": report})
