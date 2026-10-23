"""The `fin categories`, `fin rules`, `fin categorize`, and `fin uncategorized` commands."""

from typing import Annotated

import typer

from finances.analysis.categories import (
    card_credit_count,
    category_tree,
    rule_listing,
    uncategorized_items,
)
from finances.categorize.service import CategorizeResult, categorize, preview_rule
from finances.categorize.transfers import pair_transfers
from finances.cli.common import fail, print_rows, require_current_schema
from finances.cli.listing import transactions_app
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import (
    CategoryExistsError,
    clear_categories_by_hand,
    create_category,
    create_rule,
    delete_category,
    delete_rule,
    edit_rule,
    get_category_by_name,
    list_categories,
    rename_category,
    set_categories_by_hand,
)
from finances.views.categories import (
    card_credits_note,
    categorized_text,
    category_lines,
    preview_lines,
    preview_more,
    preview_text,
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


@categories_app.command("list")
def list_categories_command() -> None:
    """List the categories in each group."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        lines = category_lines(category_tree(session))
    print_rows(("Group", "Category", "Kind"), lines)


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


@categories_app.command("rename")
def rename_category_command(
    name: Annotated[str, typer.Option("--name", help="The category or group to rename.")],
    to: Annotated[str, typer.Option("--to", help="Its new name.")],
) -> None:
    """Rename a category or a group."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            old, renamed = rename_category(session, name, to)
        except (CategoryExistsError, ValueError) as error:
            fail(str(error))
    typer.echo(f'Renamed "{old}" to "{renamed.name}".')


@categories_app.command("delete")
def delete_category_command(
    name: Annotated[str, typer.Option("--name", help="The category or group to delete.")],
    move_to: Annotated[
        str,
        typer.Option(
            "--move-to",
            help="When the category is in use, move its transactions and rules here first.",
        ),
    ] = "",
) -> None:
    """Delete a category or an empty group."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            deleted = delete_category(session, name, move_to)
        except ValueError as error:
            fail(str(error))
    if deleted.was_group:
        typer.echo(f'Deleted group "{deleted.name}".')
    elif deleted.moved_to is not None:
        typer.echo(
            f'Deleted category "{deleted.name}"; moved its transactions ({deleted.transactions}) '
            f'and rules ({deleted.rules}) to "{deleted.moved_to}".'
        )
    else:
        typer.echo(f'Deleted category "{deleted.name}".')


@rules_app.command("list")
def list_rules_command() -> None:
    """List the rules in the order they are tried."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        lines = rule_lines(rule_listing(session))
    if not lines:
        typer.echo("No rules.")
        return
    print_rows(("ID", "Priority", "Match", "Pattern", "Category"), lines)


@rules_app.command("preview")
def preview_rule_command(
    pattern: Annotated[str, typer.Option("--pattern", help="Text to look for in the merchant.")],
    category: Annotated[str, typer.Option("--category", help="The category it gives.")],
    match: Annotated[
        str, typer.Option("--match", help="contains, starts_with, or equals.")
    ] = "contains",
    priority: Annotated[int, typer.Option("--priority", help="Higher is tried first.")] = 0,
) -> None:
    """Show which transactions a rule would put in its category, without adding it."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        try:
            preview = preview_rule(session, pattern, category, match=match, priority=priority)
        except ValueError as error:
            fail(str(error))
    typer.echo(preview_text(preview))
    lines = preview_lines(preview)
    if lines:
        print_rows(("ID", "Date", "Account", "Merchant", "Amount", "Now"), lines)
    more = preview_more(preview)
    if more is not None:
        typer.echo(more)


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


@rules_app.command("edit")
def edit_rule_command(
    rule_id: Annotated[int, typer.Option("--id", help="The rule's id (see fin rules list).")],
    pattern: Annotated[
        str | None, typer.Option("--pattern", help="Text to look for in the merchant.")
    ] = None,
    match: Annotated[
        str | None, typer.Option("--match", help="contains, starts_with, or equals.")
    ] = None,
    priority: Annotated[
        int | None, typer.Option("--priority", help="Higher is tried first.")
    ] = None,
    category: Annotated[
        str | None, typer.Option("--category", help="The category it gives.")
    ] = None,
) -> None:
    """Change a rule, then categorize every transaction."""
    require_current_schema()
    if pattern is None and match is None and priority is None and category is None:
        fail("give at least one of --pattern, --match, --priority, --category")
    with session_scope(get_engine()) as session:
        try:
            rule = edit_rule(
                session,
                rule_id,
                pattern=pattern,
                match=match,
                priority=priority,
                category=category,
            )
        except ValueError as error:
            fail(str(error))
        names = {item.id: item.name for item in list_categories(session)}
        target_name = names[rule.category_id]
    typer.echo(f'Changed rule {rule.id}: {rule.match} "{rule.pattern}" -> {target_name}.')
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
        items = uncategorized_items(session, limit)
        lines = uncategorized_lines(items)
        note = card_credits_note(card_credit_count(items))
    if not lines:
        typer.echo("No uncategorized transactions.")
        return
    print_rows(("ID", "Date", "Account", "Merchant", "Amount"), lines)
    if note is not None:
        typer.echo(note)


@transactions_app.command("set-category")
def set_category_command(
    transaction_ids: Annotated[
        list[int], typer.Option("--id", help="The transaction's id; may be given several times.")
    ],
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
                count = clear_categories_by_hand(session, transaction_ids)
            else:
                count, chosen = set_categories_by_hand(session, transaction_ids, category)
        except ValueError as error:
            fail(str(error))
    if category is None:
        if count == 1:
            typer.echo(f"Transaction {transaction_ids[0]}: category left to the rules.")
        else:
            typer.echo(f"{count} transactions: category left to the rules.")
        typer.echo(categorized_text(categorize_all()))
    elif count == 1:
        typer.echo(f"Transaction {transaction_ids[0]}: {chosen.name}, set by hand.")
    else:
        typer.echo(f"{count} transactions: {chosen.name}, set by hand.")
