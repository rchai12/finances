from datetime import date

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import BalanceSnapshotRow, FeedItemRow, TransactionRow
from finances.db.repositories import (
    create_account,
    create_feed_pull,
    delete_feed_transaction,
    feed_posted_total,
    find_feed_transactions,
    get_account,
    insert_feed_transaction,
    insert_transactions,
    latest_feed_pull,
    set_balance_snapshot,
    update_feed_transaction,
)
from finances.domain.models import AccountType, DataSource, NewTransaction, Transaction

DAY = date(2026, 6, 1)


def new(
    account_id: int = 1,
    cents: int = -450,
    *,
    pending: bool = False,
    source: DataSource = DataSource.AGGREGATOR,
    fingerprint: str = "a" * 64,
) -> NewTransaction:
    return NewTransaction(
        account_id=account_id,
        statement_id=None,
        posted_date=DAY,
        transaction_date=None,
        amount_cents=cents,
        description="ACME COFFEE",
        section=None,
        card_last4=None,
        cardholder=None,
        external_id=None,
        source=source,
        is_pending=pending,
        fingerprint=fingerprint,
    )


def pull_values(**changes: object) -> dict:
    values = {
        "account_id": 1,
        "inserted": 1,
        "updated": 2,
        "removed": 3,
        "unchanged": 4,
        "feed_total_cents": -500,
        "balance_cents": None,
        "balance_date": None,
        "drift_cents": None,
    }
    return {**values, **changes}


