import dataclasses
from datetime import date

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import FeedAccountRow, to_feed_account
from finances.db.repositories import (
    create_account,
    insert_feed_transaction,
    insert_transactions,
    list_feed_accounts,
    list_pending_feed_ids,
    map_feed_account,
    update_feed_transaction,
)
from finances.domain.models import DataSource, FeedAccount, NewTransaction

SINCE = date(2026, 5, 2)


def new(
    day: date,
    account_id: int = 1,
    *,
    pending: bool = True,
    source: DataSource = DataSource.AGGREGATOR,
    fingerprint: str = "a" * 64,
) -> NewTransaction:
    return NewTransaction(
        account_id=account_id,
        statement_id=None,
        posted_date=day,
        transaction_date=None,
        amount_cents=-450,
        description="ACME COFFEE",
        section=None,
        card_last4=None,
        cardholder=None,
        external_id=None,
        source=source,
        is_pending=pending,
        fingerprint=fingerprint,
    )


def fed(session: Session, feed_id: str, day: date, **changes: object) -> None:
    insert_feed_transaction(session, new(day, fingerprint=feed_id * 64, **changes), feed_id)


@pytest.fixture
def session(db_engine: Engine):
    """A session with a card (id 1), a checking account (id 2), and a savings account (id 3)."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card", last4="1111")
        create_account(opened, "Test Checking", "Test Bank", "checking")
        create_account(opened, "Test Savings", "Test Bank", "savings")
        yield opened


# ----- FeedAccount and to_feed_account (R1) -----


def test_feed_account_fields_in_order_and_frozen() -> None:
    names = [field.name for field in dataclasses.fields(FeedAccount)]
    assert names == ["id", "account_id", "provider_account_id"]
    mapping = FeedAccount(1, 2, "ACT-X")
    with pytest.raises(dataclasses.FrozenInstanceError):
        mapping.account_id = 3  # type: ignore[misc]


def test_to_feed_account_reads_a_row(session: Session) -> None:
    session.add(FeedAccountRow(account_id=2, provider_account_id="ACT-X"))
    session.flush()
    row = session.scalars(select(FeedAccountRow)).one()
    assert to_feed_account(row) == FeedAccount(row.id, 2, "ACT-X")


# ----- map_feed_account (R2) -----


def test_a_first_mapping(session: Session) -> None:
    mapping = map_feed_account(session, 1, "ACT-A")
    assert (mapping.account_id, mapping.provider_account_id) == (1, "ACT-A")
    assert list_feed_accounts(session) == [mapping]


def test_a_new_aggregator_account_replaces_the_old_one_in_place(session: Session) -> None:
    first = map_feed_account(session, 1, "ACT-A")
    second = map_feed_account(session, 1, "ACT-B")
    assert second == FeedAccount(first.id, 1, "ACT-B")
    assert list_feed_accounts(session) == [second]
    freed = map_feed_account(session, 2, "ACT-A")
    assert (freed.account_id, freed.provider_account_id) == (2, "ACT-A")
    assert list_feed_accounts(session) == [second, freed]


def test_the_same_pair_twice_changes_nothing(session: Session) -> None:
    first = map_feed_account(session, 1, "ACT-A")
    assert map_feed_account(session, 1, "ACT-A") == first
    assert list_feed_accounts(session) == [first]


def test_an_aggregator_account_that_feeds_another_account_is_refused(session: Session) -> None:
    first = map_feed_account(session, 1, "ACT-A")
    other = map_feed_account(session, 2, "ACT-B")
    with pytest.raises(ValueError) as caught:
        map_feed_account(session, 2, "ACT-A")
    assert str(caught.value) == "feed account is already mapped to another account"
    assert list_feed_accounts(session) == [first, other]
    with pytest.raises(ValueError):
        map_feed_account(session, 3, "ACT-A")
    assert list_feed_accounts(session) == [first, other]


def test_a_mapping_for_an_account_that_does_not_exist(db_engine: Engine) -> None:
    with pytest.raises(IntegrityError), session_scope(db_engine) as opened:
        map_feed_account(opened, 99, "ACT-A")


# ----- list_feed_accounts (R3) -----


def test_list_is_empty_then_in_id_order(session: Session) -> None:
    assert list_feed_accounts(session) == []
    third = map_feed_account(session, 3, "ACT-C")
    first = map_feed_account(session, 1, "ACT-A")
    second = map_feed_account(session, 2, "ACT-B")
    assert list_feed_accounts(session) == [third, first, second]
    assert [mapping.id for mapping in list_feed_accounts(session)] == [1, 2, 3]


# ----- list_pending_feed_ids (R4) -----


def test_pending_ids_leave_out_posted_statement_other_account_and_older_rows(
    session: Session,
) -> None:
    fed(session, "k", SINCE)
    fed(session, "p", SINCE, pending=False)
    fed(session, "o", SINCE, account_id=2)
    fed(session, "e", date(2026, 5, 1))
    insert_transactions(session, [new(SINCE, source=DataSource.STATEMENT, fingerprint="s" * 64)])
    assert list_pending_feed_ids(session, 1, SINCE) == ["k"]
    assert list_pending_feed_ids(session, 2, SINCE) == ["o"]


def test_pending_ids_come_in_transaction_id_order(session: Session) -> None:
    fed(session, "z", date(2026, 5, 20))
    fed(session, "a", date(2026, 5, 3))
    fed(session, "m", SINCE)
    assert list_pending_feed_ids(session, 1, SINCE) == ["z", "a", "m"]


def test_a_replaced_hold_appears_under_its_current_feed_id(session: Session) -> None:
    held = insert_feed_transaction(session, new(SINCE, fingerprint="h" * 64), "h-old")
    update_feed_transaction(
        session,
        held.id,
        feed_id="h-new",
        posted_date=date(2026, 5, 4),
        transaction_date=None,
        amount_cents=-500,
        description="ACME COFFEE",
        card_last4=None,
        is_pending=True,
        fingerprint="n" * 64,
    )
    assert list_pending_feed_ids(session, 1, SINCE) == ["h-new"]


def test_pending_ids_are_empty_with_no_rows(session: Session) -> None:
    assert list_pending_feed_ids(session, 1, SINCE) == []


# ----- a later session (R5) -----


def test_a_later_session_sees_what_an_earlier_one_wrote(db_engine: Engine) -> None:
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        mapping = map_feed_account(opened, 1, "ACT-A")
        fed(opened, "k", SINCE)
    with session_scope(db_engine) as opened:
        assert list_feed_accounts(opened) == [mapping]
        assert list_pending_feed_ids(opened, 1, SINCE) == ["k"]
