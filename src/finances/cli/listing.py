"""The `fin statements` and `fin transactions` commands."""

from datetime import datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy.orm import Session

from finances.cli.common import require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import (
    get_account_by_name,
    list_accounts,
    list_statements,
    list_transactions,
)
from finances.domain.models import Statement, Transaction
from finances.domain.money import format_cents

statements_app = typer.Typer(help="Show imported statements.", no_args_is_help=True)
transactions_app = typer.Typer(help="Show transactions.", no_args_is_help=True)
console = Console(width=200, height=25)
_BULLETS = "\u2022\u2022"


@statements_app.command("list")
def list_statements_command(
    account: Annotated[str | None, typer.Option("--account", help="Account name.")] = None,
) -> None:
    """List imported statements."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        account_id = _account_id(session, account)
        found = list_statements(session, account_id)
        names = _account_names(session)
    if not found:
        typer.echo("No statements.")
        return
    table = Table()
    for heading in ("Account", "File", "Parser", "Period", "Opening", "Closing", "Lines", "New"):
        table.add_column(heading)
    for item in found:
        table.add_row(*_statement_cells(item, names))
    console.print(table)


@transactions_app.command("list")
def list_transactions_command(
    account: Annotated[str | None, typer.Option("--account", help="Account name.")] = None,
    start: Annotated[
        datetime | None,
        typer.Option("--from", formats=["%Y-%m-%d"], help="First posted date, YYYY-MM-DD."),
    ] = None,
    end: Annotated[
        datetime | None,
        typer.Option("--to", formats=["%Y-%m-%d"], help="Last posted date, YYYY-MM-DD."),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum rows.")] = 50,
) -> None:
    """List stored transactions."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        account_id = _account_id(session, account)
        found = list_transactions(
            session,
            account_id,
            None if start is None else start.date(),
            None if end is None else end.date(),
            limit,
        )
        names = _account_names(session)
    if not found:
        typer.echo("No transactions.")
        return
    table = Table()
    for heading in ("Date", "Account", "Description", "Amount", "Card", "Section"):
        table.add_column(heading)
    for item in found:
        table.add_row(*_transaction_cells(item, names))
    console.print(table)


def _account_id(session: Session, name: str | None) -> int | None:
    if name is None:
        return None
    account = get_account_by_name(session, name)
    if account is None:
        typer.echo("Error: account not found", err=True)
        raise typer.Exit(code=1) from None
    return account.id


def _account_names(session: Session) -> dict[int, str]:
    return {item.id: item.name for item in list_accounts(session, include_inactive=True)}


def _statement_cells(item: Statement, names: dict[int, str]) -> tuple[str, ...]:
    return (
        names[item.account_id],
        item.source_filename,
        item.parser_name,
        f"{item.period_start.isoformat()} to {item.period_end.isoformat()}",
        format_cents(item.opening_balance_cents),
        format_cents(item.closing_balance_cents),
        str(item.lines_parsed),
        str(item.rows_inserted),
    )


def _transaction_cells(item: Transaction, names: dict[int, str]) -> tuple[str, ...]:
    card = f"{_BULLETS}{item.card_last4}" if item.card_last4 else ""
    return (
        item.posted_date.isoformat(),
        names[item.account_id],
        item.description,
        format_cents(item.amount_cents),
        card,
        item.section or "",
    )
