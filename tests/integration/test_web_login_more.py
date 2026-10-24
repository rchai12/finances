from datetime import UTC, datetime, timedelta

import keyring
import keyring.errors
import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.web.login import (
    KEYCHAIN_SERVICE,
    Attempt,
    attempt,
    check_password,
    set_password,
)

RIGHT = "correct horse battery"
T0 = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
runner = CliRunner(env={"COLUMNS": "200"})


def test_the_stored_hash_uses_scrypt_and_a_new_salt_each_time() -> None:
    set_password(RIGHT, None)
    first = keyring.get_password(KEYCHAIN_SERVICE, "password")
    assert first is not None and first.startswith("scrypt$16384$8$1$")
    set_password("another long password", RIGHT)
    second = keyring.get_password(KEYCHAIN_SERVICE, "password")
    assert second is not None and second.startswith("scrypt$16384$8$1$")
    assert first.split("$")[4] != second.split("$")[4]


def test_check_password_neither_counts_nor_locks() -> None:
    set_password(RIGHT, None)
    for _ in range(10):
        assert check_password("wrong") is False
    assert attempt(RIGHT, T0) == Attempt(True, None)


def test_a_keychain_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise keyring.errors.KeyringError("no")

    monkeypatch.setattr(keyring, "set_password", boom)
    with pytest.raises(ValueError) as raised:
        set_password(RIGHT, None)
    assert str(raised.value) == "could not use the system keychain"
    monkeypatch.setattr(keyring, "get_password", boom)
    with pytest.raises(ValueError) as raised:
        attempt(RIGHT, T0)
    assert str(raised.value) == "could not use the system keychain"


def test_a_lock_that_ended_exactly_now_is_over() -> None:
    set_password(RIGHT, None)
    for _ in range(5):
        attempt("wrong", T0)
    end = T0 + timedelta(hours=1)
    assert attempt(RIGHT, end) == Attempt(True, None)


def test_the_first_password_does_not_ask_for_a_current_one(tmp_settings: Settings) -> None:
    result = runner.invoke(app, ["web", "password"], input=f"{RIGHT}\n{RIGHT}\n")
    assert result.exit_code == 0
    assert "Current password" not in result.output
