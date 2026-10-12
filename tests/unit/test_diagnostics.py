import collections
import types
from pathlib import Path

import pytest

import finances.diagnostics
from finances.config import Settings
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


def test_database_url_is_masked(tmp_settings: Settings, tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, database_url="postgresql://user:secret@host/db")
    checks = run_checks(settings)
    assert checks[3][0] == "Database URL"
    assert "secret" not in checks[3][2]
    assert "***" in checks[3][2]
