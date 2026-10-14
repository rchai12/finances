import logging
from typing import Annotated

import typer
from rich.table import Table

from finances import __version__
from finances.cli.accounts import app as accounts_app
from finances.cli.common import print_table
from finances.cli.db import app as db_app
from finances.cli.importing import app as import_app
from finances.cli.listing import statements_app, transactions_app
from finances.cli.people import app as people_app
from finances.cli.sync import app as sync_app
from finances.cli.web import app as web_app
from finances.config import get_settings
from finances.diagnostics import run_checks
from finances.log import setup_logging

app = typer.Typer(add_completion=False)
app.add_typer(db_app, name="db")
app.add_typer(accounts_app, name="accounts")
app.add_typer(import_app, name="import")
app.add_typer(statements_app, name="statements")
app.add_typer(transactions_app, name="transactions")
app.add_typer(sync_app, name="sync")
app.add_typer(people_app, name="people")
app.add_typer(web_app, name="web")


@app.callback(invoke_without_command=True)
def main(
    version: Annotated[
        bool,
        typer.Option("--version", help="Show the version and exit."),
    ] = False,
) -> None:
    setup_logging(get_settings().log_level)
    logging.getLogger("alembic").setLevel(logging.WARNING)
    if version:
        typer.echo(f"finances {__version__}")
        raise typer.Exit()


@app.command()
def doctor() -> None:
    checks = run_checks(get_settings())
    table = Table()
    table.add_column("Check")
    table.add_column("Result")
    for name, _ok, detail in checks:
        table.add_row(name, detail)
    print_table(table)
    if any(not ok for _name, ok, _detail in checks):
        raise typer.Exit(code=1)
