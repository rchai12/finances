"""The `fin aliases` commands."""

from typing import Annotated

import typer

from finances.cli.categories import categorize_all
from finances.cli.common import fail, print_rows, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import add_alias, delete_alias, list_aliases
from finances.views.categories import alias_rows, categorized_text

aliases_app = typer.Typer(help="Merge one merchant into another.", no_args_is_help=True)


@aliases_app.command("add")
def add_command(
    source: Annotated[str, typer.Option("--from", help="The name to merge.")],
    target: Annotated[str, typer.Option("--to", help="The merchant it joins.")],
) -> None:
    """Merge one merchant into another, then categorize every transaction."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            alias = add_alias(session, source, target)
        except ValueError as error:
            fail(str(error))
    typer.echo(f'Merged "{alias.source}" into "{alias.target}".')
    typer.echo(categorized_text(categorize_all()))


@aliases_app.command("list")
def list_command() -> None:
    """List each merchant and the name it is merged into."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        rows = alias_rows(list_aliases(session))
    if not rows:
        typer.echo("No aliases.")
        return
    print_rows(("From", "To"), rows)


@aliases_app.command("delete")
def delete_command(
    source: Annotated[str, typer.Option("--from", help="The name that was merged.")],
) -> None:
    """Remove an alias, then categorize every transaction."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            alias = delete_alias(session, source)
        except ValueError as error:
            fail(str(error))
    typer.echo(f'Removed the alias for "{alias.source}".')
    typer.echo(categorized_text(categorize_all()))
