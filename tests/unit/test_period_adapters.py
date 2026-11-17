from datetime import date, datetime

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from typer.exceptions import Exit

from finances.cli import reports as cli
from finances.mcp_server import tools
from finances.web.routes import reports as web


@pytest.mark.parametrize(
    ("month", "start", "message"),
    [
        ("", None, "Error: month must be a year and month, like 2026-05\n"),
        ("bad", datetime(2024, 1, 1), "Error: give --month, or --from and --to, not both\n"),
        (None, datetime(2024, 1, 1), "Error: give both --from and --to\n"),
    ],
    ids=["empty", "conflict", "incomplete"],
)
def test_cli_period_refusals(month, start, message, capsys):
    with pytest.raises(Exit) as stopped:
        cli._range(month, start, None)
    assert stopped.value.exit_code == 1
    assert capsys.readouterr().err == message


@pytest.mark.parametrize(
    ("month", "start", "end", "message"),
    [
        ("bad", "bad", "", "give a month, or from and to, not both"),
        ("", "bad", "", "give both from and to"),
        ("", "bad", "2024-02-01", "from must be a date as YYYY-MM-DD"),
    ],
    ids=["conflict", "incomplete-before-date", "bad-day"],
)
def test_web_period_refusals(month, start, end, message):
    with pytest.raises(ValueError) as stopped:
        web._spending_range({"month": month, "start": start, "end": end})
    assert str(stopped.value) == message


def test_web_empty_month_defaults(monkeypatch):
    monkeypatch.setattr(web.web_app, "_today", lambda: date(2024, 2, 15))
    assert web._spending_range({"month": "", "start": "", "end": ""}) == (
        date(2024, 2, 1),
        date(2024, 2, 29),
    )


def test_mcp_bad_month_keeps_tool_error():
    with pytest.raises(ToolError) as stopped:
        tools._month_start("bad")
    assert str(stopped.value) == "month must be a year and month, like 2026-05"
