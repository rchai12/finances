import pytest
from typer.testing import CliRunner

from finances.cli import web as web_module
from finances.cli.main import app
from finances.config import Settings, get_settings

runner = CliRunner(env={"COLUMNS": "200"})


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> list[tuple[object, dict]]:
    """Replace uvicorn.run so that no server starts; remember how it was called."""
    calls: list[tuple[object, dict]] = []

    def fake_run(app: object, **options: object) -> None:
        calls.append((app, options))

    monkeypatch.setattr(web_module.uvicorn, "run", fake_run)
    return calls


def test_the_default_port_setting(tmp_settings: Settings) -> None:
    assert get_settings().web_port == 8765


def test_serve_on_the_default_port(tmp_settings: Settings, served) -> None:
    result = runner.invoke(app, ["web", "serve"])
    assert (result.exit_code, result.stdout) == (
        0,
        "Serving on http://127.0.0.1:8765 (press Ctrl+C to stop)\n",
    )
    assert len(served) == 1
    application, options = served[0]
    assert options == {
        "host": "127.0.0.1",
        "port": 8765,
        "access_log": False,
        "log_level": "warning",
    }
    assert callable(application)


def test_serve_on_a_port_from_the_settings(
    tmp_settings: Settings, served, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIN_WEB_PORT", "9123")
    get_settings.cache_clear()
    result = runner.invoke(app, ["web", "serve"])
    assert result.stdout == "Serving on http://127.0.0.1:9123 (press Ctrl+C to stop)\n"
    assert served[0][1]["port"] == 9123


def test_serve_on_a_port_given(tmp_settings: Settings, served) -> None:
    result = runner.invoke(app, ["web", "serve", "--port", "8800"])
    assert result.exit_code == 0
    assert served[0][1]["port"] == 8800
    assert served[0][1]["host"] == "127.0.0.1"


@pytest.mark.parametrize("port", ["80", "1023", "65536", "x"])
def test_a_bad_port(tmp_settings: Settings, served, port: str) -> None:
    result = runner.invoke(app, ["web", "serve", "--port", port])
    assert result.exit_code == 2
    assert served == []


def test_there_is_no_host_option(tmp_settings: Settings, served) -> None:
    result = runner.invoke(app, ["web", "serve", "--host", "0.0.0.0"])
    assert result.exit_code == 2
    assert served == []
