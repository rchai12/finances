"""The `fin categories`, `fin rules`, `fin categorize`, and `fin uncategorized` commands."""

from dataclasses import astuple
from typing import Annotated

import typer
from rich.table import Table

from finances.categorize.service import CategorizeResult, categorize
from finances.categorize.transfers import pair_transfers
from finances.cli.common import fail, print_table, require_current_schema
from finances.cli.listing import transactions_app
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import (
    CategoryExistsError,
    clear_category_by_hand,
    create_category,
    create_rule,
    delete_rule,
    get_category_by_name,
    set_category_by_hand,
)
from finances.views.categories import (
    categorized_text,
    category_lines,
    rule_lines,
    uncategorized_lines,
)

categories_app = typer.Typer(help="Show and add categories.", no_args_is_help=True)
rules_app = typer.Typer(help="Rules that put transactions in categories.", no_args_is_help=True)


def categorize_all() -> CategorizeResult:
    """Run the rules over every transaction, then pair transfers, in a session of its own."""
    with session_scope(get_engine()) as session:
        result = categorize(session)
        pair_transfers(session)
    return result


def _print_rows(headings: tuple[str, ...], rows: list) -> None:
    table = Table()
    for heading in headings:
        table.add_column(heading)
    for row in rows:
        table.add_row(*astuple(row))
    print_table(table)


@categories_app.command("list")
def list_categories_command() -> None:
    """List the categories in each group."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        lines = category_lines(session)
    _print_rows(("Group", "Category", "Kind"), lines)


@categories_app.command("add")
def add_category_command(
    name: Annotated[str, typer.Option("--name", help="The new category's name.")],
    group: Annotated[str, typer.Option("--group", help="The group it goes in.")],
) -> None:
    """Add a category to a group."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            made = create_category(session, name, group)
        except (CategoryExistsError, ValueError) as error:
            fail(str(error))
        parent = get_category_by_name(session, group)
    typer.echo(f'Added category "{made.name}" to {parent.name}.')


@rules_app.command("list")
def list_rules_command() -> None:
    """List the rules in the order they are tried."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        lines = rule_lines(session)
    if not lines:
        typer.echo("No rules.")
        return
    _print_rows(("ID", "Priority", "Match", "Pattern", "Category"), lines)


@rules_app.command("add")
def add_rule_command(
    pattern: Annotated[str, typer.Option("--pattern", help="Text to look for in the merchant.")],
    category: Annotated[str, typer.Option("--category", help="The category it gives.")],
    match: Annotated[
        str, typer.Option("--match", help="contains, starts_with, or equals.")
    ] = "contains",
    priority: Annotated[int, typer.Option("--priority", help="Higher is tried first.")] = 0,
) -> None:
    """Add a rule, then categorize every transaction."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            rule = create_rule(session, pattern, category, match, priority)
        except ValueError as error:
            fail(str(error))
        target = get_category_by_name(session, category)
    typer.echo(f'Added rule {rule.id}: {rule.match} "{rule.pattern}" -> {target.name}.')
    typer.echo(categorized_text(categorize_all()))


@rules_app.command("delete")
def delete_rule_command(
    rule_id: Annotated[int, typer.Option("--id", help="The rule's id (see fin rules list).")],
) -> None:
    """Delete a rule, then categorize every transaction."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            delete_rule(session, rule_id)
        except ValueError as error:
            fail(str(error))
    typer.echo(f"Deleted rule {rule_id}.")
    typer.echo(categorized_text(categorize_all()))


def categorize_command() -> None:
    """Run the rules over every transaction."""
    require_current_schema()
    typer.echo(categorized_text(categorize_all()))


def uncategorized_command(
    limit: Annotated[
        int, typer.Option("--limit", min=1, max=1000, help="Most transactions to show.")
    ] = 50,
) -> None:
    """List transactions without a category, latest first."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        lines = uncategorized_lines(session, limit)
    if not lines:
        typer.echo("No uncategorized transactions.")
        return
    _print_rows(("ID", "Date", "Account", "Merchant", "Amount"), lines)


@transactions_app.command("set-category")
def set_category_command(
    transaction_id: Annotated[int, typer.Option("--id", help="The transaction's id.")],
    category: Annotated[
        str | None, typer.Option("--category", help="The category to set by hand.")
    ] = None,
    clear: Annotated[
        bool, typer.Option("--clear", help="Leave the category to the rules again.")
    ] = False,
) -> None:
    """Set a transaction's category by hand, or leave it to the rules again."""
    require_current_schema()
    if (category is not None) == clear:
        fail("give either --category or --clear")
    with session_scope(get_engine()) as session:
        try:
            if category is None:
                clear_category_by_hand(session, transaction_id)
            else:
                chosen = set_category_by_hand(session, transaction_id, category)
        except ValueError as error:
            fail(str(error))
    if category is None:
        typer.echo(f"Transaction {transaction_id}: category left to the rules.")
        typer.echo(categorized_text(categorize_all()))
    else:
        typer.echo(f"Transaction {transaction_id}: {chosen.name}, set by hand.")
