"""The `fin health` command."""

from dataclasses import astuple
from datetime import datetime
from typing import Annotated

import typer
from rich.table import Table

from finances import clock
from finances.analysis.health import gather_health
from finances.cli.common import print_table, require_current_schema
from finances.config import get_settings
from finances.db.engine import get_engine, session_scope
from finances.views.health import health_rows, health_summary


def health_command(
    as_of: Annotated[
        datetime | None,
        typer.Option(
            "--as-of", formats=["%Y-%m-%d"], help="The day to judge from (today by default)."
        ),
    ] = None,
) -> None:
    """List when the household's data is out of date or incomplete."""
    require_current_schema()
    day = clock.today() if as_of is None else as_of.date()
    settings = get_settings()
    with session_scope(get_engine()) as session:
        problems = gather_health(session, settings.effective_backup_dir, day)
    rows = health_rows(problems)
    if rows:
        table = Table()
        for heading in ("Kind", "Account", "Problem", "What to do"):
            table.add_column(heading)
        for row in rows:
            table.add_row(*astuple(row))
        print_table(table)
    typer.echo(health_summary(problems))
