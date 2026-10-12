from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine

from finances.config import Settings, get_settings
from finances.db.engine import get_engine
from finances.db.migrate import upgrade_to_head

_ENV_KEYS = ("FIN_ENVIRONMENT", "FIN_DATA_DIR", "FIN_DATABASE_URL", "FIN_LOG_LEVEL")


@pytest.fixture
def tmp_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Settings]:
    """Settings whose data dir is under tmp_path, with no .env file in reach."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FIN_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    """URL of a SQLite database file under tmp_path. The file does not exist yet."""
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def db_engine(db_url: str) -> Iterator[Engine]:
    """Engine for a temporary database that has been migrated to the newest revision."""
    upgrade_to_head(db_url)
    engine = get_engine(db_url)
    yield engine
    engine.dispose()
