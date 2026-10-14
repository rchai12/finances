"""The `fin accounts` commands."""

from typing import Annotated, NoReturn

import typer
from rich.table import Table

from finances.analysis.people import JOINT_FILTER, load_attribution
from finances.cli.common import print_table, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import (
    AccountExistsError,
    create_account,
    get_account_by_name,
    get_person_by_name,
    list_accounts,
    set_account_owner,
)
from finances.domain.models import AccountType
from finances.domain.people import JOINT

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
        table.add_column("Owner")

        attribution = load_attribution(session)
        for account in accounts:
            last4 = f"\u2022\u2022{account.last4}" if account.last4 else ""
            active = "yes" if account.is_active else "no"
            owner = attribution.owner(account.id) or ""
            table.add_row(
                account.name, account.institution, account.type.value, last4, active, owner
            )
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
            _fail("account not found")
        if owner.strip().lower() == JOINT_FILTER:
            person_id, label = None, JOINT
        else:
            person = get_person_by_name(session, owner)
            if person is None:
                _fail("person not found")
            person_id, label = person.id, person.name
        set_account_owner(session, found.id, person_id)
        typer.echo(f'Owner of "{found.name}" is {label}.')


def _fail(message: str) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1) from None
