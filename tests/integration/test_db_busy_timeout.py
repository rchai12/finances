import pytest

from finances.config import get_settings
from finances.db.engine import get_engine


@pytest.mark.parametrize("kind", ["memory", "file", "configured"])
@pytest.mark.parametrize("read_only", [False, True], ids=["write", "read"])
def test_every_connection_timeout(tmp_settings, monkeypatch, tmp_path, kind, read_only):
    monkeypatch.setenv("FIN_DB_BUSY_TIMEOUT_MS", "137")
    get_settings.cache_clear()
    url = {
        "memory": "sqlite:///:memory:",
        "file": "sqlite:///" + (tmp_path / "new.db").as_posix(),
        "configured": None,
    }[kind]
    engine = get_engine(url, read_only=read_only)
    try:
        with engine.connect() as first, engine.connect() as second:
            for connection in (first, second):
                assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 137
                assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
                assert connection.exec_driver_sql("PRAGMA query_only").scalar_one() == int(
                    read_only
                )
        engine.dispose()
        with engine.connect() as fresh:
            assert fresh.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 137
    finally:
        engine.dispose()


def test_setting_overrides_url_timeout(tmp_settings, monkeypatch):
    monkeypatch.setenv("FIN_DB_BUSY_TIMEOUT_MS", "211")
    get_settings.cache_clear()
    engine = get_engine("sqlite:///:memory:?timeout=0")
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 211
    finally:
        engine.dispose()
