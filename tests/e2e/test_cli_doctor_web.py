import keyring
import keyring.backend
import keyring.errors
import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings, get_settings
from finances.web.login import set_password
from tests.support import table_rows

runner = CliRunner(env={"COLUMNS": "200"})


def doctor() -> tuple[int, list[list[str]]]:
    assert runner.invoke(app, ["db", "upgrade"]).exit_code == 0
    result = runner.invoke(app, ["doctor"])
    return result.exit_code, table_rows(result.stdout)[-3:]


def test_doctor_without_a_password(tmp_settings: Settings) -> None:
    assert doctor() == (
        1,
        [
            ["Web address", "http://127.0.0.1:8765 (loopback only)"],
            ["Web password", "not set FAIL (run: fin web password)"],
            ["Tailscale name", "not set (this Mac only)"],
        ],
    )


def test_doctor_ready_for_tailscale(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIN_WEB_HOSTNAME", "mac.tail1234.ts.net")
    get_settings.cache_clear()
    set_password("correct horse battery", None)
    assert doctor() == (
        0,
        [
            ["Web address", "http://127.0.0.1:8765 (loopback only)"],
            ["Web password", "set OK"],
            ["Tailscale name", "mac.tail1234.ts.net"],
        ],
    )


class Broken(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringLocked("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.PasswordSetError("no")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.PasswordDeleteError("no")


def test_doctor_with_a_broken_keychain(tmp_settings: Settings) -> None:
    previous = keyring.get_keyring()
    keyring.set_keyring(Broken())
    try:
        code, rows = doctor()
    finally:
        keyring.set_keyring(previous)
    assert (code, rows[1]) == (1, ["Web password", "cannot read the Keychain FAIL"])
