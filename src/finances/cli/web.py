"""The `fin web` commands."""

from typing import Annotated

import typer
import uvicorn

from finances.config import get_settings
from finances.web.app import HOST, create_app

app = typer.Typer(help="Serve the web interface on this machine.", no_args_is_help=True)


@app.command()
def serve(
    port: Annotated[
        int | None,
        typer.Option("--port", min=1024, max=65535, help="Port on 127.0.0.1 to listen on."),
    ] = None,
) -> None:
    """Serve the web interface at http://127.0.0.1:PORT until Ctrl+C."""
    chosen = get_settings().web_port if port is None else port
    typer.echo(f"Serving on http://{HOST}:{chosen} (press Ctrl+C to stop)")
    uvicorn.run(create_app(chosen), host=HOST, port=chosen, access_log=False, log_level="warning")
