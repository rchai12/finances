from pathlib import Path

import pytest

from finances.config import get_settings, mask_url

_ENV_KEYS = ("FIN_ENVIRONMENT", "FIN_DATA_DIR", "FIN_DATABASE_URL", "FIN_LOG_LEVEL")


@pytest.fixture(autouse=True)
def _clear_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults() -> None:
    settings = get_settings()
    assert settings.environment == "local"
    assert settings.effective_database_url.endswith("data/finances.db")


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIN_DATA_DIR", "custom-data")
    monkeypatch.setenv("FIN_DATABASE_URL", "postgresql://user:secret@host/db")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.data_dir == Path("custom-data")
    assert settings.effective_database_url == "postgresql://user:secret@host/db"


def test_mask_url_hides_password() -> None:
    masked = mask_url("postgresql://user:secret@host/db")
    assert "secret" not in masked
    assert "***" in masked


def test_mask_url_without_password_is_unchanged() -> None:
    url = "sqlite:///data/finances.db"
    assert mask_url(url) == url
