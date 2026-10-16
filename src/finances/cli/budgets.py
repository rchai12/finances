"""The `fin budgets` commands."""

from dataclasses import astuple
from typing import Annotated

import typer
from rich.table import Table

from finances import clock
from finances.analysis.budgets import budget_report
from finances.cli.common import fail, print_table, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import list_budgets, remove_budget, set_budget
from finances.domain.budgets import AMOUNT_MESSAGE
from finances.domain.money import format_cents, parse_money
from finances.domain.spending import month_bounds, month_range
from finances.views.budgets import budget_rows, budgets_summary

app = typer.Typer(help="Monthly spending targets for categories and groups.", no_args_is_help=True)


@app.command("set")
def set_command(
    name: Annotated[str, typer.Option("--name", help="A category or group name.")],
    amount: Annotated[str, typer.Option("--amount", help="The monthly target, as money.")],
) -> None:
    """Set or replace a monthly budget."""
    require_current_schema()
    try:
        cents = parse_money(amount)
    except ValueError:
        fail(AMOUNT_MESSAGE)
    with session_scope(get_engine()) as session:
        try:
            stored, budget = set_budget(session, name, cents)
        except ValueError as error:
            fail(str(error))
    typer.echo(f'Budget for "{stored}": {format_cents(budget.amount_cents)} a month.')


@app.command("remove")
def remove_command(
    name: Annotated[str, typer.Option("--name", help="A category or group name.")],
) -> None:
    """Remove a monthly budget."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            stored = remove_budget(session, name)
        except ValueError as error:
            fail(str(error))
    typer.echo(f'Removed the budget for "{stored}".')


@app.command("list")
def list_command(
    month: Annotated[
        str | None, typer.Option("--month", help="A month, YYYY-MM (this month by default).")
    ] = None,
) -> None:
    """Show each budget for a month: target, spent, left, and how far through the month."""
    require_current_schema()
    today = clock.today()
    try:
        start, _end = month_range(month) if month else month_bounds(today)
    except ValueError as error:
        fail(str(error))
    with session_scope(get_engine()) as session:
        if not list_budgets(session):
            typer.echo(f"Budgets for {start.isoformat()[:7]}.\nNo budgets.")
            return
        lines = budget_report(session, start, today)
    typer.echo(f"Budgets for {start.isoformat()[:7]}.")
    table = Table()
    for heading in ("Budget", "Kind", "Target", "Spent", "Left", "Used", "Month gone"):
        table.add_column(heading)
    for row in budget_rows(lines):
        table.add_row(*astuple(row))
    print_table(table)
    typer.echo(budgets_summary(lines))
