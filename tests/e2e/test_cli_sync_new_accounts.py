import base64
import json
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import set_feed_account_ignored
from finances.sync import transport

runner = CliRunner(env={"COLUMNS": "200"})
SERVICE = "finances-simplefin"
ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"
SAM = "https://sam-user:sam-pass@bridge.simplefin.org/simplefin"
HINT = "(open the SimpleFIN page, or run: fin sync accounts --link {})"


def run(*args: str):
    return runner.invoke(app, list(args))


def key(access: str) -> str:
    user, password = access.split("//")[1].split("@")[0].split(":")
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


class Bridge:
    """A fake SimpleFIN Bridge: each access URL has its list of accounts."""

    def __init__(self) -> None:
        self.answers: dict[str, list[tuple[str, str]]] = {}
        self.asked: list[str] = []

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.asked.append(headers["Authorization"])
        noon = int(datetime.now(UTC).replace(hour=12, minute=0, second=0).timestamp())
        accounts = [
            {
                "id": feed_id,
                "name": name,
                "conn_id": "C",
                "currency": "USD",
                "balance": "-1.00",
                "balance-date": noon,
                "transactions": [],
            }
            for feed_id, name in self.answers[headers["Authorization"]]
        ]
        body = {
            "errlist": [{"code": "con.auth", "msg": "Probe note"}],
            "connections": [{"conn_id": "C", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}],
            "accounts": accounts,
        }
        return 200, json.dumps(body).encode()


@pytest.fixture
def bridge(monkeypatch: pytest.MonkeyPatch, keychain) -> Bridge:
    fake = Bridge()
    monkeypatch.setattr(transport, "urllib_transport", fake)
    keychain.passwords[(SERVICE, "alex")] = ALEX
    keychain.passwords[(SERVICE, "sam")] = SAM
    return fake


@pytest.fixture
def mapped(tmp_settings: Settings, bridge: Bridge) -> Bridge:
    """Alex's link maps ACT-1 to Test Card."""
    assert run("db", "upgrade").exit_code == 0
    details = ["--institution", "Probe Bank", "--type", "credit_card", "--last4", "1111"]
    assert run("accounts", "add", "--name", "Test Card", *details).exit_code == 0
    made = run("sync", "map", "--account", "Test Card", "--feed-account", "ACT-1", "--link", "alex")
    assert made.exit_code == 0
    return bridge


def tail(output: str) -> list[str]:
    """The lines after the table."""
    lines = output.splitlines()
    return lines[max(index for index, line in enumerate(lines) if line.startswith("└")) + 1 :]


def test_a_sync_names_the_new_accounts_before_simplefins_messages(mapped: Bridge) -> None:
    mapped.answers[key(ALEX)] = [("ACT-1", "Card"), ("ACT-2", "Visa 9876"), ("ACT-3", "Savings")]
    result = run("sync", "run")
    assert result.exit_code == 0
    assert tail(result.stdout) == [
        "SimpleFIN (alex): 2 new accounts to set up " + HINT.format("alex"),
        "SimpleFIN (alex): Probe note",
    ]


def test_one_new_account(mapped: Bridge) -> None:
    mapped.answers[key(ALEX)] = [("ACT-1", "Card"), ("ACT-2", "Visa 9876")]
    assert tail(run("sync", "run").stdout)[0] == (
        "SimpleFIN (alex): 1 new account to set up " + HINT.format("alex")
    )


def test_no_line_when_everything_is_mapped_or_not_tracked(mapped: Bridge) -> None:
    mapped.answers[key(ALEX)] = [("ACT-1", "Card")]
    assert tail(run("sync", "run").stdout) == ["SimpleFIN (alex): Probe note"]
    mapped.answers[key(ALEX)] = [("ACT-1", "Card"), ("ACT-2", "Visa 9876")]
    run("sync", "run")
    engine = get_engine()
    with session_scope(engine) as session:
        set_feed_account_ignored(session, "alex", "ACT-2", True)
    engine.dispose()
    assert tail(run("sync", "run").stdout) == ["SimpleFIN (alex): Probe note"]


def test_a_link_with_only_new_accounts_is_synced_too(mapped: Bridge) -> None:
    mapped.answers[key(ALEX)] = [("ACT-1", "Card")]
    mapped.answers[key(SAM)] = [("SAM-1", "Sam Checking")]
    first = run("sync", "run")
    assert key(SAM) not in mapped.asked
    assert "sam" not in first.stdout
    assert run("sync", "run", "--link", "sam").exit_code == 0
    mapped.asked.clear()
    result = run("sync", "run")
    assert sorted(set(mapped.asked)) == sorted({key(ALEX), key(SAM)})
    assert "SimpleFIN (sam): 1 new account to set up " + HINT.format("sam") in result.stdout


def test_only_links_that_ran_are_counted(mapped: Bridge) -> None:
    mapped.answers[key(ALEX)] = [("ACT-1", "Card"), ("ACT-2", "Visa 9876")]
    mapped.answers[key(SAM)] = [("SAM-1", "Sam Checking")]
    run("sync", "run", "--link", "sam")
    result = run("sync", "run", "--link", "alex")
    assert "SimpleFIN (alex): 1 new account" in result.stdout
    assert "SimpleFIN (sam)" not in result.stdout
