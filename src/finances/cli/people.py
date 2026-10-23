"""The `fin people` commands."""

from typing import Annotated

import typer

from finances.analysis.listings import people_listing
from finances.cli.common import fail, print_rows, require_current_schema
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
            fail(str(error))
        typer.echo(f'Added person "{person.name}" (id {person.id})')


@app.command("list")
def list_command() -> None:
    """List the people, the accounts each owns, and their cardholder names."""
    require_current_schema()

    with session_scope(get_engine()) as session:
        rows = people_rows(people_listing(session))
    if not rows:
        typer.echo("No people.")
        return
    print_rows(("Name", "Owns", "Cardholder names"), rows)


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
            fail("person not found")
        try:
            stored = set_cardholder_alias(session, cardholder, found.id)
        except ValueError as error:
            fail(str(error))
        typer.echo(f'Cardholder "{stored}" is {found.name}.')
