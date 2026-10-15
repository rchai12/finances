"""The `fin spending` command: where the money went in a month or range."""

from datetime import date, datetime
from typing import Annotated

import typer
from rich.table import Table

from finances.analysis.spending import spending_report
from finances.cli.common import fail, print_table, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.domain.spending import month_bounds, month_range
from finances.views.spending import spending_heading, spending_rows, spending_summary


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
        table = Table()
        for heading in (by.capitalize(), "Spent", "Count"):
            table.add_column(heading)
        for row in rows:
            table.add_row(row.label, row.spent, row.count)
        print_table(table)
    else:
        typer.echo("No spending.")
    for line in spending_summary(report):
        typer.echo(line)
