import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine, select

from finances.db.engine import session_scope
from finances.db.orm import FeedSeenAccountRow
from finances.db.repositories import (
    create_account,
    list_feed_links,
    list_new_feed_accounts,
    map_feed_account,
    record_seen_feed_account,
    set_feed_account_ignored,
)
from finances.domain.models import SeenFeedAccount
from finances.sync.runner import run_sync

MAY_1 = date(2026, 5, 1)
MAY_9 = date(2026, 5, 9)


def seen(engine: Engine, link: str | None = None, ignored: bool = False) -> list[tuple]:
    with session_scope(engine) as session:
        return [
            (item.link, item.provider_account_id, item.name, item.institution)
            for item in list_new_feed_accounts(session, link, ignored=ignored)
        ]


def test_a_new_account_is_recorded(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        record_seen_feed_account(session, "kim", "ACT-1", "Probe Visa", "Probe Bank", MAY_1)
        assert list_new_feed_accounts(session) == [
            SeenFeedAccount(1, "kim", "ACT-1", "Probe Visa", "Probe Bank", MAY_1, MAY_1, False)
        ]


def test_seeing_it_again_updates_the_name_and_the_last_day(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        record_seen_feed_account(session, "kim", "ACT-1", "Old Name", "Old Bank", MAY_1)
        record_seen_feed_account(session, "kim", "ACT-1", "New  Name", " New Bank ", MAY_9)
        record_seen_feed_account(session, "kim", "ACT-1", "Newer", "Newer Bank", MAY_1)
        (item,) = list_new_feed_accounts(session)
    assert (item.name, item.institution, item.first_seen, item.last_seen) == (
        "Newer",
        "Newer Bank",
        MAY_1,
        MAY_9,
    )


def test_long_text_is_cut_to_fit(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        record_seen_feed_account(session, "kim", "ACT-1", "N" * 99 + "  X" * 40, "I" * 300, MAY_1)
        row = session.scalars(select(FeedSeenAccountRow)).one()
        assert (row.name, row.institution) == ("N" * 99, "I" * 100)


def test_a_mapped_account_is_not_new_under_its_link(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        made = create_account(session, "Probe Card", "Probe Bank", "credit_card")
        map_feed_account(session, made.id, "ACT-1", "kim")
        for link, feed_id in (("kim", "ACT-1"), ("kim", "ACT-2"), ("sam", "ACT-1")):
            record_seen_feed_account(session, link, feed_id, f"{link} {feed_id}", "Probe", MAY_1)
    assert seen(db_engine) == [
        ("kim", "ACT-2", "kim ACT-2", "Probe"),
        ("sam", "ACT-1", "sam ACT-1", "Probe"),
    ]
    assert seen(db_engine, "sam") == [("sam", "ACT-1", "sam ACT-1", "Probe")]


def test_new_accounts_come_by_link_then_first_day_then_id(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        record_seen_feed_account(session, "sam", "S-1", "S one", "Probe", MAY_1)
        record_seen_feed_account(session, "kim", "K-late", "K late", "Probe", MAY_9)
        record_seen_feed_account(session, "kim", "K-b", "K b", "Probe", MAY_1)
        record_seen_feed_account(session, "kim", "K-a", "K a", "Probe", MAY_1)
    assert [item[1] for item in seen(db_engine)] == ["K-b", "K-a", "K-late", "S-1"]


def test_an_account_not_tracked_leaves_the_new_list_and_can_come_back(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        record_seen_feed_account(session, "kim", "ACT-1", "Probe", "Probe Bank", MAY_1)
        record_seen_feed_account(session, "kim", "ACT-2", "Other", "Probe Bank", MAY_1)
        set_feed_account_ignored(session, "kim", "ACT-1", True)
    assert [item[1] for item in seen(db_engine)] == ["ACT-2"]
    assert [item[1] for item in seen(db_engine, ignored=True)] == ["ACT-1"]
    with session_scope(db_engine) as session:
        record_seen_feed_account(session, "kim", "ACT-1", "Probe", "Probe Bank", MAY_9)
    assert [item[1] for item in seen(db_engine, ignored=True)] == ["ACT-1"]
    with session_scope(db_engine) as session:
        set_feed_account_ignored(session, "kim", "ACT-1", False)
    assert [item[1] for item in seen(db_engine)] == ["ACT-1", "ACT-2"]


@pytest.mark.parametrize(("link", "feed_id"), [("sam", "ACT-1"), ("kim", "ACT-9")])
def test_an_unknown_account_cannot_be_ignored(db_engine: Engine, link: str, feed_id: str) -> None:
    with session_scope(db_engine) as session:
        record_seen_feed_account(session, "kim", "ACT-1", "Probe", "Probe Bank", MAY_1)
        with pytest.raises(ValueError, match="^SimpleFIN account not found$"):
            set_feed_account_ignored(session, link, feed_id, True)


def test_links_to_sync_have_a_mapping_or_a_seen_account(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        assert list_feed_links(session) == []
        made = create_account(session, "Probe Card", "Probe Bank", "credit_card")
        map_feed_account(session, made.id, "sam", "sam")
        record_seen_feed_account(session, "kim", "ACT-1", "Probe", "Probe Bank", MAY_1)
        record_seen_feed_account(session, "sam", "ACT-2", "Probe", "Probe Bank", MAY_1)
        assert list_feed_links(session) == ["kim", "sam"]


def test_a_sync_records_every_account_it_delivers(db_engine: Engine) -> None:
    stamp = int(datetime(2026, 5, 9, 12, tzinfo=UTC).timestamp())
    body = {
        "errlist": [],
        "connections": [{"conn_id": "C", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}],
        "accounts": [
            {
                "id": feed_id,
                "name": name,
                "conn_id": "C",
                "currency": "USD",
                "balance": "-1.00",
                "balance-date": stamp,
                "transactions": [],
            }
            for feed_id, name in (("ACT-1", "Mapped Card"), ("ACT-2", "Probe Visa 9876"))
        ],
    }
    with session_scope(db_engine) as session:
        made = create_account(session, "Probe Card", "Probe Bank", "credit_card")
        map_feed_account(session, made.id, "ACT-1", "kim")
    with session_scope(db_engine) as session:
        report = run_sync(
            session,
            "https://u:p@bridge.simplefin.org/simplefin",
            today=MAY_9,
            transport=lambda *_: (200, json.dumps(body).encode()),
            link="kim",
        )
    assert [item.problem for item in report.accounts] == [None, "not mapped"]
    assert seen(db_engine) == [("kim", "ACT-2", "Probe Visa 9876", "Probe Bank")]
    with session_scope(db_engine) as session:
        rows = session.scalars(select(FeedSeenAccountRow).order_by(FeedSeenAccountRow.id)).all()
        assert [(row.provider_account_id, row.last_seen) for row in rows] == [
            ("ACT-1", MAY_9),
            ("ACT-2", MAY_9),
        ]
