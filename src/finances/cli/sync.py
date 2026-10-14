"""The `fin sync` commands."""

from dataclasses import astuple
from datetime import UTC, datetime
from typing import Annotated

import typer
from rich.table import Table

from finances.cli.common import fail, print_table, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import (
    account_names,
    get_account_by_name,
    list_feed_accounts,
    list_feed_links,
    map_feed_account,
)
from finances.domain.feed_setup import new_accounts
from finances.domain.models import DEFAULT_LINK, validate_provider_account_id
from finances.sync import transport
from finances.sync.links import (
    delete_access_url,
    load_access_url,
    save_access_url,
    validate_link_name,
)
from finances.sync.runner import KEYCHAIN_FAILED, NOT_SET_UP, LinkRun, run_links
from finances.sync.simplefin import SyncError, claim_access_url, fetch_accounts
from finances.views.sync import run_rows, simplefin_messages, status_rows, waiting_counts

app = typer.Typer(help="Pull transactions from SimpleFIN.", no_args_is_help=True)

_LinkOption = Annotated[str, typer.Option("--link", help="Name of the SimpleFIN link.")]


def _link_name(name: str) -> str:
    try:
        return validate_link_name(name)
    except ValueError as error:
        fail(str(error))


def _not_set_up(link: str) -> str:
    return f"link {link} is not set up (run: fin sync link --link {link})"


def _access(link: str) -> str:
    """Return the link's access URL, or end the command when there is none."""
    try:
        access_url = load_access_url(link)
    except SyncError as error:
        fail(str(error))
    if access_url is None:
        fail(_not_set_up(link))
    return access_url


def _today() -> datetime:
    return datetime.now(UTC)


@app.command("link")
def link_command(
    link: _LinkOption = DEFAULT_LINK,
    replace: Annotated[
        bool, typer.Option("--replace", help="Set up a link that is already set up.")
    ] = False,
) -> None:
    """Claim a SimpleFIN setup token and keep the access in the Keychain."""
    name = _link_name(link)
    try:
        if load_access_url(name) is not None and not replace:
            fail(f"link {name} is already set up; use --replace to set it up again")
        token = typer.prompt("SimpleFIN setup token", hide_input=True)
        save_access_url(name, claim_access_url(token, transport.urllib_transport))
    except SyncError as error:
        fail(str(error))
    typer.echo(f"Linked {name}.")


@app.command("unlink")
def unlink_command(link: _LinkOption = DEFAULT_LINK) -> None:
    """Forget a link's access. Its mappings stay."""
    name = _link_name(link)
    try:
        removed = delete_access_url(name)
    except SyncError as error:
        fail(str(error))
    if not removed:
        fail(f"link {name} is not set up")
    typer.echo(f"Unlinked {name}.")


@app.command("accounts")
def accounts_command(link: _LinkOption = DEFAULT_LINK) -> None:
    """List the accounts SimpleFIN has under a link."""
    require_current_schema()
    name = _link_name(link)
    access_url = _access(name)
    today = _today().date()
    try:
        answer = fetch_accounts(access_url, today, today, transport.urllib_transport)
    except SyncError as error:
        fail(str(error))
    with session_scope(get_engine()) as session:
        names = account_names(session)
        mapped = {
            item.provider_account_id: names[item.account_id]
            for item in list_feed_accounts(session, name)
        }
    if not answer.accounts:
        typer.echo("No accounts.")
    else:
        table = Table()
        for heading in ("SimpleFIN account", "Institution", "Name", "Currency", "Mapped to"):
            table.add_column(heading)
        for item in answer.accounts:
            table.add_row(
                item.provider_account_id,
                item.institution,
                item.name,
                item.currency,
                mapped.get(item.provider_account_id, ""),
            )
        print_table(table)
    for message in answer.messages:
        typer.echo(f"SimpleFIN: {message}")


@app.command("map")
def map_command(
    account: Annotated[str, typer.Option("--account", help="Account name.")],
    feed_account: Annotated[
        str, typer.Option("--feed-account", help="SimpleFIN account id (see fin sync accounts).")
    ],
    link: _LinkOption = DEFAULT_LINK,
) -> None:
    """Say which SimpleFIN account feeds one of our accounts."""
    require_current_schema()
    name = _link_name(link)
    try:
        feed_id = validate_provider_account_id(feed_account)
    except ValueError as error:
        fail(str(error))
    with session_scope(get_engine()) as session:
        found = get_account_by_name(session, account)
        if found is None:
            fail("account not found")
        try:
            map_feed_account(session, found.id, feed_id, name)
        except ValueError as error:
            fail(str(error))
    typer.echo(f'Mapped {feed_id} to "{found.name}" under link {name}.')


@app.command("run")
def run_command(
    link: Annotated[
        str | None, typer.Option("--link", help="Run this link only; every link when left out.")
    ] = None,
    days: Annotated[
        int, typer.Option("--days", min=1, max=90, help="Days of transactions to ask for.")
    ] = 30,
) -> None:
    """Pull every link's accounts from SimpleFIN."""
    require_current_schema()
    if link is not None:
        links = [_link_name(link)]
    else:
        with session_scope(get_engine()) as session:
            links = list_feed_links(session)
    if not links:
        typer.echo("No mapped accounts.")
        return
    runs = run_links(
        get_engine(), links, today=_today().date(), transport=transport.urllib_transport, days=days
    )
    for item in runs:
        if item.failure is not None:
            typer.echo(f"Error: {_failure_text(item)}", err=True)
    with session_scope(get_engine()) as session:
        rows = run_rows(runs, account_names(session))
        waiting = waiting_counts(session, runs)
    if rows:
        table = Table()
        for heading in (
            "Link",
            "Account",
            "SimpleFIN account",
            "New",
            "Changed",
            "Removed",
            "Same",
            "Drift",
            "Problem",
        ):
            table.add_column(heading)
        for row in rows:
            table.add_row(*astuple(row))
        print_table(table)
    for name, count in waiting:
        typer.echo(
            f"SimpleFIN ({name}): {new_accounts(count)} to set up "
            f"(open the SimpleFIN page, or run: fin sync accounts --link {name})"
        )
    for name, message in simplefin_messages(runs):
        typer.echo(f"SimpleFIN ({name}): {message}")
    if any(item.failure is not None for item in runs):
        raise typer.Exit(code=1)


def _failure_text(item: LinkRun) -> str:
    if item.failure == KEYCHAIN_FAILED:
        return str(item.cause)
    if item.failure == NOT_SET_UP:
        return _not_set_up(item.link)
    return f"link {item.link}: {item.cause}"


@app.command("status")
def status_command() -> None:
    """Show each mapped account's last pull and drift."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        rows = status_rows(session)
    if not rows:
        typer.echo("No mapped accounts.")
        return
    table = Table()
    for heading in (
        "Link",
        "Account",
        "SimpleFIN account",
        "Keychain",
        "Last pull",
        "Balance date",
        "Drift",
    ):
        table.add_column(heading)
    for row in rows:
        table.add_row(*astuple(row))
    print_table(table)
