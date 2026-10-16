"""Checks shared by every command that reads the database."""

from collections.abc import Iterable, Sequence
from dataclasses import astuple
from typing import NoReturn

import typer
from rich.console import Console
from rich.table import Table

from finances.db.migrate import current_revision, head_revision

_PLAIN_WIDTH = 1_000_000


def fail(message: str) -> NoReturn:
    """Print the error and end the command with exit code 1."""
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1) from None


def require_current_schema() -> None:
    """Exit when the database has not been migrated to the newest revision."""
    if current_revision() != head_revision():
        typer.echo("Error: database is not up to date (run: fin db upgrade)", err=True)
        raise typer.Exit(code=1) from None


def print_rows(headings: Sequence[str], rows: Iterable[object]) -> None:
    """Print a table of dataclass rows under the given headings."""
    table = Table()
    for heading in headings:
        table.add_column(heading)
    for row in rows:
        table.add_row(*astuple(row))
    print_table(table)


def print_table(table: Table, console: Console | None = None) -> None:
    """Print a table: fitted to the terminal when there is one, each row on one line otherwise."""
    if console is None:
        console = Console()
    if console.is_terminal and not console.is_dumb_terminal:
        console.print(table)
        return
    plain = Console(
        file=console.file,
        width=_PLAIN_WIDTH,
        height=25,
        force_terminal=False,
        color_system=None,
        _environ={},
    )
    plain.print(table, width=plain.measure(table).maximum)
