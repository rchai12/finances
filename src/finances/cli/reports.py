"""Report commands: `fin spending`, `fin balances`, and `fin months`."""

from collections.abc import Iterable, Sequence
from dataclasses import astuple
from datetime import date, datetime
from typing import Annotated

import typer
from rich.table import Table

from finances.analysis.balances import balance_report
from finances.analysis.months import month_report
from finances.analysis.spending import spending_report
from finances.cli.common import fail, print_table, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.domain.periods import MONTHS_MAX
from finances.domain.spending import month_bounds, month_range
from finances.views.balances import balance_rows, balance_summary
from finances.views.months import month_heading, month_notes, month_rows
from finances.views.spending import spending_heading, spending_rows, spending_summary


def _print_rows(headings: Sequence[str], rows: Iterable[object]) -> None:
    table = Table()
    for heading in headings:
        table.add_column(heading)
    for row in rows:
        table.add_row(*astuple(row))
    print_table(table)


def _range(month: str | None, start: datetime | None, end: datetime | None) -> tuple[date, date]:
    if month is not None and (start is not None or end is not None):
        fail("give --month, or --from and --to, not both")
    if (start is None) != (end is None):
        fail("give both --from and --to")
    if month is not None:
        try:
            return month_range(month)
        except ValueError as error:
            fail(str(error))
    if start is not None and end is not None:
        return start.date(), end.date()
    return month_bounds(date.today())


def spending_command(
    month: Annotated[str | None, typer.Option("--month", help="A month, YYYY-MM.")] = None,
    start: Annotated[
        datetime | None,
        typer.Option("--from", formats=["%Y-%m-%d"], help="First day, YYYY-MM-DD."),
    ] = None,
    end: Annotated[
        datetime | None,
        typer.Option("--to", formats=["%Y-%m-%d"], help="Last day, YYYY-MM-DD."),
    ] = None,
    by: Annotated[
        str,
        typer.Option("--by", help="category, group, merchant, person, account, bank, or card."),
    ] = "category",
) -> None:
    """Show spending for a month or range (this month by default), grouped one way."""
    require_current_schema()
    first, last = _range(month, start, end)
    with session_scope(get_engine()) as session:
        try:
            report = spending_report(session, first, last, by)
        except ValueError as error:
            fail(str(error))
    typer.echo(spending_heading(report))
    rows = spending_rows(report)
    if rows:
        _print_rows((by.capitalize(), "Spent", "Count"), rows)
    else:
        typer.echo("No spending.")
    for line in spending_summary(report):
        typer.echo(line)


def balances_command() -> None:
    """Show each active account's newest balance, and the net worth."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        report = balance_report(session)
    if not report.lines:
        typer.echo("No accounts.")
        return
    _print_rows(("Account", "Type", "Balance", "As of", "From"), balance_rows(report))
    for line in balance_summary(report):
        typer.echo(line)


def months_command(
    to: Annotated[
        str | None, typer.Option("--to", help="The last month, YYYY-MM (this month by default).")
    ] = None,
    count: Annotated[int, typer.Option("--count", help=f"How many months, 1 to {MONTHS_MAX}.")] = 6,
) -> None:
    """Compare the spending and income of recent months, and say which data covers them."""
    require_current_schema()
    day = date.today()
    if to is not None:
        try:
            day = month_range(to)[0]
        except ValueError as error:
            fail(str(error))
    with session_scope(get_engine()) as session:
        try:
            lines = month_report(session, day, count)
        except ValueError as error:
            fail(str(error))
    typer.echo(month_heading(lines))
    _print_rows(("Month", "Spent", "Income", "Change", "Covered"), month_rows(lines))
    for note in month_notes(lines):
        typer.echo(note)
