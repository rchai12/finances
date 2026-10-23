"""The `fin audit` command."""

from datetime import datetime
from typing import Annotated

import typer

from finances.cli.common import fail, print_rows, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import list_changes
from finances.domain.audit import ACTIONS
from finances.views.audit import change_rows


def audit_command(
    since: Annotated[
        datetime | None,
        typer.Option("--since", formats=["%Y-%m-%d"], help="Only changes on or after this day."),
    ] = None,
    action: Annotated[
        str | None, typer.Option("--action", help="Only this kind of change.")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=1000, help="Maximum rows.")] = 50,
) -> None:
    """List the changes a person made to the household's data, newest first."""
    if action is not None and action not in ACTIONS:
        fail("action must be one of: " + ", ".join(ACTIONS))
    require_current_schema()
    with session_scope(get_engine()) as session:
        found = list_changes(
            session,
            since=None if since is None else since.date(),
            action=action,
            limit=limit,
        )
    if not found:
        typer.echo("No changes recorded.")
        return
    print_rows(("When (UTC)", "Who", "Action", "Record", "Before", "After"), change_rows(found))
