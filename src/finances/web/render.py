"""Page rendering: templates, notices, the form token cookie, and the redirect."""

import re
import secrets
from pathlib import Path

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from finances.db.migrate import current_revision, head_revision
from finances.views.format import amount_class

NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"
CSRF_COOKIE = "fin_csrf"
NOTICES = {
    "account-added": "Account added.",
    "account-renamed": "Account renamed.",
    "account-closed": "Account closed.",
    "account-reopened": "Account reopened.",
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
    "category-renamed": "Category renamed.",
    "category-deleted": "Category deleted.",
    "rule-changed": "Rule changed, and the rules were run again.",
    "merchant-merged": "Merchants merged, and the rules were run again.",
    "merchant-unmerged": "Merchant alias removed, and the rules were run again.",
    "category-set": "Category saved.",
    "category-cleared": "Category left to the rules.",
    "bulk-set": "Category set by hand on the chosen transactions.",
    "bulk-cleared": (
        "The chosen transactions were left to the rules, and the rules were run again."
    ),
    "transfers-found": "Clear transfers were paired; the rest wait for review.",
    "transfer-confirmed": "Transfer saved.",
    "transfer-rejected": "Those two will not be paired.",
    "transfer-removed": "Transfer removed; those two will not be paired again.",
    "backed-up": "Backup written.",
    "deleted": "Backup deleted.",
    "restored": (
        "Backup restored. The database it replaced is listed under Set aside before a restore."
    ),
    "restored-old": (
        "Backup restored. It comes from an older version of the app: run fin db upgrade in the"
        " terminal before using the other pages."
    ),
    "budget-set": "Budget saved.",
    "budget-removed": "Budget removed.",
    "proposals-accepted": "Proposals accepted, as your choice.",
    "proposals-declined": "Proposals declined. The agent will not propose them again.",
    "tag-added": "Tag added.",
    "tag-removed": "Tag removed.",
    "note-saved": "Note saved.",
    "note-removed": "Note removed.",
}

_TEMPLATES = Jinja2Templates(directory=Path(__file__).parent / "templates")
_TEMPLATES.env.filters["amount_class"] = amount_class
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")


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
