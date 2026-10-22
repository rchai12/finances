"""The `fin mcp` commands."""

import typer

from finances.mcp_server import server as mcp_server

app = typer.Typer(help="Serve the agent's tools over stdio.", no_args_is_help=True)


@app.command()
def serve() -> None:
    mcp_server.serve()
