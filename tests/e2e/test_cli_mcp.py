import pytest

from finances.config import Settings
from tests.support import run


def test_serve_runs_on_stdio_and_prints_nothing(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = []
    monkeypatch.setattr(
        "mcp.server.mcpserver.MCPServer.run",
        lambda self, transport="stdio", **options: started.append((self.name, transport, options)),
    )
    result = run("mcp", "serve")
    assert (result.exit_code, result.stdout, result.stderr) == (0, "", "")
    assert started == [("finances", "stdio", {})]


def test_serve_takes_no_options(tmp_settings: Settings) -> None:
    result = run("mcp", "serve", "--port", "8000")
    assert result.exit_code == 2
    assert "--port" in result.stderr
