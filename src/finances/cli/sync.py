"""The `fin sync` commands."""

from datetime import UTC, datetime
from typing import Annotated, NoReturn

import typer
from rich.table import Table
from sqlalchemy.orm import Session

from finances.cli.common import print_table, require_current_schema
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import (
    get_account_by_name,
    latest_feed_pull,
    list_accounts,
    list_feed_accounts,
    list_feed_links,
    list_new_feed_accounts,
    map_feed_account,
)
from finances.domain.feed_setup import new_accounts
from finances.domain.models import DEFAULT_LINK, FeedPull
from finances.domain.money import format_cents
from finances.sync import transport
from finances.sync.links import (
    delete_access_url,
    load_access_url,
    save_access_url,
    validate_link_name,
)
from finances.sync.runner import AccountSync, run_sync
from finances.sync.simplefin import SyncError, claim_access_url, fetch_accounts

app = typer.Typer(help="Pull transactions from SimpleFIN.", no_args_is_help=True)

_FEED_ID_LIMIT = 200
_LinkOption = Annotated[str, typer.Option("--link", help="Name of the SimpleFIN link.")]


def _fail(message: str) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1) from None


def _link_name(name: str) -> str:
    try:
        return validate_link_name(name)
    except ValueError as error:
        _fail(str(error))


def _not_set_up(link: str) -> str:
    return f"link {link} is not set up (run: fin sync link --link {link})"


def _access(link: str) -> str:
    """Return the link's access URL, or end the command when there is none."""
    try:
        access_url = load_access_url(link)
    except SyncError as error:
        _fail(str(error))
    if access_url is None:
        _fail(_not_set_up(link))
    return access_url


def _today() -> datetime:
    return datetime.now(UTC)


def _account_names(session: Session) -> dict[int, str]:
    return {item.id: item.name for item in list_accounts(session, include_inactive=True)}


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
            _fail(f"link {name} is already set up; use --replace to set it up again")
        token = typer.prompt("SimpleFIN setup token", hide_input=True)
        save_access_url(name, claim_access_url(token, transport.urllib_transport))
    except SyncError as error:
        _fail(str(error))
    typer.echo(f"Linked {name}.")


@app.command("unlink")
def unlink_command(link: _LinkOption = DEFAULT_LINK) -> None:
    """Forget a link's access. Its mappings stay."""
    name = _link_name(link)
    try:
        removed = delete_access_url(name)
    except SyncError as error:
        _fail(str(error))
    if not removed:
        _fail(f"link {name} is not set up")
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
        _fail(str(error))
    with session_scope(get_engine()) as session:
        names = _account_names(session)
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
    feed_id = feed_account.strip()
    if not 1 <= len(feed_id) <= _FEED_ID_LIMIT:
        _fail("feed account id must be 1 to 200 characters")
    with session_scope(get_engine()) as session:
        found = get_account_by_name(session, account)
        if found is None:
            _fail("account not found")
        try:
            map_feed_account(session, found.id, feed_id, name)
        except ValueError as error:
            _fail(str(error))
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
    today = _today().date()
    results: list[tuple[str, AccountSync]] = []
    messages: list[tuple[str, str]] = []
    ran: list[str] = []
    skipped = False
    for name in links:
        try:
            access_url = load_access_url(name)
        except SyncError as error:
            typer.echo(f"Error: {error}", err=True)
            skipped = True
            continue
        if access_url is None:
            typer.echo(f"Error: {_not_set_up(name)}", err=True)
            skipped = True
            continue
        try:
            with session_scope(get_engine()) as session:
                report = run_sync(
                    session,
                    access_url,
                    today=today,
                    transport=transport.urllib_transport,
                    days=days,
                    link=name,
                )
        except SyncError as error:
            typer.echo(f"Error: link {name}: {error}", err=True)
            skipped = True
            continue
        ran.append(name)
        results += [(name, item) for item in report.accounts]
        messages += [(name, message) for message in report.messages]
    if results:
        with session_scope(get_engine()) as session:
            names = _account_names(session)
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
        for name, item in results:
            table.add_row(*_run_cells(name, item, names))
        print_table(table)
    with session_scope(get_engine()) as session:
        waiting = [(name, len(list_new_feed_accounts(session, name))) for name in ran]
    for name, count in waiting:
        if count:
            typer.echo(
                f"SimpleFIN ({name}): {new_accounts(count)} to set up "
                f"(open the SimpleFIN page, or run: fin sync accounts --link {name})"
            )
    for name, message in messages:
        typer.echo(f"SimpleFIN ({name}): {message}")
    if skipped:
        raise typer.Exit(code=1)


def _run_cells(link: str, item: AccountSync, names: dict[int, str]) -> tuple[str, ...]:
    pull = item.pull
    counts = (
        ("", "", "", "")
        if pull is None
        else (str(pull.inserted), str(pull.updated), str(pull.removed), str(pull.unchanged))
    )
    return (
        link,
        "" if item.account_id is None else names[item.account_id],
        item.provider_account_id,
        *counts,
        _drift(pull),
        item.problem or "",
    )


def _drift(pull: FeedPull | None) -> str:
    return "" if pull is None or pull.drift_cents is None else format_cents(pull.drift_cents)


def _balance_date(pull: FeedPull | None) -> str:
    return "" if pull is None or pull.balance_date is None else pull.balance_date.isoformat()


@app.command("status")
def status_command() -> None:
    """Show each mapped account's last pull and drift."""
    require_current_schema()
    with session_scope(get_engine()) as session:
        mappings = list_feed_accounts(session)
        names = _account_names(session)
        pulls = {
            item.account_id: (
                latest_feed_pull(session, item.account_id),
                latest_feed_pull(session, item.account_id, with_balance=True),
            )
            for item in mappings
        }
    if not mappings:
        typer.echo("No mapped accounts.")
        return
    keychain = {}
    for link in {item.link for item in mappings}:
        try:
            keychain[link] = "no" if load_access_url(link) is None else "yes"
        except SyncError:
            keychain[link] = "unknown"
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
    for item in mappings:
        last, balanced = pulls[item.account_id]
        table.add_row(
            item.link,
            names[item.account_id],
            item.provider_account_id,
            keychain[item.link],
            "never" if last is None else last.pulled_at.strftime("%Y-%m-%d %H:%M UTC"),
            _balance_date(balanced),
            _drift(balanced),
        )
    print_table(table)
