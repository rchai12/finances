from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_tags,
    create_account,
    delete_feed_transaction,
    insert_feed_transaction,
    list_changes,
    list_tags,
    note_of,
    remove_tags,
    set_note,
    tags_for,
)
from finances.domain.models import DataSource, NewTransaction
from finances.domain.tags import TagCount
from tests.support import run


def add_card(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    for number, (cents, description) in enumerate(
        ((-450, "ACME COFFEE"), (-2599, "FOOBAR GROCERY"), (-500, "BAZ CAFE")), start=1
    ):
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=date(2026, 5, number),
                amount_cents=cents,
                description=description,
                source="statement",
                fingerprint=f"a{number:02d}".ljust(64, "0"),
            )
        )
    session.flush()


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        add_card(opened)
        yield opened


def test_add_tags_counts_distinct_ids_and_skips_a_tag_already_there(session: Session) -> None:
    count, stored = add_tags(session, [1, 1], "Trip")
    assert (count, stored) == (1, "trip")
    add_tags(session, [1], "trip")
    added = [item for item in list_changes(session) if item.action == "tag_added"]
    assert [(item.kind, item.record_id, item.after) for item in added] == [
        ("transaction", 1, "trip")
    ]
    removed = remove_tags(session, [1], "trip")
    assert removed == (1, "trip")
    gone = [item for item in list_changes(session) if item.action == "tag_removed"]
    assert [(item.kind, item.record_id, item.before) for item in gone] == [
        ("transaction", 1, "trip")
    ]


def test_remove_tags_of_a_tag_the_transaction_lacks(session: Session) -> None:
    assert remove_tags(session, [1], "trip") == (1, "trip")
    assert [item.action for item in list_changes(session) if item.action.startswith("tag")] == []
    assert tags_for(session, [1]) == {}
    assert tags_for(session, []) == {}
    assert list_tags(session) == []


def test_add_tags_is_all_or_none(session: Session) -> None:
    with pytest.raises(ValueError, match="transaction not found"):
        add_tags(session, [1, 9], "trip")
    assert tags_for(session, [1]) == {}
    assert [item.action for item in list_changes(session) if item.action.startswith("tag")] == []


def test_set_note_records_only_a_change(session: Session) -> None:
    assert set_note(session, 1, "first") == "first"
    first = list_changes(session, action="note_set")
    assert [(item.before, item.after, item.kind, item.record_id) for item in first] == [
        (None, "first", "transaction", 1)
    ]
    assert set_note(session, 1, "later") == "later"
    changed = list_changes(session, action="note_set")
    assert (changed[0].before, changed[0].after) == ("first", "later")
    assert set_note(session, 1, "later") == "later"
    assert len(list_changes(session, action="note_set")) == 2
    assert set_note(session, 1, "") is None
    cleared = list_changes(session, action="note_cleared")
    assert [(item.before, item.after, item.record_id) for item in cleared] == [("later", None, 1)]
    assert set_note(session, 1, "") is None
    assert len(list_changes(session, action="note_cleared")) == 1
    assert note_of(session, 1) is None


def test_tags_for_leaves_out_a_transaction_with_none(session: Session) -> None:
    add_tags(session, [1], "tax")
    add_tags(session, [1, 2], "work trip")
    assert tags_for(session, [1, 2, 3]) == {
        1: ["tax", "work trip"],
        2: ["work trip"],
    }
    assert list_tags(session) == [TagCount("tax", 1), TagCount("work trip", 2)]


def test_deleting_a_feed_transaction_takes_tags_and_a_note(session: Session) -> None:
    feed = insert_feed_transaction(
        session,
        NewTransaction(
            account_id=1,
            statement_id=None,
            posted_date=date(2026, 5, 4),
            transaction_date=None,
            amount_cents=-450,
            description="ACME COFFEE",
            section=None,
            card_last4=None,
            cardholder=None,
            external_id=None,
            source=DataSource.AGGREGATOR,
            is_pending=False,
            fingerprint="f".ljust(64, "0"),
        ),
        "f-1",
    )
    add_tags(session, [feed.id], "tax")
    set_note(session, feed.id, "pending")
    assert delete_feed_transaction(session, feed.id) is True
    assert tags_for(session, [feed.id]) == {}
    assert note_of(session, feed.id) is None


def test_untagging_several_transactions(tmp_settings: Settings) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        add_card(session)
    engine.dispose()
    run("transactions", "tag", "--id", "1", "--id", "2", "--tag", "trip")
    removed = run("transactions", "untag", "--id", "1", "--id", "2", "--tag", "trip")
    assert (removed.exit_code, removed.stdout) == (0, '2 transactions: "trip" removed.\n')
