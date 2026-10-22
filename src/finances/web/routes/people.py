"""The People page and its forms."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from finances.analysis.listings import people_listing
from finances.db.repositories import create_person, get_person_by_name, set_cardholder_alias
from finances.views.people import people_rows
from finances.web.access import _reading
from finances.web.forms import _REFUSALS, _Field, refused
from finances.web.render import _done, _not_migrated, _render

router = APIRouter()


def _people_page(request: Request, *, error: str | None = None, status_code: int = 200) -> Response:
    with _reading() as session:
        rows = people_rows(people_listing(session))
    context = {"rows": rows, "people": [row.name for row in rows], "error": error}
    return _render(request, "people", context, status_code)


@router.get("/people")
def people(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    return _people_page(request)


@router.post("/people/add")
def add_person(request: Request, csrf: _Field = "", name: _Field = "") -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    try:
        with _reading() as session:
            create_person(session, name)
    except _REFUSALS as error:
        return _people_page(request, error=str(error), status_code=400)
    return _done("/people?notice=person-added")


@router.post("/people/alias")
def add_alias(
    request: Request, csrf: _Field = "", person: _Field = "", cardholder: _Field = ""
) -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    try:
        with _reading() as session:
            found = get_person_by_name(session, person)
            if found is None:
                raise ValueError("person not found")
            set_cardholder_alias(session, cardholder, found.id)
    except _REFUSALS as error:
        return _people_page(request, error=str(error), status_code=400)
    return _done("/people?notice=alias-set")
