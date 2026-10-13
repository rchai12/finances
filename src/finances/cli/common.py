"""Checks shared by every command that reads the database."""

import typer

from finances.db.migrate import current_revision, head_revision


def require_current_schema() -> None:
    """Exit when the database has not been migrated to the newest revision."""
    if current_revision() != head_revision():
        typer.echo("Error: database is not up to date (run: fin db upgrade)", err=True)
        raise typer.Exit(code=1) from None
