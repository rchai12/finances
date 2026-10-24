"""The `fin transactions` split, parts, and unsplit commands."""

from typing import Annotated

import typer

from finances.cli.categories import categorize_all
from finances.cli.common import fail, print_rows, require_current_schema
from finances.cli.listing import transactions_app
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import (
    clear_split,
    get_transaction,
    list_categories,
    split_by_sizes,
    splits_for,
)
from finances.domain.splits import parse_part
from finances.views.categories import categorized_text
from finances.views.transactions import part_lines


@transactions_app.command("split")
def split_command(
    transaction_id: Annotated[int, typer.Option("--id", help="The transaction's id.")],
    parts: Annotated[
        list[str],
        typer.Option("--part", help='A part as SIZE CATEGORY, such as "12.00 Groceries".'),
    ],
) -> None:
    """Split a transaction into parts, each with its own size and category."""
    require_current_schema()
    try:
        parsed = [parse_part(text) for text in parts]
    except ValueError as error:
        fail(str(error))
    with session_scope(get_engine()) as session:
        try:
            stored = split_by_sizes(session, transaction_id, parsed)
        except ValueError as error:
            fail(str(error))
    typer.echo(f"Transaction {transaction_id}: split into {len(stored)} parts.")


@transactions_app.command("unsplit")
def unsplit_command(
    transaction_id: Annotated[int, typer.Option("--id", help="The transaction's id.")],
) -> None:
    """Remove a transaction's split and run the rules."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            clear_split(session, transaction_id)
        except ValueError as error:
            fail(str(error))
    typer.echo(f"Transaction {transaction_id}: split removed.")
    typer.echo(categorized_text(categorize_all()))


@transactions_app.command("parts")
def parts_command(
    transaction_id: Annotated[int, typer.Option("--id", help="The transaction's id.")],
) -> None:
    """Show a transaction's parts."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        if get_transaction(session, transaction_id) is None:
            fail("transaction not found")
        found = splits_for(session, [transaction_id]).get(transaction_id)
        names = {item.id: item.name for item in list_categories(session)}
    if not found:
        typer.echo(f"Transaction {transaction_id} is not split.")
        return
    print_rows(("Part", "Amount", "Category"), part_lines(found, names))
