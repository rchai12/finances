from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings, get_settings
from finances.db.migrate import head_revision

runner = CliRunner(env={"COLUMNS": "200"})
HEAD = head_revision()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_doctor_creates_data_dir(tmp_settings: Settings) -> None:
    result = runner.invoke(app, ["doctor"])
    assert tmp_settings.data_dir.is_dir()
    assert "Data dir" in result.stdout


def test_doctor_exits_1_when_a_check_fails(monkeypatch, tmp_settings) -> None:
    monkeypatch.setattr(
        "finances.cli.main.run_checks",
        lambda settings: [("Probe", False, "bad FAIL")],
    )

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "Probe" in result.stdout


def test_doctor_fails_before_the_first_upgrade(tmp_settings: Settings) -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "Database schema" in result.stdout
    assert f"none -> {HEAD} FAIL (run: fin db upgrade)" in result.stdout


def test_db_upgrade_reports_the_revision(tmp_settings: Settings) -> None:
    result = runner.invoke(app, ["db", "upgrade"])
    assert result.exit_code == 0
    assert f"Database is at revision {HEAD}" in result.stdout
    assert (tmp_settings.data_dir / "finances.db").is_file()


def test_db_upgrade_prints_the_revision_it_was_given(tmp_settings: Settings, monkeypatch) -> None:
    monkeypatch.setattr("finances.cli.db.upgrade_to_head", lambda: "0007")
    result = runner.invoke(app, ["db", "upgrade"])
    assert result.exit_code == 0
    assert result.stdout == "Database is at revision 0007\n"


def test_db_upgrade_twice_is_fine(tmp_settings: Settings) -> None:
    runner.invoke(app, ["db", "upgrade"])
    result = runner.invoke(app, ["db", "upgrade"])
    assert result.exit_code == 0
    assert f"Database is at revision {HEAD}" in result.stdout


def test_doctor_passes_after_an_upgrade(tmp_settings: Settings) -> None:
    runner.invoke(app, ["db", "upgrade"])
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert f"{HEAD} OK" in result.stdout


def test_db_upgrade_reports_an_unsupported_database(tmp_settings: Settings, monkeypatch) -> None:
    monkeypatch.setenv("FIN_DATABASE_URL", "postgresql://user:secret@host/db")
    get_settings.cache_clear()
    result = runner.invoke(app, ["db", "upgrade"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.stderr == "Error: only SQLite databases are supported\n"
    assert "secret" not in result.output
