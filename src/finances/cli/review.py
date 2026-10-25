"""The `fin review` commands: a person accepts or declines the agent's proposals."""

from typing import Annotated

import typer

from finances.analysis.review import review_items
from finances.categorize.service import accept_proposals
from finances.cli.common import fail, print_rows, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import decline_proposals
from finances.views.categories import categorized_text
from finances.views.review import accepted_text, declined_text, review_rows

app = typer.Typer(help="Review the agent's proposals.", no_args_is_help=True)

_HEADINGS = (
    "ID",
    "Date",
    "Account",
    "Description",
    "Amount",
    "Now",
    "Proposed",
    "Reason",
    "State",
)


@app.command("list")
def list_command(
    limit: Annotated[int, typer.Option("--limit", min=1, max=500, help="Maximum rows.")] = 50,
) -> None:
    """List the open proposals, newest first."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        rows = review_rows(review_items(session, limit=limit))
    if not rows:
        typer.echo("No open proposals.")
        return
    print_rows(_HEADINGS, rows)


@app.command("accept")
def accept_command(
    proposal_ids: Annotated[
        list[int],
        typer.Option("--id", help="The proposal's id; may be given several times."),
    ],
) -> None:
    """Do what the proposal says, as the person's choice."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            found = accept_proposals(session, proposal_ids)
        except ValueError as error:
            fail(str(error))
    for proposal in found.proposals:
        typer.echo(accepted_text(proposal))
    if found.categorized is not None:
        typer.echo(categorized_text(found.categorized))


@app.command("decline")
def decline_command(
    proposal_ids: Annotated[
        list[int],
        typer.Option("--id", help="The proposal's id; may be given several times."),
    ],
) -> None:
    """Leave the transaction as it is and stop this proposal being made again."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            found = decline_proposals(session, proposal_ids)
        except ValueError as error:
            fail(str(error))
    for proposal, waited in found:
        typer.echo(declined_text(proposal, waited=waited))
