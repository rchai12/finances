import base64
import json
from datetime import UTC, date, datetime

import keyring
import keyring.backend
import keyring.errors
import pytest
from sqlalchemy import Engine, func, select

from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, map_feed_account
from finances.sync.runner import LinkRun, run_links

TODAY = date(2026, 5, 20)
SERVICE = "finances-simplefin"
ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"
SAM = "https://sam-user:sam-pass@bridge.simplefin.org/simplefin"


def key(access: str) -> str:
    user, password = access.split("//")[1].split("@")[0].split(":")
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def answer(*moves: tuple[str, str]) -> dict:
    posted = int(datetime(2026, 5, 18, 12, tzinfo=UTC).timestamp())
    return {
        "errlist": [],
        "connections": [{"conn_id": "C-1", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}],
        "accounts": [
            {
                "id": "ACT-1",
                "name": "Probe",
                "conn_id": "C-1",
                "currency": "USD",
                "balance": "-1.00",
                "balance-date": posted,
                "transactions": [
                    {"id": feed_id, "posted": posted, "amount": amount, "description": "PROBE"}
                    for feed_id, amount in moves
                ],
            }
        ],
    }


class Bridge:
    def __init__(self, answers: dict[str, tuple[int, dict]]) -> None:
        self.answers = answers
        self.urls: list[str] = []

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.urls.append(url)
        status, body = self.answers[headers["Authorization"]]
        return status, json.dumps(body).encode()


class BrokenKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def get_password(self, service: str, username: str) -> str | None:
        raise keyring.errors.KeyringError("locked")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise keyring.errors.KeyringError("locked")

    def delete_password(self, service: str, username: str) -> None:
        raise keyring.errors.KeyringError("locked")


@pytest.fixture
def mapped(db_engine: Engine) -> Engine:
    """Account 1 under link alex, account 2 under link sam, both as SimpleFIN ACT-1."""
    with session_scope(db_engine) as session:
        for name, link in (("Test Card", "alex"), ("Test Checking", "sam")):
            made = create_account(session, name, "Test Bank", "other")
            map_feed_account(session, made.id, "ACT-1", link)
    return db_engine


def stored(engine: Engine) -> dict[int, int]:
    with session_scope(engine) as session:
        rows = session.execute(
            select(TransactionRow.account_id, func.count()).group_by(TransactionRow.account_id)
        )
        return dict(rows.all())


def test_each_link_is_synced_and_committed(mapped: Engine, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    keychain.passwords[(SERVICE, "sam")] = SAM
    bridge = Bridge(
        {key(ALEX): (200, answer(("A-1", "-1.00"))), key(SAM): (200, answer(("S-1", "-2.00")))}
    )
    runs = run_links(mapped, ["alex", "sam"], today=TODAY, transport=bridge)
    assert [(run.link, run.error) for run in runs] == [("alex", None), ("sam", None)]
    assert [[item.account_id for item in run.report.accounts] for run in runs] == [[1], [2]]
    assert stored(mapped) == {1: 1, 2: 1}


def test_a_failing_link_does_not_stop_the_next(mapped: Engine, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    keychain.passwords[(SERVICE, "sam")] = SAM
    bridge = Bridge({key(ALEX): (403, {}), key(SAM): (200, answer(("S-1", "-2.00")))})
    runs = run_links(mapped, ["alex", "bob", "sam"], today=TODAY, transport=bridge)
    assert runs[:2] == [
        LinkRun("alex", None, "link alex: aggregator access was revoked or is wrong"),
        LinkRun("bob", None, "link bob is not set up"),
    ]
    assert runs[2].error is None
    assert stored(mapped) == {2: 1}


def test_a_keychain_that_fails(mapped: Engine) -> None:
    keyring.set_keyring(BrokenKeyring())
    bridge = Bridge({})
    runs = run_links(mapped, ["alex"], today=TODAY, transport=bridge)
    assert runs == [LinkRun("alex", None, "link alex: could not use the system keychain")]
    assert bridge.urls == []


def test_the_days_asked_for(mapped: Engine, keychain) -> None:
    keychain.passwords[(SERVICE, "alex")] = ALEX
    bridge = Bridge({key(ALEX): (200, answer())})
    run_links(mapped, ["alex"], today=TODAY, transport=bridge)
    run_links(mapped, ["alex"], today=TODAY, transport=bridge, days=7)
    starts = [int(url.split("start-date=")[1].split("&")[0]) for url in bridge.urls]
    assert [datetime.fromtimestamp(start, UTC).date() for start in starts] == [
        date(2026, 4, 20),
        date(2026, 5, 13),
    ]


def test_no_links(mapped: Engine) -> None:
    assert run_links(mapped, [], today=TODAY, transport=Bridge({})) == []
