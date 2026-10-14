import hashlib
from datetime import date

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import BalanceSnapshotRow, FeedItemRow, FeedPullRow, TransactionRow
from finances.db.repositories import create_account, insert_transactions, latest_balance
from finances.domain.models import DataSource, FeedPull, NewTransaction
from finances.sync.feed import AccountFeed, FeedError, FeedTransaction, feed_fingerprint
from finances.sync.service import apply_feed

MAY = date(2026, 5, 1)


def day(number: int) -> date:
    return date(2026, 5, number)


def tx(feed_id: str, number: int, cents: int, text: str, **more: object) -> FeedTransaction:
    return FeedTransaction(feed_id, day(number), cents, text, **more)


def feed(*items: FeedTransaction, removed: tuple[str, ...] = (), balance=None, on=None):
    return AccountFeed(list(items), list(removed), balance, on)


def counts(pull: FeedPull) -> tuple[int, int, int, int]:
    return (pull.inserted, pull.updated, pull.removed, pull.unchanged)


def ledger(session: Session, account_id: int = 1) -> list[tuple]:
    """Every stored transaction of the account with its feed id, in id order."""
    stmt = (
        select(TransactionRow, FeedItemRow.feed_id)
        .outerjoin(FeedItemRow, FeedItemRow.transaction_id == TransactionRow.id)
        .where(TransactionRow.account_id == account_id)
        .order_by(TransactionRow.id)
    )
    return [
        (row.id, feed_id, row.posted_date.day, row.amount_cents, row.description, row.is_pending)
        for row, feed_id in session.execute(stmt).all()
    ]


