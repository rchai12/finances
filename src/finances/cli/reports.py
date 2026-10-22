"""Report commands: spending, balances, months, recurring charges, insights, and merchants."""

from datetime import date, datetime
from typing import Annotated

import typer

from finances import clock
from finances.analysis.balances import balance_report
from finances.analysis.forecast import forecast_report
from finances.analysis.insights import insights_report
from finances.analysis.months import month_report
from finances.analysis.recurring import recurring_charges, recurring_income
from finances.analysis.spending import spending_report
from finances.analysis.upcoming import upcoming_report
from finances.cli.common import fail, print_rows, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.domain.periods import MONTHS_MAX
from finances.domain.spending import month_bounds, month_range
from finances.views.balances import balance_rows, balance_summary
from finances.views.forecast import (
    account_heading,
    forecast_heading,
    forecast_rows,
    lowest_line,
    no_balance_line,
    starting_line,
    step_rows,
)
from finances.views.insights import (
    finding_rows,
    findings_summary,
    insights_heading,
    merchant_rows,
)
from finances.views.months import month_heading, month_notes, month_rows
from finances.views.recurring import recurring_income_summary, recurring_rows, recurring_summary
from finances.views.spending import spending_heading, spending_rows, spending_summary
from finances.views.upcoming import upcoming_heading, upcoming_rows, upcoming_summary


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
    return month_bounds(clock.today())


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
        print_rows((by.capitalize(), "Spent", "Count"), rows)
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
    print_rows(("Account", "Type", "Balance", "As of", "From"), balance_rows(report))
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
    day = clock.today()
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
    print_rows(("Month", "Spent", "Income", "Change", "Covered"), month_rows(lines))
    for note in month_notes(lines):
        typer.echo(note)


def recurring_command(
    as_of: Annotated[
        datetime | None,
        typer.Option(
            "--as-of", formats=["%Y-%m-%d"], help="The day to look from (today by default)."
        ),
    ] = None,
    show_all: Annotated[
        bool, typer.Option("--all", help="Also list charges that have stopped.")
    ] = False,
    income: Annotated[
        bool, typer.Option("--income", help="List recurring income instead of charges.")
    ] = False,
) -> None:
    """List subscriptions and other charges that come at a regular rhythm."""
    require_current_schema()
    day = clock.today() if as_of is None else as_of.date()
    with session_scope(get_engine()) as session:
        items = recurring_income(session, day) if income else recurring_charges(session, day)
    rows = recurring_rows(items, include_inactive=show_all)
    if rows:
        headings = ("Merchant", "Every", "Amount", "Monthly", "Count", "Last", "Next", "Active")
        print_rows(headings, rows)
    else:
        typer.echo("No recurring income." if income else "No recurring charges.")
    typer.echo(recurring_income_summary(items) if income else recurring_summary(items))


def upcoming_command(
    as_of: Annotated[
        datetime | None,
        typer.Option(
            "--as-of", formats=["%Y-%m-%d"], help="The day to look from (today by default)."
        ),
    ] = None,
    days: Annotated[
        int, typer.Option("--days", min=1, max=90, help="How many days to look ahead, 1 to 90.")
    ] = 30,
) -> None:
    """List bills and income expected in the next days (today counted as the first)."""
    require_current_schema()
    day = clock.today() if as_of is None else as_of.date()
    with session_scope(get_engine()) as session:
        report = upcoming_report(session, day, days)
    typer.echo(upcoming_heading(report))
    rows = upcoming_rows(report)
    if rows:
        print_rows(("Date", "What", "Merchant", "Every", "Amount"), rows)
    else:
        typer.echo("Nothing expected.")
    typer.echo(upcoming_summary(report))


def forecast_command(
    as_of: Annotated[
        datetime | None,
        typer.Option(
            "--as-of", formats=["%Y-%m-%d"], help="The day to look from (today by default)."
        ),
    ] = None,
    days: Annotated[
        int, typer.Option("--days", min=1, max=90, help="How many days to look ahead, 1 to 90.")
    ] = 30,
    account: Annotated[
        str | None, typer.Option("--account", help="One account, shown day by day.")
    ] = None,
) -> None:
    """Walk each account's balance through the bills and income expected in the next days."""
    require_current_schema()
    day = clock.today() if as_of is None else as_of.date()
    with session_scope(get_engine()) as session:
        try:
            report = forecast_report(session, day, days, account)
        except ValueError as error:
            fail(str(error))
    if account is not None:
        forecast = report.accounts[0]
        typer.echo(account_heading(report))
        typer.echo(starting_line(forecast))
        rows = step_rows(forecast)
        if rows:
            print_rows(("Date", "Merchant", "Amount", "Balance"), rows)
        else:
            typer.echo("Nothing expected.")
        typer.echo(lowest_line(forecast))
        return
    typer.echo(forecast_heading(report))
    rows = forecast_rows(report)
    if rows:
        headings = (
            "Account",
            "Balance",
            "As of",
            "Expected in",
            "Expected out",
            "End",
            "Lowest",
            "Lowest on",
        )
        print_rows(headings, rows)
    else:
        typer.echo("No accounts with a balance.")
    missing = no_balance_line(report)
    if missing is not None:
        typer.echo(missing)


_MONTH_OPTION = typer.Option("--month", help="A month, YYYY-MM (this month by default).")


def _first_day(month: str | None) -> date:
    if month is None:
        return month_bounds(clock.today())[0]
    try:
        return month_range(month)[0]
    except ValueError as error:
        fail(str(error))


def insights_command(month: Annotated[str | None, _MONTH_OPTION] = None) -> None:
    """List what deserves a look in a month, and roughly what it could save."""
    require_current_schema()
    first = _first_day(month)
    with session_scope(get_engine()) as session:
        report = insights_report(session, first)
    typer.echo(insights_heading(report))
    rows = finding_rows(report)
    if not rows:
        typer.echo("No findings.")
        return
    print_rows(("Severity", "Type", "About", "Saves a month", "Detail"), rows)
    typer.echo(findings_summary(report))


def merchants_command(month: Annotated[str | None, _MONTH_OPTION] = None) -> None:
    """List each merchant of a month against its three months before."""
    require_current_schema()
    first = _first_day(month)
    with session_scope(get_engine()) as session:
        report = insights_report(session, first)
    typer.echo(f"Merchants for {first.isoformat()[:7]}.")
    rows = merchant_rows(report)
    if not rows:
        typer.echo("No spending.")
        return
    headings = ("Merchant", "Visits", "Spent", "Average", "Baseline", "Change", "Weekend")
    print_rows(headings, rows)
