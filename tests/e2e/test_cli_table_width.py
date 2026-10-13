from pathlib import Path

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import create_account
from finances.ingest.service import import_statement

NAME = "Test Card With A Long Name " + "X" * 90
FILE = "statement-" + "y" * 120 + ".pdf"
ENVIRONMENTS = [
    {"COLUMNS": "20"},
    {"COLUMNS": "80"},
    {"COLUMNS": "20", "TERM": "dumb"},
    {"COLUMNS": "30", "LINES": "10", "TERM": "xterm-256color"},
]


def rows(output: str) -> list[list[str]]:
    lines = [line for line in output.splitlines() if line.startswith("│")]
    return [[cell.strip() for cell in line.split("│")[1:-1]] for line in lines]


@pytest.fixture
def inbox(tmp_settings, fake_bank, fake_statement_pdf) -> Path:
    """A database with one long-named account and one imported statement, and a folder."""
    upgrade_to_head()
    content = fake_statement_pdf()
    with session_scope(get_engine()) as session:
        create_account(session, NAME, "Fake Bank", "credit_card", last4="1111")
        result = import_statement(session, filename=FILE, content=content)
    assert result.message == "imported"
    folder = tmp_settings.data_dir / "inbox"
    folder.mkdir(parents=True)
    (folder / FILE).write_bytes(content)
    return folder


@pytest.mark.parametrize("env", ENVIRONMENTS)
def test_every_table_keeps_each_row_on_one_line(env: dict[str, str], inbox: Path) -> None:
    runner = CliRunner(env=env)

    result = runner.invoke(app, ["accounts", "list"])
    assert result.exit_code == 0
    assert rows(result.output) == [[NAME, "Fake Bank", "credit_card", "••1111", "yes"]]

    result = runner.invoke(app, ["statements", "list"])
    assert result.exit_code == 0
    assert [cells[:3] for cells in rows(result.output)] == [[NAME, FILE, "fake_bank"]]

    result = runner.invoke(app, ["transactions", "list"])
    assert result.exit_code == 0
    found = rows(result.output)
    assert len(found) == 4
    assert [(len(cells), cells[1]) for cells in found] == [(6, NAME)] * 4

    result = runner.invoke(app, ["import", "folder", str(inbox)])
    assert result.exit_code == 0
    found = rows(result.output)
    assert len(found) == 1
    assert found[0][0].endswith(FILE)
    assert found[0][-1] == "already imported"

    result = runner.invoke(app, ["doctor"])
    lines = [line for line in result.output.splitlines() if line.startswith(("│", "┃"))]
    assert len(lines) > 2
    assert len({len(line) for line in lines}) == 1
