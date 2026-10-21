import json
import re
from datetime import UTC, datetime

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.repositories import create_account, map_feed_account
from finances.sync import transport
from finances.sync.links import KEYCHAIN_SERVICE
from finances.sync.simplefin import AggregatorUnreachable
from tests.support import run, table_rows

ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"
EMPTY = json.dumps({"errlist": [], "connections": [], "accounts": []}).encode()
FAILED = re.compile(
    r"Last failure of link alex: \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC:"
    r" could not reach the aggregator\."
)


def unreachable(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    raise AggregatorUnreachable("could not reach the aggregator")


def answers(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    return 200, EMPTY


@pytest.fixture
def linked(tmp_settings: Settings, keychain, monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Test Card mapped under link alex; waits are recorded instead of slept."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        map_feed_account(session, card.id, "ACT-1", "alex")
    engine.dispose()
    keychain.passwords[(KEYCHAIN_SERVICE, "alex")] = ALEX
    waits: list[float] = []
    monkeypatch.setattr("time.sleep", waits.append)
    return waits


def test_the_daily_sync_tries_again_then_remembers_the_failure(
    linked: list[float], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(transport, "urllib_transport", unreachable)
    result = run("sync", "run")
    assert result.exit_code == 1
    assert result.stderr.splitlines() == [
        "link alex: could not reach the aggregator; trying again in 30 seconds.",
        "link alex: could not reach the aggregator; trying again in 60 seconds.",
        "link alex: could not reach the aggregator; trying again in 120 seconds.",
        "Error: link alex: could not reach the aggregator",
    ]
    assert linked == [30, 60, 120]
    status = run("sync", "status").stdout
    assert [line for line in status.splitlines() if FAILED.fullmatch(line)] != []
    today = datetime.now(UTC).date().isoformat()
    health = table_rows(run("health").stdout)
    assert [
        "sync",
        "",
        f"The last sync of link alex failed on {today}: could not reach the aggregator.",
        "Run fin sync run; if it fails, link SimpleFIN again (docs/sync-setup.md).",
    ] in health


def test_a_good_sync_clears_it(linked: list[float], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transport, "urllib_transport", unreachable)
    run("sync", "run")
    monkeypatch.setattr(transport, "urllib_transport", answers)
    assert run("sync", "run").exit_code == 0
    assert "Last failure" not in run("sync", "status").stdout
    assert not any(row[2].startswith("The last sync") for row in table_rows(run("health").stdout))
