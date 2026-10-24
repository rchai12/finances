"""The `fin web` commands."""

from typing import Annotated

import typer
import uvicorn

from finances.cli.common import fail
from finances.config import get_settings
from finances.web.app import HOST, create_app
from finances.web.login import check_password, has_password, set_password, unlock

app = typer.Typer(help="Serve the web interface on this machine.", no_args_is_help=True)


@app.command("password")
def password_command() -> None:
    """Set or change the household password."""
    current: str | None = None
    if has_password():
        current = typer.prompt("Current password", hide_input=True)
        if not check_password(current):
            fail("the current password is wrong")
    new = typer.prompt("New password", hide_input=True, confirmation_prompt=True)
    try:
        set_password(new, current)
    except ValueError as error:
        fail(str(error))
    typer.echo("Password saved; every session has ended.")


@app.command("unlock")
def unlock_command() -> None:
    """Clear the login lockout."""
    given = typer.prompt("Password", hide_input=True)
    try:
        unlock(given)
    except ValueError as error:
        fail(str(error))
    typer.echo("The login is unlocked.")


@app.command()
def serve(
    port: Annotated[
        int | None,
        typer.Option("--port", min=1024, max=65535, help="Port on 127.0.0.1 to listen on."),
    ] = None,
) -> None:
    """Serve the web interface at http://127.0.0.1:PORT until Ctrl+C."""
    if not has_password():
        fail("set a password first: fin web password")
    chosen = get_settings().web_port if port is None else port
    typer.echo(f"Serving on http://{HOST}:{chosen} (press Ctrl+C to stop)")
    uvicorn.run(create_app(chosen), host=HOST, port=chosen, access_log=False, log_level="warning")
