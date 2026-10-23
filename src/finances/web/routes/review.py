"""The Review page: the agent's proposals and notes, and a person's decisions."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from finances.analysis.review import review_items
from finances.categorize.service import accept_proposals
from finances.db.repositories import decline_proposal, list_advice
from finances.views.review import advice_rows, review_rows
from finances.web.access import _reading
from finances.web.forms import refused
from finances.web.helpers import _WHOLE
from finances.web.render import _done, _not_migrated, _render

router = APIRouter()
NONE_CHOSEN = "choose at least one proposal"
_DECISIONS = {"accept", "decline"}


def _page(request: Request, *, error: str | None = None, status_code: int = 200) -> Response:
    with _reading() as session:
        context = {
            "rows": review_rows(review_items(session)),
            "notes": advice_rows(list_advice(session, limit=20)),
            "error": error,
        }
    return _render(request, "review", context, status_code)


@router.get("/review")
def review(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    return _page(request)


@router.post("/review")
async def decide(request: Request) -> Response:
    form = await request.form()
    csrf = str(form.get("csrf") or "")
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    decision = str(form.get("decision") or "")
    chosen = [str(value) for value in form.getlist("id")]
    bad_id = any(_WHOLE.fullmatch(text) is None for text in chosen)
    if decision not in _DECISIONS or not chosen or bad_id:
        return _page(request, error=NONE_CHOSEN, status_code=400)
    ids = [int(text) for text in chosen]
    try:
        with _reading() as session:
            if decision == "accept":
                accept_proposals(session, ids)
            else:
                for proposal_id in ids:
                    decline_proposal(session, proposal_id)
    except ValueError as error:
        return _page(request, error=str(error), status_code=400)
    notice = "proposals-accepted" if decision == "accept" else "proposals-declined"
    return _done(f"/review?notice={notice}")
