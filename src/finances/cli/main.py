import logging
from typing import Annotated

import typer
from rich.table import Table

from finances import __version__
from finances.cli.accounts import app as accounts_app
from finances.cli.aliases import aliases_app
from finances.cli.audit import audit_command
from finances.cli.backup import app as backup_app
from finances.cli.budgets import app as budgets_app
from finances.cli.categories import (
    categories_app,
    categorize_command,
    rules_app,
    uncategorized_command,
)
from finances.cli.common import print_table
from finances.cli.db import app as db_app
from finances.cli.health import health_command
from finances.cli.importing import app as import_app
from finances.cli.listing import statements_app, transactions_app
from finances.cli.mcp import app as mcp_app
from finances.cli.people import app as people_app
from finances.cli.reports import (
    balances_command,
    forecast_command,
    insights_command,
    merchants_command,
    months_command,
    recurring_command,
    spending_command,
    upcoming_command,
)
from finances.cli.review import app as review_app
from finances.cli.sync import app as sync_app
from finances.cli.transfers import transfers_app
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
app.add_typer(mcp_app, name="mcp")
app.add_typer(categories_app, name="categories")
app.add_typer(rules_app, name="rules")
app.add_typer(aliases_app, name="aliases")
app.add_typer(transfers_app, name="transfers")
app.add_typer(backup_app, name="backup")
app.add_typer(budgets_app, name="budgets")
app.add_typer(review_app, name="review")
app.command("categorize")(categorize_command)
app.command("uncategorized")(uncategorized_command)
app.command("spending")(spending_command)
app.command("balances")(balances_command)
app.command("months")(months_command)
app.command("recurring")(recurring_command)
app.command("upcoming")(upcoming_command)
app.command("forecast")(forecast_command)
app.command("insights")(insights_command)
app.command("merchants")(merchants_command)
app.command("health")(health_command)
app.command("audit")(audit_command)


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
