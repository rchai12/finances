from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from finances import __version__
from finances.config import get_settings
from finances.diagnostics import run_checks
from finances.log import setup_logging

app = typer.Typer(add_completion=False)
console = Console()


@app.callback(invoke_without_command=True)
def main(
    version: Annotated[
        bool,
        typer.Option("--version", help="Show the version and exit."),
    ] = False,
) -> None:
    setup_logging(get_settings().log_level)
    if version:
        typer.echo(f"finances {__version__}")
        raise typer.Exit()


@app.command()
def doctor() -> None:
    checks = run_checks(get_settings())
    table = Table()
    table.add_column("Check")
    table.add_column("Result")
    for name, _ok, detail in checks:
        table.add_row(name, detail)
    console.print(table)
    if any(not ok for _name, ok, _detail in checks):
        raise typer.Exit(code=1)
