from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

import finances.cli.web as web_module
from finances.cli.main import app
from finances.config import Settings
from finances.web.login import Attempt, attempt, set_password

RIGHT = "correct horse battery"
runner = CliRunner(env={"COLUMNS": "200"})


def run(*args: str, given: str = ""):
    return runner.invoke(app, list(args), input=given)


def last_line(text: str) -> str:
    return text.strip().splitlines()[-1]


def test_the_first_password(tmp_settings: Settings) -> None:
    result = run("web", "password", given=f"{RIGHT}\n{RIGHT}\n")
    assert result.exit_code == 0
    assert last_line(result.stdout) == "Password saved; every session has ended."
    assert attempt(RIGHT, datetime(2026, 10, 24, tzinfo=UTC)) == Attempt(True, None)


def test_a_change_needs_the_current_password(tmp_settings: Settings) -> None:
    set_password(RIGHT, None)
    wrong = run("web", "password", given="not the password\n")
    assert (wrong.exit_code, wrong.stderr) == (1, "Error: the current password is wrong\n")
    right = run("web", "password", given=f"{RIGHT}\nanother long one\nanother long one\n")
    assert last_line(right.stdout) == "Password saved; every session has ended."


def test_a_short_password(tmp_settings: Settings) -> None:
    result = run("web", "password", given="too short\ntoo short\n")
    assert (result.exit_code, result.stderr) == (1, "Error: a password is 12 to 200 characters\n")


@pytest.mark.parametrize(
    ("ready", "given", "code", "out"),
    [
        (False, f"{RIGHT}\n", 1, "Error: no password is set; run fin web password\n"),
        (True, "not the password\n", 1, "Error: wrong password\n"),
    ],
)
def test_unlock_refused(
    tmp_settings: Settings, ready: bool, given: str, code: int, out: str
) -> None:
    if ready:
        set_password(RIGHT, None)
    result = run("web", "unlock", given=given)
    assert (result.exit_code, result.stderr) == (code, out)


def test_unlock(tmp_settings: Settings) -> None:
    set_password(RIGHT, None)
    for _ in range(5):
        attempt("wrong", datetime(2026, 10, 24, tzinfo=UTC))
    result = run("web", "unlock", given=f"{RIGHT}\n")
    assert (result.exit_code, last_line(result.stdout)) == (0, "The login is unlocked.")
    assert attempt(RIGHT, datetime(2026, 10, 24, tzinfo=UTC)) == Attempt(True, None)


def test_serve_needs_a_password(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    started = []
    monkeypatch.setattr(web_module.uvicorn, "run", lambda *a, **k: started.append(a))
    result = run("web", "serve")
    assert (result.exit_code, result.stderr, result.stdout) == (
        1,
        "Error: set a password first: fin web password\n",
        "",
    )
    assert started == []
