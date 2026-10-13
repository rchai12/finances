"""The `fin import` commands."""

from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from finances.cli.common import print_table, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.ingest.service import (
    ImportStatus,
    StatementImportResult,
    import_folder,
    import_statement,
)

app = typer.Typer(help="Import statements.", no_args_is_help=True)

_STATUS = {
    ImportStatus.IMPORTED: "imported",
    ImportStatus.DRY_RUN: "dry run, nothing written",
    ImportStatus.ALREADY_IMPORTED: "already imported",
    ImportStatus.FAILED: "failed",
}
_FOLDER_HEADINGS = (
    "File",
    "Parser",
    "Account",
    "Period",
    "Lines",
    "Inserted",
    "Duplicates",
    "Status",
)


@app.command()
def statement(
    path: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=True, dir_okay=False, metavar="PATH"),
    ],
    account: Annotated[str | None, typer.Option("--account", help="Account name.")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Do not write anything.")] = False,
) -> None:
    """Import one PDF statement."""
    require_current_schema()
    content = path.read_bytes()
    with session_scope(get_engine()) as session:
        result = import_statement(
            session,
            filename=str(path),
            content=content,
            account_name=account,
            dry_run=dry_run,
        )
    _report_statement(result)


@app.command()
def folder(
    directory: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=False, dir_okay=True, metavar="DIR"),
    ],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Do not write anything.")] = False,
) -> None:
    """Import every PDF in a folder."""
    require_current_schema()
    results = import_folder(get_engine(), directory, dry_run=dry_run)
    if not results:
        typer.echo("No PDF files.")
        return
    table = Table()
    for heading in _FOLDER_HEADINGS:
        table.add_column(heading)
    for result in results:
        table.add_row(*_folder_cells(result))
    print_table(table)
    failed = False
    for result in results:
        if result.status is ImportStatus.FAILED:
            failed = True
            typer.echo(f"Error: {result.filename}: {result.message}", err=True)
    if failed:
        raise typer.Exit(code=1) from None


def _report_statement(result: StatementImportResult) -> None:
    if result.status is ImportStatus.FAILED:
        typer.echo(f"Error: {result.message}", err=True)
        raise typer.Exit(code=1) from None
    if result.status is ImportStatus.ALREADY_IMPORTED:
        typer.echo(f"File: {result.filename}")
        typer.echo("Status: already imported")
        return
    typer.echo(f"File: {result.filename}")
    typer.echo(f"Parser: {result.parser_name}")
    typer.echo(f"Account: {result.account_name}")
    typer.echo(f"Period: {result.period_start} to {result.period_end}")
    typer.echo(f"Lines: {result.lines_parsed}")
    typer.echo(f"Inserted: {result.inserted}")
    typer.echo(f"Duplicates: {result.duplicates}")
    typer.echo(f"Status: {_STATUS[result.status]}")


def _folder_cells(result: StatementImportResult) -> tuple[str, ...]:
    return (
        result.filename,
        result.parser_name or "",
        result.account_name or "",
        _period(result),
        str(result.lines_parsed),
        str(result.inserted),
        str(result.duplicates),
        _STATUS[result.status],
    )


def _period(result: StatementImportResult) -> str:
    if result.period_start is None or result.period_end is None:
        return ""
    return f"{result.period_start.isoformat()} to {result.period_end.isoformat()}"
