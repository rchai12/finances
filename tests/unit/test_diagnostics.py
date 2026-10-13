import collections
import types
from pathlib import Path

import pytest
from sqlalchemy import text

import finances.diagnostics
from finances.config import Settings
from finances.db.engine import get_engine
from finances.db.migrate import upgrade_to_head
from finances.diagnostics import run_checks

Version = collections.namedtuple("Version", "major minor micro")


def test_python_version_ok(tmp_settings: Settings) -> None:
    checks = run_checks(tmp_settings)
    assert checks[0][0] == "Python version"
    assert checks[0][1] is True
    assert "FAIL" not in checks[0][2]


def test_python_version_too_old(monkeypatch: pytest.MonkeyPatch, tmp_settings: Settings) -> None:
    fake_sys = types.SimpleNamespace(version_info=Version(3, 10, 0))
    monkeypatch.setattr(finances.diagnostics, "sys", fake_sys)
    checks = run_checks(tmp_settings)
    assert checks[0] == ("Python version", False, "3.10.0 FAIL")


def test_data_dir_ok(tmp_settings: Settings) -> None:
    checks = run_checks(tmp_settings)
    assert checks[2][0] == "Data dir"
    assert checks[2][1] is True
    assert checks[2][2].endswith(" OK")
    assert tmp_settings.data_dir.is_dir()
    assert not (tmp_settings.data_dir / ".fin_write_probe").exists()


def test_data_dir_unwritable(tmp_settings: Settings, tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    checks = run_checks(Settings(data_dir=blocker / "data"))
    assert checks[2][1] is False
    assert checks[2][2].endswith(" FAIL")
    assert checks[4] == ("Database schema", False, "cannot open database FAIL")


def test_database_url_is_masked(tmp_settings: Settings, tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, database_url="postgresql://user:secret@host/db")
    checks = run_checks(settings)
    assert checks[3][0] == "Database URL"
    assert "secret" not in checks[3][2]
    assert "***" in checks[3][2]


def test_there_are_five_checks_in_order(tmp_settings: Settings) -> None:
    names = [name for name, _ok, _detail in run_checks(tmp_settings)]
    assert names == [
        "Python version",
        "Environment",
        "Data dir",
        "Database URL",
        "Database schema",
    ]


def test_database_schema_fails_before_the_first_upgrade(tmp_settings: Settings) -> None:
    checks = run_checks(tmp_settings)
    assert checks[4] == ("Database schema", False, "none -> 0001 FAIL (run: fin db upgrade)")


def test_database_schema_is_ok_after_an_upgrade(tmp_settings: Settings) -> None:
    upgrade_to_head(tmp_settings.effective_database_url)
    checks = run_checks(tmp_settings)
    assert checks[4] == ("Database schema", True, "0001 OK")


def test_database_schema_shows_an_old_revision(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    upgrade_to_head(tmp_settings.effective_database_url)
    monkeypatch.setattr(finances.diagnostics, "head_revision", lambda: "0002")
    checks = run_checks(tmp_settings)
    assert checks[4] == ("Database schema", False, "0001 -> 0002 FAIL (run: fin db upgrade)")


def test_database_schema_uses_the_settings_it_is_given(
    tmp_settings: Settings, tmp_path: Path
) -> None:
    other = Settings(data_dir=tmp_path / "other")
    upgrade_to_head(other.effective_database_url)
    assert run_checks(other)[4] == ("Database schema", True, "0001 OK")
    assert run_checks(tmp_settings)[4][1] is False


def test_database_schema_reports_an_unsupported_database(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, database_url="postgresql://user:secret@host/db")
    checks = run_checks(settings)
    assert checks[4] == ("Database schema", False, "unsupported database FAIL")


def test_database_schema_reports_a_file_that_is_not_a_database(tmp_settings: Settings) -> None:
    tmp_settings.data_dir.mkdir(parents=True)
    (tmp_settings.data_dir / "finances.db").write_text("this is not a database " * 50)
    checks = run_checks(tmp_settings)
    assert checks[4] == ("Database schema", False, "cannot open database FAIL")


def test_database_schema_check_changes_no_tables(tmp_settings: Settings) -> None:
    run_checks(tmp_settings)
    engine = get_engine(tmp_settings.effective_database_url)
    with engine.connect() as connection:
        tables = connection.execute(text("SELECT name FROM sqlite_master")).all()
    engine.dispose()
    assert tables == []
