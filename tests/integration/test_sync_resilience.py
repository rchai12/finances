import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine

from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import list_sync_failures, record_sync_failure
from finances.domain.models import SyncFailure
from finances.sync.links import KEYCHAIN_SERVICE
from finances.sync.runner import AGGREGATOR_FAILED, RETRY_WAITS, run_links
from finances.sync.simplefin import AggregatorUnreachable

TODAY = date(2026, 10, 20)
NOW = datetime(2026, 10, 20, 7, 0, 5, tzinfo=UTC)
ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"
SAM = "https://sam-user:sam-pass@bridge.simplefin.org/simplefin"
EMPTY = json.dumps({"errlist": [], "connections": [], "accounts": []}).encode()
UNREACHABLE = "could not reach the aggregator"


class Bridge:
    """A fake SimpleFIN: it fails the first `failures` requests as `failure`, then answers."""

    def __init__(self, failures: int = 0, failure: str = "unreachable") -> None:
        self.failures = failures
        self.failure = failure
        self.calls = 0

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls += 1
        if self.calls <= self.failures:
            if self.failure == "unreachable":
                raise AggregatorUnreachable(UNREACHABLE)
            return {"error": 500, "revoked": 403}[self.failure], b""
        return 200, EMPTY


@pytest.fixture
def engine(db_url: str, keychain) -> Engine:
    upgrade_to_head(db_url)
    keychain.passwords[(KEYCHAIN_SERVICE, "alex")] = ALEX
    keychain.passwords[(KEYCHAIN_SERVICE, "sam")] = SAM
    found = get_engine(db_url)
    yield found
    found.dispose()


def failures(engine: Engine) -> list[SyncFailure]:
    with session_scope(engine) as session:
        return list_sync_failures(session)


def sync(engine: Engine, bridge, links=("alex",), **options):
    waits: list[float] = []
    retries: list[tuple[str, int]] = []
    runs = run_links(
        engine,
        list(links),
        today=TODAY,
        transport=bridge,
        sleep=waits.append,
        on_retry=lambda link, seconds: retries.append((link, seconds)),
        now=lambda: NOW,
        **options,
    )
    return runs, waits, retries


def test_the_waits() -> None:
    assert RETRY_WAITS == (30, 60, 120)


def test_unreachable_twice_then_answered(engine: Engine) -> None:
    bridge = Bridge(failures=2)
    runs, waits, retries = sync(engine, bridge, retry_waits=RETRY_WAITS)
    assert [run.failure for run in runs] == [None]
    assert runs[0].report is not None
    assert (bridge.calls, waits, retries) == (3, [30, 60], [("alex", 30), ("alex", 60)])
    assert failures(engine) == []


def test_unreachable_every_time(engine: Engine) -> None:
    bridge = Bridge(failures=99)
    runs, waits, retries = sync(engine, bridge, retry_waits=RETRY_WAITS)
    assert [(run.failure, run.cause) for run in runs] == [(AGGREGATOR_FAILED, UNREACHABLE)]
    assert (bridge.calls, waits) == (4, [30, 60, 120])
    assert failures(engine) == [SyncFailure("alex", NOW, UNREACHABLE)]


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("error", "aggregator answered with an error"),
        ("revoked", "aggregator access was revoked or is wrong"),
    ],
)
def test_an_answer_with_an_error_is_not_tried_again(
    engine: Engine, failure: str, message: str
) -> None:
    bridge = Bridge(failures=99, failure=failure)
    runs, waits, _ = sync(engine, bridge, retry_waits=RETRY_WAITS)
    assert [run.cause for run in runs] == [message]
    assert (bridge.calls, waits) == (1, [])
    assert failures(engine) == [SyncFailure("alex", NOW, message)]


def test_without_waits_nothing_is_tried_again(engine: Engine) -> None:
    bridge = Bridge(failures=99)
    runs, waits, _ = sync(engine, bridge)
    assert [run.cause for run in runs] == [UNREACHABLE]
    assert (bridge.calls, waits) == (1, [])
    assert failures(engine) == [SyncFailure("alex", NOW, UNREACHABLE)]


def test_a_good_sync_clears_the_links_failure_only(engine: Engine) -> None:
    earlier = datetime(2026, 10, 19, 7, 0, tzinfo=UTC)
    with session_scope(engine) as session:
        record_sync_failure(session, "alex", earlier, UNREACHABLE)
        record_sync_failure(session, "sam", earlier, UNREACHABLE)
    runs, _, _ = sync(engine, Bridge(), links=("alex",))
    assert [run.failure for run in runs] == [None]
    assert failures(engine) == [SyncFailure("sam", earlier, UNREACHABLE)]


def test_a_new_failure_replaces_the_old_one(engine: Engine) -> None:
    with session_scope(engine) as session:
        record_sync_failure(session, "alex", datetime(2026, 10, 19, 7, 0, tzinfo=UTC), "older")
    sync(engine, Bridge(failures=99, failure="error"))
    assert failures(engine) == [SyncFailure("alex", NOW, "aggregator answered with an error")]
