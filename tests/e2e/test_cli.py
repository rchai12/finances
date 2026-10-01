from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import get_settings

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_doctor_creates_data_dir(monkeypatch, tmp_path) -> None:
    data_dir = tmp_path / "fin-data"
    monkeypatch.setenv("FIN_DATA_DIR", str(data_dir))
    get_settings.cache_clear()

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert data_dir.is_dir()
    get_settings.cache_clear()
