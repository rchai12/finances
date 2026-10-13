import importlib
import io

import pytest
from rich.console import Console
from rich.table import Table

from finances.cli.common import print_table

LONG = " ".join(["ACME WIDGET"] * 30)
CLI_MODULES = ["accounts", "common", "db", "importing", "listing", "main"]


def wide_table() -> Table:
    table = Table()
    table.add_column("Name")
    table.add_column("Note")
    table.add_row("first", LONG)
    table.add_row("second", "short")
    return table


def rows(output: str) -> list[list[str]]:
    lines = [line for line in output.splitlines() if line.startswith("│")]
    return [[cell.strip() for cell in line.split("│")[1:-1]] for line in lines]


def terminal(width: int, term: str = "xterm-256color") -> tuple[Console, io.StringIO]:
    stream = io.StringIO()
    console = Console(
        file=stream, force_terminal=True, width=width, color_system=None, _environ={"TERM": term}
    )
    return console, stream


def test_without_a_terminal_every_row_is_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    print_table(wide_table())
    output = capsys.readouterr().out
    assert rows(output) == [["first", LONG], ["second", "short"]]
    assert len(output.splitlines()) == 6
    assert len({len(line) for line in output.splitlines()}) == 1


@pytest.mark.parametrize("columns", ["20", "80", "200", "5000"])
def test_without_a_terminal_columns_is_not_used(
    columns: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COLUMNS", columns)
    print_table(wide_table())
    output = capsys.readouterr().out
    assert rows(output) == [["first", LONG], ["second", "short"]]
    assert len(output.splitlines()[0]) == len(LONG) + 13


def test_without_a_terminal_the_table_is_as_wide_as_its_content(
    capsys: pytest.CaptureFixture[str],
) -> None:
    table = Table()
    table.add_column("A")
    table.add_row("xyz")
    print_table(table)
    assert capsys.readouterr().out.splitlines() == [
        "┏━━━━━┓",
        "┃ A   ┃",
        "┡━━━━━┩",
        "│ xyz │",
        "└─────┘",
    ]


def test_without_a_terminal_there_are_no_escape_codes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TERM", "xterm-256color")
    print_table(wide_table())
    assert "\x1b" not in capsys.readouterr().out


def test_a_dumb_terminal_gets_every_row_on_one_line() -> None:
    console, stream = terminal(40, term="dumb")
    print_table(wide_table(), console)
    assert rows(stream.getvalue()) == [["first", LONG], ["second", "short"]]


def test_a_console_that_is_not_a_terminal_gets_every_row_on_one_line() -> None:
    stream = io.StringIO()
    print_table(wide_table(), Console(file=stream, width=40))
    assert rows(stream.getvalue()) == [["first", LONG], ["second", "short"]]


@pytest.mark.parametrize("width", [40, 72, 120])
def test_in_a_terminal_the_table_fits_the_terminal(width: int) -> None:
    console, stream = terminal(width)
    print_table(wide_table(), console)
    lines = stream.getvalue().splitlines()
    assert {len(line) for line in lines} == {width}
    assert len(lines) > 6
    words = " ".join(cells[1] for cells in rows(stream.getvalue())).split()
    assert words == [*LONG.split(), "short"]


def test_in_a_wide_terminal_the_table_is_not_stretched() -> None:
    console, stream = terminal(5000)
    print_table(wide_table(), console)
    assert len(stream.getvalue().splitlines()[0]) == len(LONG) + 13


def test_the_output_goes_to_the_given_console(capsys: pytest.CaptureFixture[str]) -> None:
    console, stream = terminal(40)
    print_table(wide_table(), console)
    stream_two = io.StringIO()
    print_table(wide_table(), Console(file=stream_two))
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "")
    assert stream.getvalue() != ""
    assert stream_two.getvalue() != ""


@pytest.mark.parametrize("name", CLI_MODULES)
def test_no_cli_module_keeps_a_console(name: str) -> None:
    module = importlib.import_module(f"finances.cli.{name}")
    assert not [key for key, value in vars(module).items() if isinstance(value, Console)]
