"""The Statements page and the upload form."""

from fastapi import APIRouter, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from finances.analysis.statements import statement_gap_lines
from finances.categorize.service import categorize
from finances.categorize.transfers import pair_transfers
from finances.db.repositories import account_names, list_accounts, list_statements
from finances.ingest.service import ImportStatus, StatementImportResult, import_statement
from finances.views.statements import gap_rows, import_rows, statement_rows
from finances.web import app as web_app
from finances.web.access import _reading
from finances.web.forms import refused
from finances.web.render import _not_migrated, _render

router = APIRouter()
UPLOAD_LIMIT = 20 * 1024 * 1024


def _statements_page(
    request: Request,
    *,
    chosen_account: str = "",
    dry_run: bool = False,
    result: list[tuple[str, str]] | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> Response:
    with _reading() as session:
        accounts = [account.name for account in list_accounts(session)]
        names = account_names(session)
        statements = statement_rows(list_statements(session), names)
        gaps = gap_rows(statement_gap_lines(session))
    context = {
        "accounts": accounts,
        "chosen_account": chosen_account,
        "dry_run": dry_run,
        "result": result,
        "statements": statements,
        "gaps": gaps,
        "error": error,
    }
    return _render(request, "statements", context, status_code)


@router.get("/statements")
def statements(request: Request) -> Response:
    stopped = _not_migrated(request)
    if stopped is not None:
        return stopped
    return _statements_page(request)


@router.post("/statements/upload")
async def upload_statement(request: Request) -> Response:
    form = await request.form()
    csrf = str(form.get("csrf") or "")
    stopped = refused(request, csrf)
    if stopped is not None:
        return stopped
    account = str(form.get("account") or "")
    dry_run = form.get("dry_run") == "yes"
    uploaded = form.get("file")

    def refuse(message: str) -> Response:
        return _statements_page(
            request,
            chosen_account=account,
            dry_run=dry_run,
            error=message,
            status_code=400,
        )

    if not isinstance(uploaded, UploadFile):
        return refuse("choose a PDF statement")
    content = uploaded.file.read(UPLOAD_LIMIT + 1)
    if not content:
        return refuse("choose a PDF statement")
    if len(content) > UPLOAD_LIMIT:
        return refuse("a statement must be at most 20 MB")
    if not content.startswith(b"%PDF-"):
        return refuse("the file is not a PDF")
    stored = web_app._upload_name(uploaded.filename or "")
    if not stored:
        return refuse("choose a PDF statement")

    def run_import() -> StatementImportResult:
        with _reading() as session:
            return import_statement(
                session,
                filename=stored,
                content=content,
                account_name=account or None,
                dry_run=dry_run,
            )

    answer = await run_in_threadpool(run_import)
    if answer.status is ImportStatus.FAILED:
        return refuse(answer.message)
    if answer.status is ImportStatus.IMPORTED:

        def after() -> None:
            with _reading() as session:
                categorize(session)
                pair_transfers(session)

        await run_in_threadpool(after)
    return _statements_page(
        request,
        chosen_account=account,
        dry_run=dry_run,
        result=import_rows(answer),
    )
