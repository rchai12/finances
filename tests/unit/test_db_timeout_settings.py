import pytest
from pydantic import ValidationError

from finances.config import Settings, get_settings


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FIN_DB_BUSY_TIMEOUT_MS", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default():
    assert Settings(_env_file=None).db_busy_timeout_ms == 30000


@pytest.mark.parametrize("value", [0, 17, 120000])
def test_valid_bounds(value):
    assert Settings(_env_file=None, db_busy_timeout_ms=value).db_busy_timeout_ms == value


@pytest.mark.parametrize("value", [-1, 120001])
def test_invalid_bounds(value):
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, db_busy_timeout_ms=value)
    assert caught.value.errors()[0]["loc"] == ("db_busy_timeout_ms",)


def test_environment(monkeypatch):
    monkeypatch.setenv("FIN_DB_BUSY_TIMEOUT_MS", "271")
    get_settings.cache_clear()
    assert get_settings().db_busy_timeout_ms == 271


def test_shared_fixture_clears_timeout_environment():
    from tests import conftest

    assert "FIN_DB_BUSY_TIMEOUT_MS" in conftest._ENV_KEYS
