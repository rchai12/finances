"""The Categories page, its forms, and the rules."""

import re

from fastapi import APIRouter, Request
from fastapi.responses import Response

from finances.analysis.categories import (
    card_credit_count,
    category_tree,
    rule_listing,
    uncategorized_items,
)
from finances.analysis.review import open_suggestions
from finances.categorize.service import categorize
from finances.db.repositories import (
    create_category,
    create_rule,
    delete_category,
    delete_rule,
    edit_rule,
    list_categories,
    list_rules,
    rename_category,
)
from finances.domain.rules import MATCHES
from finances.views.categories import (
    card_credits_note,
    category_choices,
    category_lines,
    rule_lines,
    uncategorized_lines,
)
from finances.web.access import _reading
from finances.web.forms import _REFUSALS, _Field, refused
from finances.web.helpers import _WHOLE, _id, _rule_form
from finances.web.render import _done, _not_migrated, _render

router = APIRouter()
_UNCATEGORIZED_LIMIT = 50
_PRIORITY = re.compile(r"-?[0-9]{1,6}")


def _priority(text: str) -> int:
    if not text:
        return 0
    if _PRIORITY.fullmatch(text) is None:
        raise ValueError("priority must be a whole number")
    return int(text)


def _categories_page(
    request: Request,
    *,
    rule_form: dict[str, str] | None = None,
    category_form: dict[str, str] | None = None,
    rename_form: dict[str, str] | None = None,
    delete_form: dict[str, str] | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> Response:
    with _reading() as session:
        tree = category_tree(session)
        items = uncategorized_items(session, _UNCATEGORIZED_LIMIT)
        choices = category_choices(tree)
        context = {
            "uncategorized": uncategorized_lines(items),
            "suggestions": {str(key): value for key, value in open_suggestions(session).items()},
            "card_note": card_credits_note(card_credit_count(items)),
            "limit": _UNCATEGORIZED_LIMIT,
            "rules": rule_lines(rule_listing(session)),
            "matches": MATCHES,
            "choices": choices,
            "rule_form": rule_form if rule_form is not None else _rule_form(),
            "tree": category_lines(tree),
            "groups": [group for group, _ in choices],
            "category_form": category_form or {"name": "", "group": ""},
            "rename_form": rename_form or {"name": "", "to": ""},
            "delete_form": delete_form or {"name": "", "move_to": ""},
            "error": error,
        }
    return _render(request, "categories", context, status_code)


def _rule_edit_page(
    request: Request,
    rule_id: int,
    *,
    rule_form: dict[str, str] | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> Response:
    with _reading() as session:
        rules = {rule.id: rule for rule in list_rules(session)}
        rule = rules.get(rule_id)
        if rule is None:
            return _render(request, "error", {"message": "rule not found"}, status_code=404)
        names = {item.id: item.name for item in list_categories(session)}
        form = rule_form or _rule_form(
            rule.pattern, rule.match, str(rule.priority), names[rule.category_id]
        )
        context = {
            "rule_id": rule_id,
            "rule_form": form,
            "matches": MATCHES,
            "choices": category_choices(category_tree(session)),
            "error": error,
        }
    return _render(request, "rule_edit", context, status_code)


@router.get("/categories")
def categories(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    return _categories_page(request)


@router.post("/categories/add")
def add_category(
    request: Request, csrf: _Field = "", name: _Field = "", group: _Field = ""
) -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    try:
        with _reading() as session:
            create_category(session, name, group)
    except _REFUSALS as error:
        form = {"name": name, "group": group}
        return _categories_page(request, category_form=form, error=str(error), status_code=400)
    return _done("/categories?notice=category-added")


@router.post("/categories/rules/add")
def add_rule(
    request: Request,
    csrf: _Field = "",
    pattern: _Field = "",
    match: _Field = "",
    priority: _Field = "",
    category: _Field = "",
    back: _Field = "",
) -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    try:
        number = _priority(priority)
        with _reading() as session:
            create_rule(session, pattern, category, match, number)
            categorize(session)
    except _REFUSALS as error:
        form = _rule_form(pattern, match, priority, category)
        return _categories_page(request, rule_form=form, error=str(error), status_code=400)
    if _WHOLE.fullmatch(back) is not None:
        return _done(f"/transactions/{back}?notice=rule-added")
    return _done("/categories?notice=rule-added")


@router.post("/categories/rules/delete")
def remove_rule(request: Request, csrf: _Field = "", rule: _Field = "") -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    try:
        rule_id = _id(rule)
        if rule_id is None:
            raise ValueError("rule not found")
        with _reading() as session:
            delete_rule(session, rule_id)
            categorize(session)
    except _REFUSALS as error:
        return _categories_page(request, error=str(error), status_code=400)
    return _done("/categories?notice=rule-deleted")


@router.post("/categories/rename")
def rename(request: Request, csrf: _Field = "", name: _Field = "", to: _Field = "") -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    try:
        with _reading() as session:
            rename_category(session, name, to)
    except _REFUSALS as error:
        form = {"name": name, "to": to}
        return _categories_page(request, rename_form=form, error=str(error), status_code=400)
    return _done("/categories?notice=category-renamed")


@router.post("/categories/delete")
def remove_category(
    request: Request, csrf: _Field = "", name: _Field = "", move_to: _Field = ""
) -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    try:
        with _reading() as session:
            delete_category(session, name, move_to)
    except _REFUSALS as error:
        form = {"name": name, "move_to": move_to}
        return _categories_page(request, delete_form=form, error=str(error), status_code=400)
    return _done("/categories?notice=category-deleted")


@router.get("/categories/rules/{rule_id}")
def show_rule(request: Request, rule_id: str) -> Response:
    if rule_id in ("add", "delete"):
        return Response(status_code=405)
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    number = _id(rule_id)
    if number is None:
        return _render(request, "error", {"message": "rule not found"}, status_code=404)
    return _rule_edit_page(request, number)


@router.post("/categories/rules/{rule_id}")
def change_rule(
    request: Request,
    rule_id: str,
    csrf: _Field = "",
    pattern: _Field = "",
    match: _Field = "",
    priority: _Field = "",
    category: _Field = "",
) -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    number = _id(rule_id)
    if number is None:
        return _render(request, "error", {"message": "rule not found"}, status_code=404)
    form = _rule_form(pattern, match, priority, category)
    try:
        level = _priority(priority)
        with _reading() as session:
            edit_rule(
                session,
                number,
                pattern=pattern,
                match=match,
                priority=level,
                category=category,
            )
            categorize(session)
    except _REFUSALS as error:
        return _rule_edit_page(request, number, rule_form=form, error=str(error), status_code=400)
    return _done("/categories?notice=rule-changed")
