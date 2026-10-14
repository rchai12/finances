"""The `fin people` commands."""

from dataclasses import astuple
from typing import Annotated, NoReturn

import typer
from rich.table import Table

from finances.cli.common import print_table, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import (
    PersonExistsError,
    create_person,
    get_person_by_name,
    set_cardholder_alias,
)
from finances.views.people import people_rows

app = typer.Typer(help="Manage the household's people.", no_args_is_help=True)


@app.command()
def add(name: Annotated[str, typer.Option("--name", help="The person's name.")]) -> None:
    """Add a person."""
    require_current_schema()

    with session_scope(get_engine()) as session:
        try:
            person = create_person(session, name)
        except (PersonExistsError, ValueError) as error:
            _fail(str(error))
        typer.echo(f'Added person "{person.name}" (id {person.id})')


@app.command("list")
def list_command() -> None:
    """List the people, the accounts each owns, and their cardholder names."""
    require_current_schema()

    with session_scope(get_engine()) as session:
        rows = people_rows(session)
    if not rows:
        typer.echo("No people.")
        return
    table = Table()
    for heading in ("Name", "Owns", "Cardholder names"):
        table.add_column(heading)
    for row in rows:
        table.add_row(*astuple(row))
    print_table(table)


@app.command()
def alias(
    person: Annotated[str, typer.Option("--person", help="The person's name.")],
    cardholder: Annotated[
        str, typer.Option("--cardholder", help="The cardholder name a statement prints.")
    ],
) -> None:
    """Tie a statement's cardholder name to a person."""
    require_current_schema()

    with session_scope(get_engine()) as session:
        found = get_person_by_name(session, person)
        if found is None:
            _fail("person not found")
        try:
            stored = set_cardholder_alias(session, cardholder, found.id)
        except ValueError as error:
            _fail(str(error))
        typer.echo(f'Cardholder "{stored}" is {found.name}.')


def _fail(message: str) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1) from None
