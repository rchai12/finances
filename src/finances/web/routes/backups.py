"""The Backups pages and forms."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import Response

from finances.analysis.backups import backup_file, backup_files
from finances.config import get_settings
from finances.db.backup import (
    BackupCheck,
    check_backup,
    delete_backup,
    find_backup,
    list_backups,
    list_set_asides,
    make_backup,
    restore_backup,
)
from finances.views.backups import backup_rows, taken_text
from finances.web import app as web_app
from finances.web.forms import _Field, forged, refused
from finances.web.render import _done, _render

router = APIRouter()
_CONFIRM_NAME = "type the backup's name to confirm"


def _backups_page(request: Request, error: str | None = None, status_code: int = 200) -> Response:
    settings = get_settings()
    folder = settings.effective_backup_dir
    context = {
        "folder": str(folder.resolve()),
        "keep": settings.backup_keep,
        "backups": backup_rows(backup_files(list_backups(folder))),
        "set_asides": backup_rows(backup_files(list_set_asides(folder))),
        "error": error,
    }
    return _render(request, "backups", context, status_code)


def _backup_confirm(
    request: Request,
    action: str,
    path: Path,
    check: BackupCheck | None = None,
    error: str | None = None,
) -> Response:
    context = {
        "action": action,
        "name": path.name,
        "taken": taken_text(backup_file(path).taken),
        "check": check,
        "error": error,
    }
    return _render(request, "backup_confirm", context, 200 if error is None else 400)


@router.get("/backups")
def backups(request: Request) -> Response:
    return _backups_page(request)


@router.post("/backups/run")
def back_up(request: Request, csrf: _Field = "") -> Response:
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    settings = get_settings()
    try:
        make_backup(
            settings.effective_database_url,
            settings.effective_backup_dir,
            settings.backup_keep,
            web_app._now(),
        )
    except ValueError as error:
        return _backups_page(request, str(error), 400)
    return _done("/backups?notice=backed-up")


@router.get("/backups/delete")
def delete_confirm(request: Request) -> Response:
    name = request.query_params.get("name", "")
    try:
        path = find_backup(get_settings().effective_backup_dir, name)
    except ValueError as error:
        return _backups_page(request, str(error), 400)
    return _backup_confirm(request, "delete", path)


@router.post("/backups/delete")
def delete(request: Request, csrf: _Field = "", name: _Field = "") -> Response:
    stopped = forged(request, csrf)
    if stopped is not None:
        return stopped
    try:
        delete_backup(get_settings().effective_backup_dir, name)
    except ValueError as error:
        return _backups_page(request, str(error), 400)
    return _done("/backups?notice=deleted")


@router.get("/backups/restore")
def restore_confirm(request: Request) -> Response:
    name = request.query_params.get("name", "")
    try:
        path = find_backup(get_settings().effective_backup_dir, name)
        check = check_backup(path)
    except ValueError as error:
        return _backups_page(request, str(error), 400)
    return _backup_confirm(request, "restore", path, check)


@router.post("/backups/restore")
def restore(
    request: Request, csrf: _Field = "", name: _Field = "", confirm: _Field = ""
) -> Response:
    stopped = forged(request, csrf)
    if stopped is not None:
        return stopped
    settings = get_settings()
    folder = settings.effective_backup_dir
    try:
        path = find_backup(folder, name)
        check = check_backup(path)
    except ValueError as error:
        return _backups_page(request, str(error), 400)
    if confirm != name:
        return _backup_confirm(request, "restore", path, check, _CONFIRM_NAME)
    try:
        with web_app._RESTORE_GATE:
            result = restore_backup(settings.effective_database_url, path, folder, web_app._now())
    except ValueError as error:
        return _backups_page(request, str(error), 400)
    if result.needs_upgrade:
        return _done("/backups?notice=restored-old")
    return _done("/backups?notice=restored")
