"""The `fin transactions` tag and note commands."""

from dataclasses import dataclass
from typing import Annotated

import typer

from finances.cli.common import fail, print_rows, require_current_schema
from finances.cli.listing import transactions_app
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import add_tags, list_tags, remove_tags, set_note

_IDS = Annotated[
    list[int], typer.Option("--id", help="The transaction's id; may be given several times.")
]


@dataclass(frozen=True)
class _TagRow:
    tag: str
    transactions: str


@transactions_app.command("tag")
def tag_command(
    transaction_ids: _IDS,
    tag: Annotated[str, typer.Option("--tag", help="The label to add.")],
) -> None:
    """Add a tag to one or more transactions."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            count, stored = add_tags(session, transaction_ids, tag)
        except ValueError as error:
            fail(str(error))
    if count == 1:
        typer.echo(f'Transaction {transaction_ids[0]}: tagged "{stored}".')
    else:
        typer.echo(f'{count} transactions: tagged "{stored}".')


@transactions_app.command("untag")
def untag_command(
    transaction_ids: _IDS,
    tag: Annotated[str, typer.Option("--tag", help="The label to remove.")],
) -> None:
    """Remove a tag from one or more transactions."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            count, stored = remove_tags(session, transaction_ids, tag)
        except ValueError as error:
            fail(str(error))
    if count == 1:
        typer.echo(f'Transaction {transaction_ids[0]}: "{stored}" removed.')
    else:
        typer.echo(f'{count} transactions: "{stored}" removed.')


@transactions_app.command("note")
def note_command(
    transaction_id: Annotated[int, typer.Option("--id", help="The transaction's id.")],
    text: Annotated[str, typer.Option("--text", help="The note; empty removes it.")],
) -> None:
    """Set or remove a transaction's note."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            found = set_note(session, transaction_id, text)
        except ValueError as error:
            fail(str(error))
    if found is None:
        typer.echo(f"Transaction {transaction_id}: note removed.")
    else:
        typer.echo(f"Transaction {transaction_id}: note saved.")


@transactions_app.command("tags")
def tags_command() -> None:
    """List each tag and how many transactions carry it."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        found = list_tags(session)
    if not found:
        typer.echo("No tags.")
        return
    print_rows(
        ("Tag", "Transactions"),
        [_TagRow(item.tag, str(item.transactions)) for item in found],
    )
