"""The `fin findings` commands."""

from datetime import date
from typing import Annotated

import typer

from finances.analysis.insights import find_finding
from finances.cli.common import fail, require_current_schema
from finances.cli.reports import _MONTH_OPTION, _first_day
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import reopen_finding, set_finding_status
from finances.domain.findings import HANDLED, IGNORED, finding_text

app = typer.Typer(help="Mark a finding handled or ignored, or reopen it.", no_args_is_help=True)

_TYPE = typer.Option("--type", help="The finding's type.")
_ABOUT = typer.Option("--about", help="What the finding is about (empty when it has none).")


def _month(month: str | None) -> date:
    require_current_schema()
    return _first_day(month)


@app.command("handle")
def handle_command(
    finding_type: Annotated[str, _TYPE],
    about: Annotated[str, _ABOUT] = "",
    month: Annotated[str | None, _MONTH_OPTION] = None,
) -> None:
    """Mark a finding handled for that month only."""
    first = _month(month)
    with session_scope(get_engine()) as session:
        try:
            found = find_finding(session, first, finding_type, about)
            stored = set_finding_status(session, found, HANDLED)
        except ValueError as error:
            fail(str(error))
    typer.echo(f"Marked handled: {finding_text(stored.type, stored.subject, stored.month)}.")


@app.command("ignore")
def ignore_command(
    finding_type: Annotated[str, _TYPE],
    about: Annotated[str, _ABOUT] = "",
    month: Annotated[str | None, _MONTH_OPTION] = None,
) -> None:
    """Ignore a finding's type and subject in every month."""
    first = _month(month)
    with session_scope(get_engine()) as session:
        try:
            found = find_finding(session, first, finding_type, about)
            stored = set_finding_status(session, found, IGNORED)
        except ValueError as error:
            fail(str(error))
    typer.echo(f"Ignoring: {finding_text(stored.type, stored.subject, stored.month)}.")


@app.command("reopen")
def reopen_command(
    finding_type: Annotated[str, _TYPE],
    about: Annotated[str, _ABOUT] = "",
    month: Annotated[str | None, _MONTH_OPTION] = None,
) -> None:
    """Clear a handled or ignored status so the finding is open again."""
    first = _month(month)
    with session_scope(get_engine()) as session:
        try:
            find_finding(session, first, finding_type, about)
            reopen_finding(session, finding_type, about, first)
        except ValueError as error:
            fail(str(error))
    typer.echo(f"Reopened: {finding_text(finding_type, about.strip(), first)}.")
