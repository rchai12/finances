from fastapi import APIRouter, Request
from fastapi.responses import Response

from finances.db.repositories import list_changes
from finances.domain.audit import ACTIONS
from finances.views.audit import change_link, change_rows
from finances.web.access import _reading
from finances.web.helpers import _day
from finances.web.render import _not_migrated, _render

router = APIRouter()
HISTORY_LIMIT = 200
ACTION_REFUSED = "choose an action from the list"


@router.get("/history")
def history(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    action = request.query_params.get("action", "")
    since_text = request.query_params.get("since", "")
    if action and action not in ACTIONS:
        return _render(request, "error", {"message": ACTION_REFUSED}, 400)
    try:
        since = _day(since_text, "since")
    except ValueError as error:
        return _render(request, "error", {"message": str(error)}, 400)
    with _reading() as session:
        changes = list_changes(session, since=since, action=action or None, limit=HISTORY_LIMIT)
    rows = list(zip(change_rows(changes), (change_link(item) for item in changes), strict=True))
    return _render(
        request,
        "history",
        {
            "rows": rows,
            "form": {"action": action, "since": since_text},
            "actions": ACTIONS,
            "limit": HISTORY_LIMIT,
        },
    )
