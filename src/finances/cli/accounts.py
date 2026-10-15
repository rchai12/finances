"""The `fin accounts` commands."""

from dataclasses import astuple
from typing import Annotated

import typer
from rich.table import Table

from finances.cli.common import fail, print_table, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import (
    AccountExistsError,
    create_account,
    get_account_by_name,
    rename_account,
    resolve_owner,
    set_account_active,
    set_account_owner,
)
from finances.domain.models import AccountType
from finances.domain.people import JOINT
from finances.views.accounts import account_rows

app = typer.Typer(help="Manage accounts.", no_args_is_help=True)


@app.command()
def add(
    name: Annotated[str, typer.Option("--name", help="Your label for the account.")],
    institution: Annotated[str, typer.Option("--institution", help="The bank or card issuer.")],
    account_type: Annotated[AccountType, typer.Option("--type", help="The kind of account.")],
    currency: Annotated[str, typer.Option("--currency", help="Three-letter currency.")] = "USD",
    last4: Annotated[
        str | None, typer.Option("--last4", help="Last four digits of the account number.")
    ] = None,
) -> None:
    """Add an account."""
    require_current_schema()

    with session_scope(get_engine()) as session:
        try:
            account = create_account(session, name, institution, account_type, currency, last4)
            typer.echo(f'Added account "{account.name}" (id {account.id})')
        except (AccountExistsError, ValueError) as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(code=1) from None


@app.command("list")
def list_command(
    show_all: Annotated[bool, typer.Option("--all", help="Include inactive accounts.")] = False,
) -> None:
    """List the accounts."""
    require_current_schema()

    with session_scope(get_engine()) as session:
        rows = account_rows(session, include_inactive=show_all)
    if not rows:
        typer.echo("No accounts.")
        return

    table = Table()
    for heading in ("Name", "Institution", "Type", "Last 4", "Active", "Owner"):
        table.add_column(heading)
    for row in rows:
        table.add_row(*astuple(row))
    print_table(table)


@app.command("set-owner")
def set_owner(
    account: Annotated[str, typer.Option("--account", help="Account name.")],
    owner: Annotated[str, typer.Option("--owner", help="A person's name, or joint.")],
) -> None:
    """Set who owns an account: one person, or joint."""
    require_current_schema()

    with session_scope(get_engine()) as session:
        found = get_account_by_name(session, account)
        if found is None:
            fail("account not found")
        try:
            person = resolve_owner(session, owner)
        except ValueError as error:
            fail(str(error))
        set_account_owner(session, found.id, None if person is None else person.id)
        typer.echo(f'Owner of "{found.name}" is {JOINT if person is None else person.name}.')


def _account(session, name: str):
    found = get_account_by_name(session, name)
    if found is None:
        fail("account not found")
    return found


@app.command("rename")
def rename_command(
    account: Annotated[str, typer.Option("--account", help="The account to rename.")],
    to: Annotated[str, typer.Option("--to", help="Its new name.")],
) -> None:
    """Rename an account."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        found = _account(session, account)
        try:
            renamed = rename_account(session, found.id, to)
        except (AccountExistsError, ValueError) as error:
            fail(str(error))
    typer.echo(f'Renamed account "{found.name}" to "{renamed.name}".')


@app.command("deactivate")
def deactivate_command(
    account: Annotated[str, typer.Option("--account", help="The account to close.")],
) -> None:
    """Close an account."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        found = _account(session, account)
        closed = set_account_active(session, found.id, False)
    typer.echo(f'Account "{closed.name}" is closed.')


@app.command("activate")
def activate_command(
    account: Annotated[str, typer.Option("--account", help="The account to reopen.")],
) -> None:
    """Reopen a closed account."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        found = _account(session, account)
        opened = set_account_active(session, found.id, True)
    typer.echo(f'Account "{opened.name}" is open again.')
