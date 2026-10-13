"""The `fin accounts` commands."""

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from finances.db.engine import get_engine, session_scope
from finances.db.migrate import current_revision, head_revision
from finances.db.repositories import AccountExistsError, create_account, list_accounts
from finances.domain.models import AccountType

app = typer.Typer(help="Manage accounts.", no_args_is_help=True)
console = Console()


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
    # First check database is up to date
    current = current_revision()
    head = head_revision()
    if current != head:
        typer.echo("Error: database is not up to date (run: fin db upgrade)", err=True)
        raise typer.Exit(code=1) from None

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
    # First check database is up to date
    current = current_revision()
    head = head_revision()
    if current != head:
        typer.echo("Error: database is not up to date (run: fin db upgrade)", err=True)
        raise typer.Exit(code=1)

    with session_scope(get_engine()) as session:
        accounts = list_accounts(session, include_inactive=show_all)
        if not accounts:
            typer.echo("No accounts.")
            return

        table = Table()
        table.add_column("Name")
        table.add_column("Institution")
        table.add_column("Type")
        table.add_column("Last 4")
        table.add_column("Active")

        for account in accounts:
            last4 = f"\u2022\u2022{account.last4}" if account.last4 else ""
            active = "yes" if account.is_active else "no"
            table.add_row(account.name, account.institution, account.type.value, last4, active)
        console.print(table)
