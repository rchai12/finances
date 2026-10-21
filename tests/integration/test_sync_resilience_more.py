import keyring
import keyring.backend
import keyring.errors
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import (
    create_account,
    list_sync_failures,
    map_feed_account,
    record_sync_failure,
)
from finances.domain.models import SyncFailure
from finances.sync import transport
from finances.sync.links import KEYCHAIN_SERVICE
from finances.sync.runner import KEYCHAIN_FAILED, RETRY_WAITS, run_links
from finances.sync.simplefin import AggregatorUnreachable
from finances.web.app import create_app
from tests.integration.test_sync_resilience import (
    NOW,
    TODAY,
    UNREACHABLE,
    Bridge,
    failures,
    sync,
)
from tests.support import WEB_PORT, post, run

ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"


class BrokenKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringError("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.KeyringError("locked")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.KeyringError("locked")


def unreachable(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    raise AggregatorUnreachable(UNREACHABLE)


def test_a_keychain_failure_is_remembered(db_engine: Engine) -> None:
    previous = keyring.get_keyring()
    keyring.set_keyring(BrokenKeyring())
    try:
        runs, waits, _ = sync(db_engine, unreachable, retry_waits=RETRY_WAITS)
    finally:
        keyring.set_keyring(previous)
    assert [(run.failure, run.cause) for run in runs] == [
        (KEYCHAIN_FAILED, "could not use the system keychain")
    ]
    assert waits == []
    assert failures(db_engine) == [SyncFailure("alex", NOW, "could not use the system keychain")]


def test_retries_without_an_on_retry(db_engine: Engine, keychain) -> None:
    keychain.passwords[(KEYCHAIN_SERVICE, "alex")] = ALEX
    waits: list[float] = []
    runs = run_links(
        db_engine,
        ["alex"],
        today=TODAY,
        transport=Bridge(failures=1),
        retry_waits=(30,),
        sleep=waits.append,
        now=lambda: NOW,
    )
    assert [run.failure for run in runs] == [None]
    assert waits == [30]


def test_a_link_that_is_not_set_up_is_not_remembered(db_engine: Engine) -> None:
    runs, waits, _ = sync(db_engine, unreachable, links=("bob",), retry_waits=RETRY_WAITS)
    assert [run.failure for run in runs] == ["not set up"]
    assert waits == []
    assert failures(db_engine) == []


def test_sync_now_does_not_wait(
    tmp_settings: Settings, keychain, monkeypatch: pytest.MonkeyPatch
) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        map_feed_account(session, card.id, "ACT-1", "alex")
    engine.dispose()
    keychain.passwords[(KEYCHAIN_SERVICE, "alex")] = ALEX
    waits: list[float] = []
    monkeypatch.setattr("time.sleep", waits.append)
    monkeypatch.setattr(transport, "urllib_transport", unreachable)
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/sync")
    response = post(client, "/sync/run")
    assert response.status_code == 200
    assert waits == []
    found_engine = get_engine()
    with session_scope(found_engine) as session:
        found = list_sync_failures(session)
    found_engine.dispose()
    assert [(item.link, item.message) for item in found] == [("alex", UNREACHABLE)]


def test_record_sync_failure_cuts_the_message(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        record_sync_failure(session, "alex", NOW, "x" * 300)
    assert failures(db_engine) == [SyncFailure("alex", NOW, "x" * 200)]


def test_status_prints_failures_by_link(tmp_settings: Settings) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        map_feed_account(session, card.id, "ACT-1", "alex")
        other = create_account(session, "Test Checking", "Test Bank", "checking")
        map_feed_account(session, other.id, "ACT-1", "sam")
        record_sync_failure(session, "sam", NOW, "aggregator answered with an error")
        record_sync_failure(session, "alex", NOW, UNREACHABLE)
    engine.dispose()
    lines = [
        line
        for line in run("sync", "status").stdout.splitlines()
        if line.startswith("Last failure")
    ]
    stamp = NOW.strftime("%Y-%m-%d %H:%M UTC")
    assert lines == [
        f"Last failure of link alex: {stamp}: {UNREACHABLE}.",
        f"Last failure of link sam: {stamp}: aggregator answered with an error.",
    ]
