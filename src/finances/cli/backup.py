"""The `fin backup` commands."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from finances.cli.common import fail, print_table, require_current_schema
from finances.config import get_settings
from finances.db.backup import check_backup, list_backups, make_backup, restore_backup

app = typer.Typer(add_completion=False, help="Back up the database and restore a backup.")


def _taken(name: str) -> str:
    return datetime.strptime(name, "finances-%Y%m%d-%H%M%S.db").strftime("%Y-%m-%d %H:%M:%S")


@app.command("run")
def run_command() -> None:
    """Copy the database into the backup folder, check it, and keep the newest ones."""
    require_current_schema()
    settings = get_settings()
    try:
        result = make_backup(
            settings.effective_database_url,
            settings.effective_backup_dir,
            settings.backup_keep,
            datetime.now(UTC),
        )
    except ValueError as error:
        fail(str(error))
    typer.echo(
        f"Backup written: {result.path.resolve()} "
        f"({result.check.accounts} accounts, {result.check.transactions} transactions)."
    )
    typer.echo(f"Backups kept: {result.kept}. Removed: {len(result.removed)}.")


@app.command("list")
def list_command() -> None:
    """Show the backups, newest first."""
    backups = list_backups(get_settings().effective_backup_dir)
    if not backups:
        typer.echo("No backups.")
        return
    table = Table()
    table.add_column("File")
    table.add_column("Taken (UTC)")
    for path in backups:
        table.add_row(path.name, _taken(path.name))
    print_table(table)


@app.command("restore")
def restore_command(
    file: Annotated[Path, typer.Argument(help="The backup to put back.")],
    yes: Annotated[bool, typer.Option("--yes", help="Do not ask first.")] = False,
) -> None:
    """Replace the database with a backup, keeping the database it replaces."""
    settings = get_settings()
    try:
        check_backup(file)
    except ValueError as error:
        fail(str(error))
    if not yes and not typer.confirm(f"Replace the database with {file.name}?", default=False):
        typer.echo("Nothing restored.")
        return
    try:
        result = restore_backup(
            settings.effective_database_url,
            file,
            settings.effective_backup_dir,
            datetime.now(UTC),
        )
    except ValueError as error:
        fail(str(error))
    typer.echo(f"Restored {file.name}.")
    if result.replaced is not None:
        typer.echo(f"The database it replaced is kept as {result.replaced.name}.")
    if result.needs_upgrade:
        typer.echo("Run fin db upgrade to bring it up to date.")