@pytest.fixture
def session(db_engine: Engine):
    """A session with a card (id 1) and a checking account (id 2)."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card", last4="1111")
        create_account(opened, "Test Checking", "Test Bank", "checking")
        yield opened


# ----- get_account (R7) -----


def test_get_account_found_and_not_found(session: Session) -> None:
    account = get_account(session, 2)
    assert account is not None
    assert (account.id, account.name, account.type) == (2, "Test Checking", AccountType.CHECKING)
    assert get_account(session, 99) is None


# ----- set_balance_snapshot (R8) -----


def test_set_balance_snapshot_adds_then_replaces_in_place(session: Session) -> None:
    first = set_balance_snapshot(session, 1, DAY, -1000, DataSource.AGGREGATOR)
    assert (first.account_id, first.as_of_date, first.balance_cents, first.source) == (
        1,
        DAY,
        -1000,
        DataSource.AGGREGATOR,
    )
    second = set_balance_snapshot(session, 1, DAY, -2500, DataSource.AGGREGATOR)
    assert second.id == first.id
    assert second.balance_cents == -2500
    rows = session.scalars(select(BalanceSnapshotRow)).all()
    assert [(row.id, row.balance_cents) for row in rows] == [(first.id, -2500)]


def test_set_balance_snapshot_another_source_or_date_is_a_new_row(session: Session) -> None:
    first = set_balance_snapshot(session, 1, DAY, -1000, DataSource.AGGREGATOR)
    other_source = set_balance_snapshot(session, 1, DAY, -1100, DataSource.STATEMENT)
    other_day = set_balance_snapshot(session, 1, date(2026, 6, 2), -1200, DataSource.AGGREGATOR)
    other_account = set_balance_snapshot(session, 2, DAY, 1300, DataSource.AGGREGATOR)
    assert len({first.id, other_source.id, other_day.id, other_account.id}) == 4
    assert session.get(BalanceSnapshotRow, first.id).balance_cents == -1000


def test_set_balance_snapshot_beyond_32_bits(session: Session) -> None:
    snapshot = set_balance_snapshot(session, 1, DAY, -(2**40), DataSource.AGGREGATOR)
    assert snapshot.balance_cents == -(2**40)


# ----- find_feed_transactions (R9) -----


def test_find_with_no_ids(session: Session) -> None:
    insert_feed_transaction(session, new(), "t-1")
    assert find_feed_transactions(session, 1, []) == {}
    assert find_feed_transactions(session, 1, iter(())) == {}


def test_find_returns_only_this_accounts_known_ids(session: Session) -> None:
    mine = insert_feed_transaction(session, new(1), "shared")
    insert_feed_transaction(session, new(2, 2500, fingerprint="b" * 64), "shared")
    insert_feed_transaction(session, new(2, 100, fingerprint="c" * 64), "only-2")
    found = find_feed_transactions(session, 1, {"shared", "only-2", "unknown"})
    assert found == {"shared": mine}


def test_find_more_than_a_thousand_ids_in_one_call(session: Session) -> None:
    stored = {
        f"t-{number}": insert_feed_transaction(
            session, new(cents=-number, fingerprint=f"{number:064d}"), f"t-{number}"
        )
        for number in range(1, 1201)
    }
    wanted = (f"t-{number}" for number in range(1, 1301))
    found = find_feed_transactions(session, 1, wanted)
    assert found == stored
    assert found["t-1200"].amount_cents == -1200


# ----- insert_feed_transaction (R10) -----


def test_insert_returns_every_field_of_the_new_transaction(session: Session) -> None:
    item = NewTransaction(
        account_id=1,
        statement_id=None,
        posted_date=DAY,
        transaction_date=date(2026, 5, 30),
        amount_cents=-1299,
        description="FOOBAR GROCERY",
        section="purchases",
        card_last4="1111",
        cardholder="TEST HOLDER",
        external_id="ref-9",
        source=DataSource.AGGREGATOR,
        is_pending=True,
        fingerprint="d" * 64,
    )
    stored = insert_feed_transaction(session, item, "t-9")
    assert isinstance(stored, Transaction)
    assert stored.id == 1
    for name in item.__dataclass_fields__:
        assert getattr(stored, name) == getattr(item, name), name
    assert stored.created_at.tzinfo is not None
    link = session.scalars(select(FeedItemRow)).one()
    assert (link.account_id, link.feed_id, link.transaction_id) == (1, "t-9", 1)


def test_the_same_feed_id_twice_in_one_account_is_refused(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        insert_feed_transaction(session, new(), "t-1")
    with pytest.raises(IntegrityError), session_scope(db_engine) as session:
        insert_feed_transaction(session, new(fingerprint="b" * 64), "t-1")


# ----- update_feed_transaction (R11) -----


def test_update_changes_the_eight_values_and_nothing_else(session: Session) -> None:
    item = NewTransaction(
        account_id=1,
        statement_id=None,
        posted_date=DAY,
        transaction_date=None,
        amount_cents=-450,
        description="ACME COFFEE",
        section="purchases",
        card_last4=None,
        cardholder="TEST HOLDER",
        external_id="ref-1",
        source=DataSource.AGGREGATOR,
        is_pending=True,
        fingerprint="a" * 64,
    )
    before = insert_feed_transaction(session, item, "pend-1")
    after = update_feed_transaction(
        session,
        before.id,
        feed_id="post-1",
        posted_date=date(2026, 6, 3),
        transaction_date=date(2026, 6, 2),
        amount_cents=-475,
        description="ACME COFFEE #12",
        card_last4="1111",
        is_pending=False,
        fingerprint="e" * 64,
    )
    assert (
        after.posted_date,
        after.transaction_date,
        after.amount_cents,
        after.description,
        after.card_last4,
        after.is_pending,
        after.fingerprint,
    ) == (date(2026, 6, 3), date(2026, 6, 2), -475, "ACME COFFEE #12", "1111", False, "e" * 64)
    assert (
        after.id,
        after.account_id,
        after.source,
        after.statement_id,
        after.section,
        after.cardholder,
        after.external_id,
        after.created_at,
    ) == (
        before.id,
        before.account_id,
        before.source,
        before.statement_id,
        before.section,
        before.cardholder,
        before.external_id,
        before.created_at,
    )
    assert session.scalars(select(FeedItemRow.feed_id)).all() == ["post-1"]


def update(session: Session, transaction_id: int) -> Transaction:
    return update_feed_transaction(
        session,
        transaction_id,
        feed_id="x",
        posted_date=DAY,
        transaction_date=None,
        amount_cents=-1,
        description="ACME",
        card_last4=None,
        is_pending=False,
        fingerprint="f" * 64,
    )


def test_update_an_unknown_transaction(session: Session) -> None:
    with pytest.raises(ValueError) as caught:
        update(session, 99)
    assert str(caught.value) == "transaction did not come from the feed"


def test_update_a_transaction_without_a_feed_id(session: Session) -> None:
    insert_transactions(session, [new(source=DataSource.STATEMENT)])
    with pytest.raises(ValueError) as caught:
        update(session, 1)
    assert str(caught.value) == "transaction did not come from the feed"
    assert session.get(TransactionRow, 1).amount_cents == -450


# ----- delete_feed_transaction (R12) -----


def test_delete_removes_the_transaction_and_its_feed_id(session: Session) -> None:
    kept = insert_feed_transaction(session, new(fingerprint="b" * 64), "keep")
    gone = insert_feed_transaction(session, new(), "gone")
    assert delete_feed_transaction(session, gone.id) is True
    assert session.get(TransactionRow, gone.id) is None
    assert session.scalars(select(FeedItemRow.feed_id)).all() == ["keep"]
    assert session.get(TransactionRow, kept.id) is not None


def test_delete_leaves_a_statement_row_alone(session: Session) -> None:
    insert_transactions(session, [new(source=DataSource.STATEMENT)])
    assert delete_feed_transaction(session, 1) is False
    assert session.get(TransactionRow, 1) is not None


def test_delete_an_unknown_transaction(session: Session) -> None:
    assert delete_feed_transaction(session, 99) is False


# ----- feed_posted_total (R13) -----


def test_posted_total_is_zero_with_nothing(session: Session) -> None:
    total = feed_posted_total(session, 1)
    assert total == 0
    assert type(total) is int


def test_posted_total_counts_only_posted_feed_rows_of_the_account(session: Session) -> None:
    insert_feed_transaction(session, new(cents=-450, fingerprint="1" * 64), "a")
    insert_feed_transaction(session, new(cents=-700, pending=True, fingerprint="2" * 64), "b")
    confirmed = insert_feed_transaction(session, new(cents=-900, fingerprint="3" * 64), "c")
    insert_transactions(session, [new(cents=-5000, source=DataSource.STATEMENT)])
    insert_feed_transaction(session, new(2, 2500, fingerprint="4" * 64), "a")
    session.get(TransactionRow, confirmed.id).source = "statement"
    session.flush()
    total = feed_posted_total(session, 1)
    assert total == -1350
    assert type(total) is int
    assert feed_posted_total(session, 2) == 2500


# ----- create_feed_pull and latest_feed_pull (R14, R15) -----


def test_create_feed_pull_stores_the_values(session: Session) -> None:
    pull = create_feed_pull(
        session,
        **pull_values(balance_cents=-(2**40), balance_date=DAY, drift_cents=-51),
    )
    assert (
        pull.id,
        pull.account_id,
        pull.inserted,
        pull.updated,
        pull.removed,
        pull.unchanged,
        pull.feed_total_cents,
        pull.balance_cents,
        pull.balance_date,
        pull.drift_cents,
    ) == (1, 1, 1, 2, 3, 4, -500, -(2**40), DAY, -51)
    assert pull.pulled_at.tzinfo is not None


def test_latest_feed_pull_is_the_highest_id(session: Session) -> None:
    assert latest_feed_pull(session, 1) is None
    create_feed_pull(session, **pull_values(balance_cents=-100, balance_date=DAY))
    second = create_feed_pull(session, **pull_values(inserted=9))
    create_feed_pull(session, **pull_values(account_id=2, balance_cents=5, balance_date=DAY))
    assert latest_feed_pull(session, 1) == second


def test_latest_feed_pull_with_a_balance_skips_pulls_without_one(session: Session) -> None:
    assert latest_feed_pull(session, 1, with_balance=True) is None
    create_feed_pull(session, **pull_values())
    assert latest_feed_pull(session, 1, with_balance=True) is None
    first = create_feed_pull(session, **pull_values(balance_cents=-100, balance_date=DAY))
    create_feed_pull(session, **pull_values())
    assert latest_feed_pull(session, 1, with_balance=True) == first
    assert latest_feed_pull(session, 2, with_balance=True) is None


# ----- a later session sees what an earlier one wrote -----


def test_writes_are_seen_by_a_later_session(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        stored = insert_feed_transaction(session, new(), "t-1")
        changed = insert_feed_transaction(session, new(cents=-10, fingerprint="b" * 64), "t-2")
        gone = insert_feed_transaction(session, new(cents=-20, fingerprint="c" * 64), "t-3")
        set_balance_snapshot(session, 1, DAY, -100, DataSource.AGGREGATOR)
        pull = create_feed_pull(session, **pull_values(balance_cents=-100, balance_date=DAY))
    with session_scope(db_engine) as session:
        update(session, changed.id)
        delete_feed_transaction(session, gone.id)
        set_balance_snapshot(session, 1, DAY, -200, DataSource.AGGREGATOR)
    with session_scope(db_engine) as session:
        assert get_account(session, 1) is not None
        found = find_feed_transactions(session, 1, ["t-1", "x", "t-3"])
        assert found == {"t-1": stored, "x": found["x"]}
        assert found["x"].amount_cents == -1
        assert feed_posted_total(session, 1) == -451
        assert session.scalars(select(BalanceSnapshotRow.balance_cents)).all() == [-200]
        assert latest_feed_pull(session, 1, with_balance=True) == pull
