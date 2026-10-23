"""The `fin transfers` commands: money moved between the household's own accounts."""

from typing import Annotated

import typer

from finances.analysis.transfers import pair_listing, suggestion_listing
from finances.categorize.transfers import pair_transfers
from finances.cli.common import fail, print_rows, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import create_transfer_pair, reject_transfer, unpair_transfer
from finances.domain.models import CONFIRMED
from finances.views.transfers import suggestion_lines, transfer_lines

transfers_app = typer.Typer(help="Money moved between your own accounts.", no_args_is_help=True)

_OUT = typer.Option("--out", help="The outflow's transaction id.")
_IN = typer.Option("--in", help="The inflow's transaction id.")


@transfers_app.command("list")
def list_command() -> None:
    """List the transfers, latest first."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        lines = transfer_lines(pair_listing(session))
    if not lines:
        typer.echo("No transfers.")
        return
    print_rows(("Pair", "Date", "From", "To", "Amount", "Out", "In", "How"), lines)


@transfers_app.command("review")
def review_command() -> None:
    """List the possible transfers that wait for a decision."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        lines = suggestion_lines(suggestion_listing(session))
    if not lines:
        typer.echo("No transfers wait for review.")
        return
    print_rows(("Out", "Out date", "From", "In", "In date", "To", "Amount"), lines)


@transfers_app.command("find")
def find_command() -> None:
    """Pair the clear transfers and count the ones waiting for review."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        result = pair_transfers(session)
    typer.echo(f"Transfers: {result.paired} paired, {result.waiting} waiting for review.")


@transfers_app.command("confirm")
def confirm_command(
    out_id: Annotated[int, _OUT],
    in_id: Annotated[int, _IN],
) -> None:
    """Pair an outflow and an inflow as one transfer."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            create_transfer_pair(session, out_id, in_id, CONFIRMED)
        except ValueError as error:
            fail(str(error))
    typer.echo(f"Transactions {out_id} and {in_id} are now a transfer.")


@transfers_app.command("reject")
def reject_command(
    out_id: Annotated[int, _OUT],
    in_id: Annotated[int, _IN],
) -> None:
    """Record that an outflow and an inflow are not a transfer."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            reject_transfer(session, out_id, in_id)
        except ValueError as error:
            fail(str(error))
    typer.echo(f"Transactions {out_id} and {in_id} will not be paired.")


@transfers_app.command("unpair")
def unpair_command(
    pair_id: Annotated[int, typer.Option("--pair", help="The pair's id (see fin transfers list).")],
) -> None:
    """Remove a transfer, so its two transactions are never paired again."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            pair = unpair_transfer(session, pair_id)
        except ValueError as error:
            fail(str(error))
    typer.echo(
        f"Transfer {pair_id} removed; transactions {pair.out_transaction_id} and "
        f"{pair.in_transaction_id} will not be paired again."
    )
