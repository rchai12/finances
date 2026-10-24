"""The `fin shared` commands."""

from datetime import datetime
from typing import Annotated

import typer

import finances.clock as clock
from finances.analysis.shared import owed_report
from finances.cli.common import fail, print_rows, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import (
    delete_settlement,
    list_settlements,
    list_shares,
    record_settlement,
    share_transaction,
    unshare_transaction,
)
from finances.domain.money import parse_money
from finances.views.shared import (
    owed_text,
    settlement_rows,
    settlement_text,
    share_rows,
    share_text,
)

shared_app = typer.Typer(help="Shared expenses: who owes whom.", no_args_is_help=True)


def _money(text: str) -> int:
    try:
        return parse_money(text)
    except ValueError as error:
        fail(str(error))


@shared_app.command("add")
def add_command(
    transaction_id: Annotated[int, typer.Option("--id", help="The transaction's id.")],
    with_person: Annotated[str, typer.Option("--with", help="The person who owes a share.")],
    paid_by: Annotated[str, typer.Option("--paid-by", help="Who paid, if not the owner.")] = "",
    share: Annotated[
        str, typer.Option("--share", help="The share as money (half by default).")
    ] = "",
) -> None:
    """Share a transaction: the other person owes a share."""
    require_current_schema()
    size_cents = None if share == "" else _money(share)
    with session_scope(get_engine()) as session:
        try:
            found = share_transaction(
                session, transaction_id, with_person, payer=paid_by, size_cents=size_cents
            )
        except ValueError as error:
            fail(str(error))
    typer.echo(share_text(found))


@shared_app.command("remove")
def remove_command(
    transaction_id: Annotated[int, typer.Option("--id", help="The transaction's id.")],
) -> None:
    """Stop sharing a transaction."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            unshare_transaction(session, transaction_id)
        except ValueError as error:
            fail(str(error))
    typer.echo(f"Transaction {transaction_id}: no longer shared.")


@shared_app.command("list")
def list_command() -> None:
    """List the shared transactions."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        found = list_shares(session)
    if not found:
        typer.echo("No shared transactions.")
        return
    print_rows(("ID", "Paid by", "Owes", "Owed"), share_rows(found))


@shared_app.command("owed")
def owed_command() -> None:
    """Show who owes whom."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        found = owed_report(session)
    if not found:
        typer.echo("Nobody owes anybody.")
        return
    for item in found:
        typer.echo(owed_text(item))


@shared_app.command("settle")
def settle_command(
    payer: Annotated[str, typer.Option("--from", help="Who paid the money back.")],
    payee: Annotated[str, typer.Option("--to", help="Who received it.")],
    amount: Annotated[str, typer.Option("--amount", help="How much, as money.")],
    day: Annotated[
        datetime | None,
        typer.Option("--date", formats=["%Y-%m-%d"], help="The day (today by default)."),
    ] = None,
) -> None:
    """Record that one person paid another."""
    require_current_schema()
    cents = _money(amount)
    when = clock.today() if day is None else day.date()
    with session_scope(get_engine()) as session:
        try:
            found = record_settlement(session, payer, payee, cents, when)
        except ValueError as error:
            fail(str(error))
    typer.echo(settlement_text(found))


@shared_app.command("settlements")
def settlements_command() -> None:
    """List the settlements."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        found = list_settlements(session)
    if not found:
        typer.echo("No settlements.")
        return
    print_rows(("ID", "Date", "From", "To", "Amount"), settlement_rows(found))


@shared_app.command("delete-settlement")
def delete_settlement_command(
    settlement_id: Annotated[int, typer.Option("--id", help="The settlement's id.")],
) -> None:
    """Delete a settlement."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            found = delete_settlement(session, settlement_id)
        except ValueError as error:
            fail(str(error))
    typer.echo(f"Deleted settlement {found.id}: {settlement_text(found)}")
