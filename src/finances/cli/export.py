"""The `fin export` commands: CSV files a spreadsheet can open."""

from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer

from finances import clock
from finances.analysis.export import transactions_for_export
from finances.analysis.spending import spending_report
from finances.analysis.yearend import year_report
from finances.cli.common import fail, require_current_schema
from finances.cli.reports import _range
from finances.config import get_settings
from finances.db.engine import get_engine, session_scope
from finances.export.files import write_csv
from finances.views.export import spending_csv, transactions_csv, year_csv

export_app = typer.Typer(
    help="Write CSV files a spreadsheet can open.",
    no_args_is_help=True,
)


def _folder(folder: Path | None) -> Path:
    return get_settings().effective_export_dir if folder is None else folder


def _write(folder: Path | None, name: str, text: str, rows: int, force: bool) -> None:
    try:
        path = write_csv(_folder(folder), name, text, force=force)
    except ValueError as error:
        fail(str(error))
    typer.echo(f"Wrote {rows} rows to {path}.")


@export_app.command("transactions")
def transactions_command(
    start: Annotated[
        datetime | None,
        typer.Option("--from", formats=["%Y-%m-%d"], help="First day, YYYY-MM-DD."),
    ] = None,
    end: Annotated[
        datetime | None,
        typer.Option("--to", formats=["%Y-%m-%d"], help="Last day, YYYY-MM-DD."),
    ] = None,
    folder: Annotated[
        Path | None,
        typer.Option("--folder", help="Folder for the file (the export folder by default)."),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Replace a file that is already there.")
    ] = False,
) -> None:
    """Write every transaction in a date range (this year by default)."""
    require_current_schema()
    today = clock.today()
    first = date(today.year, 1, 1) if start is None else start.date()
    last = date(today.year, 12, 31) if end is None else end.date()
    with session_scope(get_engine()) as session:
        try:
            lines = transactions_for_export(session, first, last)
        except ValueError as error:
            fail(str(error))
    _write(
        folder,
        f"transactions-{first.isoformat()}-to-{last.isoformat()}.csv",
        transactions_csv(lines),
        len(lines),
        force,
    )


@export_app.command("year")
def year_command(
    year: Annotated[int | None, typer.Option("--year", help="A calendar year.")] = None,
    folder: Annotated[
        Path | None,
        typer.Option("--folder", help="Folder for the file (the export folder by default)."),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Replace a file that is already there.")
    ] = False,
) -> None:
    """Write a calendar year's spending, and the tax-relevant categories."""
    require_current_schema()
    chosen = clock.today().year if year is None else year
    with session_scope(get_engine()) as session:
        try:
            report = year_report(session, chosen)
        except ValueError as error:
            fail(str(error))
    _write(
        folder,
        f"year-{chosen}.csv",
        year_csv(report),
        len(report.groups) + len(report.categories) + len(report.tax),
        force,
    )


@export_app.command("spending")
def spending_command(
    month: Annotated[str | None, typer.Option("--month", help="A month, YYYY-MM.")] = None,
    start: Annotated[
        datetime | None,
        typer.Option("--from", formats=["%Y-%m-%d"], help="First day, YYYY-MM-DD."),
    ] = None,
    end: Annotated[
        datetime | None,
        typer.Option("--to", formats=["%Y-%m-%d"], help="Last day, YYYY-MM-DD."),
    ] = None,
    by: Annotated[
        str,
        typer.Option("--by", help="category, group, merchant, person, account, bank, or card."),
    ] = "category",
    folder: Annotated[
        Path | None,
        typer.Option("--folder", help="Folder for the file (the export folder by default)."),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Replace a file that is already there.")
    ] = False,
) -> None:
    """Write spending for a month or range (this month by default), grouped one way."""
    require_current_schema()
    first, last = _range(month, start, end)
    with session_scope(get_engine()) as session:
        try:
            report = spending_report(session, first, last, by)
        except ValueError as error:
            fail(str(error))
    _write(
        folder,
        f"spending-by-{report.by}-{first.isoformat()}-to-{last.isoformat()}.csv",
        spending_csv(report),
        len(report.lines),
        force,
    )
