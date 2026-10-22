"""The home page."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from finances.analysis.dashboard import dashboard
from finances.config import get_settings
from finances.views.balances import balance_summary
from finances.views.budgets import budget_rows
from finances.views.health import health_rows
from finances.views.insights import finding_rows, findings_summary
from finances.views.months import month_rows
from finances.views.upcoming import upcoming_rows, upcoming_summary
from finances.web import app as web_app
from finances.web.access import _reading
from finances.web.render import _not_migrated, _render

router = APIRouter()
_PROBLEM_LINKS = {
    "backup": "/backups",
    "sync": "/sync",
    "drift": "/sync",
    "statements": "/statements",
    "gap": "/statements",
}


@router.get("/")
def home(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    folder = get_settings().effective_backup_dir
    with _reading() as session:
        found = dashboard(session, web_app._today(), folder)
        context = {
            "today": found.today.isoformat(),
            "month_label": found.today.isoformat()[:7],
            "uncategorized": found.uncategorized,
            "transfers_waiting": found.transfers_waiting,
            "problems": health_rows(found.problems),
            "problem_links": _PROBLEM_LINKS,
            "has_accounts": bool(found.balance.lines),
            "balance_summary": balance_summary(found.balance),
            "months": month_rows(found.months),
            "findings": finding_rows(found.insights)[:3],
            "findings_summary": findings_summary(found.insights),
            "budgets": budget_rows(list(found.budgets)),
            "upcoming": upcoming_rows(found.upcoming),
            "upcoming_summary": upcoming_summary(found.upcoming),
        }
    return _render(request, "dashboard", context)
