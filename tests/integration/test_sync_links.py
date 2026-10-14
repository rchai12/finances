import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.repositories import (
    create_account,
    list_feed_accounts,
    list_transactions,
    map_feed_account,
)
from finances.domain.models import FeedAccount
from finances.sync.runner import AccountSync, run_sync

ACCESS = "https://user:pass@bridge.simplefin.org/simplefin"
TODAY = date(2026, 6, 1)


def stamp(day: int) -> int:
    return int(datetime(2026, 5, day, 12, tzinfo=UTC).timestamp())


def bridge(*accounts: tuple[str, str, int]):
    """A fake transport answering one account set: (account id, transaction id, cents)."""
    body = {
        "errlist": [],
        "accounts": [
            {
                "id": account_id,
                "name": account_id,
                "currency": "USD",
                "balance": "0",
                "balance-date": stamp(31),
                "transactions": [
                    {
                        "id": feed_id,
                        "posted": stamp(20),
                        "amount": f"{cents // 100}.{abs(cents) % 100:02d}",
                        "description": "PROBE",
                    }
                ],
            }
            for account_id, feed_id, cents in accounts
        ],
    }

    def answer(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        return 200, json.dumps(body).encode()

    return answer


@pytest.fixture
def session(db_engine: Engine):
    """Three accounts: ids 1 and 2 for one person, 3 for the other."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card", last4="1111")
        create_account(opened, "Test Checking", "Test Bank", "checking", last4="2222")
        create_account(opened, "Test Other Card", "Other Bank", "credit_card", last4="3333")
        yield opened


def test_mappings_without_a_link_use_the_default_link(session: Session) -> None:
    assert map_feed_account(session, 1, "ACT-1") == FeedAccount(1, 1, "ACT-1", "default")
    assert list_feed_accounts(session) == [FeedAccount(1, 1, "ACT-1", "default")]
    assert list_feed_accounts(session, "default") == [FeedAccount(1, 1, "ACT-1", "default")]
    assert list_feed_accounts(session, "alex") == []


def test_the_same_aggregator_id_under_two_links(session: Session) -> None:
    alex = map_feed_account(session, 1, "ACT-1", "alex")
    sam = map_feed_account(session, 3, "ACT-1", "sam")
    assert (alex, sam) == (FeedAccount(1, 1, "ACT-1", "alex"), FeedAccount(2, 3, "ACT-1", "sam"))
    with pytest.raises(ValueError) as caught:
        map_feed_account(session, 2, "ACT-1", "alex")
    assert str(caught.value) == "feed account is already mapped to another account"
    assert list_feed_accounts(session, "alex") == [alex]
    assert list_feed_accounts(session, "sam") == [sam]
    assert list_feed_accounts(session) == [alex, sam]


def test_an_account_can_move_to_another_link(session: Session) -> None:
    map_feed_account(session, 1, "ACT-1", "alex")
    moved = map_feed_account(session, 1, "ACT-7", "sam")
    assert moved == FeedAccount(1, 1, "ACT-7", "sam")
    assert list_feed_accounts(session, "alex") == []
    assert map_feed_account(session, 2, "ACT-1", "alex") == FeedAccount(2, 2, "ACT-1", "alex")


def test_a_sync_touches_only_its_own_link(session: Session) -> None:
    map_feed_account(session, 1, "ACT-1", "alex")
    map_feed_account(session, 2, "ACT-2", "alex")
    map_feed_account(session, 3, "ACT-1", "sam")
    report = run_sync(
        session, ACCESS, today=TODAY, transport=bridge(("ACT-1", "S-1", -500)), link="sam"
    )
    assert [
        (item.provider_account_id, item.account_id, item.problem) for item in report.accounts
    ] == [("ACT-1", 3, None)]
    assert [t.amount_cents for t in list_transactions(session, 3)] == [-500]
    assert list_transactions(session, 1) == []
    report = run_sync(
        session, ACCESS, today=TODAY, transport=bridge(("ACT-1", "A-1", -700)), link="alex"
    )
    assert [(item.account_id, item.problem) for item in report.accounts] == [
        (1, None),
        (2, "not in the aggregator's answer"),
    ]
    assert [t.amount_cents for t in list_transactions(session, 1)] == [-700]
    assert [t.amount_cents for t in list_transactions(session, 3)] == [-500]


def test_a_sync_without_a_link_uses_the_default_link(session: Session) -> None:
    map_feed_account(session, 1, "ACT-1")
    map_feed_account(session, 3, "ACT-3", "sam")
    report = run_sync(session, ACCESS, today=TODAY, transport=bridge(("ACT-1", "D-1", -100)))
    assert report.accounts == [AccountSync("ACT-1", 1, report.accounts[0].pull, None)]
    assert report.accounts[0].pull.inserted == 1
