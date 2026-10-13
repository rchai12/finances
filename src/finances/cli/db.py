"""The `fin db` commands."""

import typer

from finances.db.migrate import upgrade_to_head

app = typer.Typer(help="Manage the database schema.", no_args_is_help=True)


@app.command()
def upgrade() -> None:
    """Apply every pending migration."""
    try:
        revision = upgrade_to_head()
        typer.echo(f"Database is at revision {revision}")
    except ValueError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from None