@pytest.fixture
def session(db_engine: Engine):
    """A session on a migrated database with a card (id 1) and a checking account (id 2)."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card", last4="1111")
        create_account(opened, "Test Checking", "Test Bank", "checking", last4="2222")
        yield opened


def audit(session: Session, transaction_id: int) -> None:
    """Mark a stored row as confirmed by a statement, as Phase 8 will."""
    session.get(TransactionRow, transaction_id).source = "statement"
    session.flush()


def test_the_fingerprint_of_a_feed_row() -> None:
    expected = hashlib.sha256(b"feed\n7\nabc-123").hexdigest()
    assert feed_fingerprint(7, "abc-123") == expected
    assert feed_fingerprint(8, "abc-123") != expected
    assert feed_fingerprint(7, "abc-124") != expected


def test_the_first_feed_inserts_every_row(session: Session) -> None:
    pull = apply_feed(
        session,
        1,
        feed(
            tx("a", 1, -450, "ACME  COFFEE "),
            tx("b", 2, -1299, "FOOBAR GROCERY", transaction_date=MAY, card_last4="1111"),
            tx("c", 3, -700, "ACME GAS", is_pending=True),
        ),
    )
    assert counts(pull) == (3, 0, 0, 0)
    assert (pull.id, pull.account_id) == (1, 1)
    assert (pull.balance_cents, pull.balance_date, pull.drift_cents) == (None, None, None)
    assert pull.feed_total_cents == -1749
    assert pull.pulled_at.tzinfo is not None
    assert ledger(session) == [
        (1, "a", 1, -450, "ACME COFFEE", False),
        (2, "b", 2, -1299, "FOOBAR GROCERY", False),
        (3, "c", 3, -700, "ACME GAS", True),
    ]
    rows = session.scalars(select(TransactionRow).order_by(TransactionRow.id)).all()
    assert [row.source for row in rows] == ["aggregator"] * 3
    assert [row.fingerprint for row in rows] == [feed_fingerprint(1, name) for name in "abc"]
    assert [(row.transaction_date, row.card_last4) for row in rows] == [
        (None, None),
        (MAY, "1111"),
        (None, None),
    ]
    assert [(row.statement_id, row.section, row.cardholder, row.external_id) for row in rows] == [
        (None, None, None, None)
    ] * 3
    assert session.scalars(select(BalanceSnapshotRow)).all() == []


def test_the_same_feed_again_changes_nothing(session: Session) -> None:
    items = (tx("a", 1, -450, "ACME COFFEE"), tx("b", 2, -1299, "FOOBAR GROCERY"))
    apply_feed(session, 1, feed(*items))
    before = ledger(session)
    pull = apply_feed(session, 1, feed(*items))
    assert counts(pull) == (0, 0, 0, 2)
    assert pull.id == 2
    assert ledger(session) == before


def test_a_changed_row_is_updated_in_place(session: Session) -> None:
    apply_feed(session, 1, feed(tx("a", 1, -450, "ACME COFFEE"), tx("b", 2, -1299, "FOOBAR")))
    pull = apply_feed(
        session,
        1,
        feed(tx("a", 4, -475, "ACME COFFEE #12", card_last4="9999"), tx("b", 2, -1299, "FOOBAR")),
    )
    assert counts(pull) == (0, 1, 0, 1)
    assert pull.feed_total_cents == -1774
    assert ledger(session) == [
        (1, "a", 4, -475, "ACME COFFEE #12", False),
        (2, "b", 2, -1299, "FOOBAR", False),
    ]
    assert session.get(TransactionRow, 1).card_last4 == "9999"


@pytest.mark.parametrize(
    "changed",
    [
        tx("a", 2, -450, "ACME COFFEE", transaction_date=MAY, card_last4="1111"),
        tx("a", 1, -451, "ACME COFFEE", transaction_date=MAY, card_last4="1111"),
        tx("a", 1, -450, "ACME COFFEE 2", transaction_date=MAY, card_last4="1111"),
        tx("a", 1, -450, "ACME COFFEE", transaction_date=day(2), card_last4="1111"),
        tx("a", 1, -450, "ACME COFFEE", card_last4="1111"),
        tx("a", 1, -450, "ACME COFFEE", transaction_date=MAY, card_last4="2222"),
        tx("a", 1, -450, "ACME COFFEE", transaction_date=MAY),
        tx("a", 1, -450, "ACME COFFEE", transaction_date=MAY, card_last4="1111", is_pending=True),
    ],
)
def test_a_change_to_any_one_field_is_an_update(session: Session, changed: FeedTransaction) -> None:
    apply_feed(
        session, 1, feed(tx("a", 1, -450, "ACME COFFEE", transaction_date=MAY, card_last4="1111"))
    )
    assert counts(apply_feed(session, 1, feed(changed))) == (0, 1, 0, 0)
    row = session.get(TransactionRow, 1)
    assert (
        row.posted_date,
        row.amount_cents,
        row.description,
        row.transaction_date,
        row.card_last4,
        row.is_pending,
    ) == (
        changed.posted_date,
        changed.amount_cents,
        changed.description,
        changed.transaction_date,
        changed.card_last4,
        changed.is_pending,
    )


def test_a_pending_row_that_posts_under_the_same_id(session: Session) -> None:
    apply_feed(session, 1, feed(tx("a", 1, -700, "ACME GAS", is_pending=True)))
    pull = apply_feed(session, 1, feed(tx("a", 2, -712, "ACME GAS #4")))
    assert counts(pull) == (0, 1, 0, 0)
    assert pull.feed_total_cents == -712
    assert ledger(session) == [(1, "a", 2, -712, "ACME GAS #4", False)]


def test_a_posted_row_replaces_its_pending_row_and_keeps_the_stored_id(session: Session) -> None:
    apply_feed(
        session,
        1,
        feed(tx("keep", 1, -100, "ACME"), tx("pend-1", 1, -700, "ACME GAS", is_pending=True)),
    )
    pull = apply_feed(
        session,
        1,
        feed(tx("post-1", 3, -712, "ACME GAS #4", replaces_feed_id="pend-1"), removed=("pend-1",)),
    )
    assert counts(pull) == (0, 1, 0, 0)
    assert ledger(session) == [
        (1, "keep", 1, -100, "ACME", False),
        (2, "post-1", 3, -712, "ACME GAS #4", False),
    ]
    assert session.get(TransactionRow, 2).fingerprint == feed_fingerprint(1, "post-1")
    assert session.scalars(select(FeedItemRow.feed_id).order_by(FeedItemRow.id)).all() == [
        "keep",
        "post-1",
    ]
    again = apply_feed(
        session, 1, feed(tx("post-1", 3, -712, "ACME GAS #4", replaces_feed_id="pend-1"))
    )
    assert counts(again) == (0, 0, 0, 1)


def test_a_replacement_whose_pending_row_is_unknown_is_inserted(session: Session) -> None:
    pull = apply_feed(session, 1, feed(tx("post-1", 3, -712, "ACME", replaces_feed_id="gone")))
    assert counts(pull) == (1, 0, 0, 0)
    assert ledger(session) == [(1, "post-1", 3, -712, "ACME", False)]


def test_removed_rows_are_deleted_and_unknown_ids_are_ignored(session: Session) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("a", 1, -450, "ACME COFFEE"),
            tx("b", 2, -700, "ACME GAS", is_pending=True),
            tx("c", 3, -900, "FOOBAR"),
        ),
    )
    pull = apply_feed(session, 1, feed(removed=("b", "c", "never-seen", "b")))
    assert counts(pull) == (0, 0, 2, 0)
    assert pull.feed_total_cents == -450
    assert ledger(session) == [(1, "a", 1, -450, "ACME COFFEE", False)]
    assert session.scalars(select(FeedItemRow.feed_id)).all() == ["a"]


def test_a_row_confirmed_by_a_statement_is_never_changed_or_deleted(session: Session) -> None:
    apply_feed(session, 1, feed(tx("a", 1, -450, "ACME COFFEE"), tx("b", 2, -900, "FOOBAR")))
    audit(session, 1)
    audit(session, 2)
    pull = apply_feed(session, 1, feed(tx("a", 9, -999, "CHANGED BY THE FEED"), removed=("b",)))
    assert counts(pull) == (0, 0, 0, 1)
    assert pull.feed_total_cents == -1350
    assert ledger(session) == [
        (1, "a", 1, -450, "ACME COFFEE", False),
        (2, "b", 2, -900, "FOOBAR", False),
    ]


def test_a_replacement_does_not_touch_a_row_confirmed_by_a_statement(session: Session) -> None:
    apply_feed(session, 1, feed(tx("old", 1, -450, "ACME COFFEE")))
    audit(session, 1)
    pull = apply_feed(session, 1, feed(tx("new", 2, -460, "ACME COFFEE", replaces_feed_id="old")))
    assert counts(pull) == (1, 0, 0, 0)
    assert ledger(session) == [
        (1, "old", 1, -450, "ACME COFFEE", False),
        (2, "new", 2, -460, "ACME COFFEE", False),
    ]


def test_accounts_do_not_share_feed_ids(session: Session) -> None:
    apply_feed(session, 1, feed(tx("same", 1, -450, "ACME COFFEE")))
    pull = apply_feed(session, 2, feed(tx("same", 1, 2500, "PAYROLL"), balance=2500, on=day(1)))
    assert counts(pull) == (1, 0, 0, 0)
    assert (pull.account_id, pull.feed_total_cents) == (2, 2500)
    assert ledger(session, 1) == [(1, "same", 1, -450, "ACME COFFEE", False)]
    assert ledger(session, 2) == [(2, "same", 1, 2500, "PAYROLL", False)]
    apply_feed(session, 2, feed(removed=("same",)))
    assert ledger(session, 1) == [(1, "same", 1, -450, "ACME COFFEE", False)]
    assert ledger(session, 2) == []


def test_statement_rows_are_not_part_of_the_feed(session: Session) -> None:
    insert_transactions(
        session,
        [
            NewTransaction(
                account_id=1,
                statement_id=None,
                posted_date=day(1),
                transaction_date=None,
                amount_cents=-5000,
                description="ACME COFFEE",
                section="purchases",
                card_last4=None,
                cardholder=None,
                external_id="a",
                source=DataSource.STATEMENT,
                is_pending=False,
                fingerprint="f" * 64,
            )
        ],
    )
    pull = apply_feed(session, 1, feed(tx("a", 1, -450, "ACME COFFEE"), removed=("f" * 64,)))
    assert counts(pull) == (1, 0, 0, 0)
    assert pull.feed_total_cents == -450
    assert ledger(session) == [
        (1, None, 1, -5000, "ACME COFFEE", False),
        (2, "a", 1, -450, "ACME COFFEE", False),
    ]


def test_a_balance_is_stored_as_an_aggregator_snapshot(session: Session) -> None:
    pull = apply_feed(session, 1, feed(tx("a", 1, -450, "ACME"), balance=-10450, on=day(2)))
    assert (pull.balance_cents, pull.balance_date, pull.drift_cents) == (-10450, day(2), None)
    snapshot = latest_balance(session, 1)
    assert (snapshot.as_of_date, snapshot.balance_cents, snapshot.source) == (
        day(2),
        -10450,
        DataSource.AGGREGATOR,
    )


def test_a_second_balance_on_the_same_day_replaces_the_first(session: Session) -> None:
    apply_feed(session, 1, feed(balance=-10000, on=day(2)))
    apply_feed(session, 1, feed(tx("a", 2, -450, "ACME"), balance=-10450, on=day(2)))
    rows = session.scalars(select(BalanceSnapshotRow)).all()
    assert [(row.as_of_date, row.balance_cents, row.source) for row in rows] == [
        (day(2), -10450, "aggregator")
    ]


def test_drift_is_zero_when_the_balance_moves_with_the_posted_rows(session: Session) -> None:
    apply_feed(
        session,
        1,
        feed(
            tx("a", 1, -450, "ACME"),
            tx("p", 1, -700, "GAS", is_pending=True),
            balance=-10450,
            on=day(1),
        ),
    )
    pull = apply_feed(
        session,
        1,
        feed(
            tx("b", 2, -1299, "FOOBAR"),
            tx("c", 2, 5000, "PAYMENT"),
            tx("q", 2, -300, "SNACK", is_pending=True),
            balance=-6749,
            on=day(2),
        ),
    )
    assert (pull.feed_total_cents, pull.drift_cents) == (3251, 0)
    pull = apply_feed(
        session,
        1,
        feed(
            tx("p2", 3, -712, "GAS #4", replaces_feed_id="p"),
            removed=("p", "q"),
            balance=-7461,
            on=day(3),
        ),
    )
    assert counts(pull) == (0, 1, 1, 0)
    assert (pull.feed_total_cents, pull.drift_cents) == (2539, 0)


def test_drift_is_what_the_balance_moved_beyond_the_posted_rows(session: Session) -> None:
    apply_feed(session, 1, feed(tx("a", 1, -450, "ACME"), balance=-10450, on=day(1)))
    pull = apply_feed(session, 1, feed(tx("b", 2, -1299, "FOOBAR"), balance=-11800, on=day(2)))
    assert pull.drift_cents == -51
    pull = apply_feed(session, 1, feed(tx("c", 3, -100, "ACME"), balance=-11849, on=day(3)))
    assert pull.drift_cents == 51
    pull = apply_feed(session, 1, feed(balance=-11849, on=day(4)))
    assert pull.drift_cents == 0


def test_drift_looks_back_to_the_last_pull_that_had_a_balance(session: Session) -> None:
    apply_feed(session, 1, feed(tx("a", 1, -450, "ACME"), balance=-10450, on=day(1)))
    middle = apply_feed(session, 1, feed(tx("b", 2, -1299, "FOOBAR")))
    assert (middle.balance_cents, middle.drift_cents, middle.feed_total_cents) == (
        None,
        None,
        -1749,
    )
    pull = apply_feed(session, 1, feed(tx("c", 3, -1, "ACME"), balance=-11750, on=day(3)))
    assert pull.drift_cents == 0
    stored = session.scalars(select(FeedPullRow).order_by(FeedPullRow.id)).all()
    assert [(row.balance_cents, row.drift_cents) for row in stored] == [
        (-10450, None),
        (None, None),
        (-11750, 0),
    ]


def test_drift_is_kept_per_account(session: Session) -> None:
    apply_feed(session, 1, feed(tx("a", 1, -450, "ACME"), balance=-10450, on=day(1)))
    first = apply_feed(session, 2, feed(tx("a", 1, 2500, "PAYROLL"), balance=90000, on=day(1)))
    assert first.drift_cents is None
    second = apply_feed(session, 2, feed(tx("b", 2, -2000, "RENT"), balance=88000, on=day(2)))
    assert second.drift_cents == 0


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (feed(tx("", 1, -1, "ACME")), "feed has an unusable transaction id"),
        (feed(tx(" a", 1, -1, "ACME")), "feed has an unusable transaction id"),
        (feed(tx("x" * 101, 1, -1, "ACME")), "feed has an unusable transaction id"),
        (
            feed(tx("b", 1, -1, "ACME", replaces_feed_id="")),
            "feed has an unusable transaction id",
        ),
        (feed(removed=("a ",)), "feed has an unusable transaction id"),
        (feed(tx("b", 1, -1, " \t ")), "feed has an empty description"),
        (feed(tx("b", 1, -1, "ACME", card_last4="12a4")), "feed has unusable card digits"),
        (
            feed(tx("b", 1, -1, "ACME"), tx("b", 2, -2, "FOOBAR")),
            "feed has a duplicate transaction id",
        ),
        (
            feed(tx("b", 1, -1, "ACME"), removed=("b",)),
            "feed removes a transaction it also delivers",
        ),
        (feed(balance=-100), "feed balance and its date must come together"),
        (feed(on=day(1)), "feed balance and its date must come together"),
    ],
)
def test_a_feed_that_cannot_be_applied_writes_nothing(
    session: Session, bad: AccountFeed, message: str
) -> None:
    apply_feed(session, 1, feed(tx("a", 1, -450, "ACME COFFEE")))
    before = ledger(session)
    whole = AccountFeed(
        [tx("good", 5, -5, "GOOD ROW"), *bad.transactions],
        ["a", *bad.removed_feed_ids],
        bad.balance_cents,
        bad.balance_date,
    )
    with pytest.raises(FeedError) as caught:
        apply_feed(session, 1, whole)
    assert str(caught.value) == message
    assert ledger(session) == before
    assert len(session.scalars(select(FeedPullRow)).all()) == 1
    assert session.scalars(select(BalanceSnapshotRow)).all() == []


def test_an_unknown_account(session: Session) -> None:
    with pytest.raises(FeedError) as caught:
        apply_feed(session, 99, feed(tx("a", 1, -450, "ACME COFFEE")))
    assert str(caught.value) == "account not found"
    assert session.scalars(select(TransactionRow)).all() == []


def test_a_long_id_and_a_long_description(session: Session) -> None:
    apply_feed(session, 1, feed(tx("x" * 100, 1, -1, "A" * 499 + " " + "B" * 10)))
    row = session.get(TransactionRow, 1)
    assert row.description == "A" * 499
    assert session.scalars(select(FeedItemRow.feed_id)).one() == "x" * 100
    assert counts(
        apply_feed(session, 1, feed(tx("x" * 100, 1, -1, "A" * 499 + " " + "B" * 10)))
    ) == (
        0,
        0,
        0,
        1,
    )
