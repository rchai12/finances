from datetime import date, timedelta

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import FeedItemRow
from finances.db.repositories import (
    confirm_transaction,
    create_account,
    create_statement,
    find_feed_transactions,
    find_unlinked_statement_transactions,
    insert_feed_transaction,
    insert_transactions,
    link_feed_transaction,
    list_provisional_transactions,
    statement_covers,
)
from finances.domain.models import DataSource, NewTransaction, Statement, Transaction

START = date(2026, 5, 1)
END = date(2026, 5, 31)


def new(
    day: date,
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
        posted_date=day,
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


def fed(session: Session, feed_id: str, day: date, **changes: object) -> Transaction:
    return insert_feed_transaction(session, new(day, fingerprint=feed_id * 64, **changes), feed_id)


def stored(session: Session, day: date, fingerprint: str, **changes: object) -> Transaction:
    insert_transactions(
        session,
        [new(day, source=DataSource.STATEMENT, fingerprint=fingerprint, **changes)],
    )
    rows = find_unlinked_statement_transactions(
        session, changes.get("account_id", 1), changes.get("cents", -450), day, day
    )
    return next(row for row in rows if row.fingerprint == fingerprint)


def statement(
    session: Session, start: date = START, end: date = END, account_id: int = 1, digest: str = "1"
) -> Statement:
    return create_statement(
        session,
        account_id=account_id,
        source_filename="statement.pdf",
        file_sha256=digest * 64,
        parser_name="test",
        period_start=start,
        period_end=end,
        opening_balance_cents=0,
        closing_balance_cents=0,
        lines_parsed=0,
        rows_inserted=0,
        rows_duplicate=0,
    )


@pytest.fixture
def session(db_engine: Engine):
    """A session with a card (id 1) and a checking account (id 2)."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card", last4="1111")
        create_account(opened, "Test Checking", "Test Bank", "checking")
        yield opened


# ----- list_provisional_transactions (R5) -----


def test_provisional_rows_leave_out_other_accounts_pending_and_statement_rows(
    session: Session,
) -> None:
    kept = fed(session, "a", date(2026, 5, 10))
    fed(session, "b", date(2026, 5, 10), account_id=2)
    fed(session, "c", date(2026, 5, 10), pending=True)
    stored(session, date(2026, 5, 10), "d" * 64)
    assert list_provisional_transactions(session, 1, START, END) == [kept]


def test_provisional_rows_include_both_ends_of_the_range_in_id_order(session: Session) -> None:
    last = fed(session, "a", END)
    fed(session, "b", END + timedelta(days=1))
    fed(session, "c", START - timedelta(days=1))
    first = fed(session, "d", START)
    found = list_provisional_transactions(session, 1, START, END)
    assert [row.id for row in found] == [last.id, first.id]


# ----- confirm_transaction (R6) -----


def confirm(session: Session, transaction_id: int, statement_id: int) -> Transaction:
    return confirm_transaction(
        session,
        transaction_id,
        statement_id=statement_id,
        posted_date=date(2026, 5, 12),
        transaction_date=date(2026, 5, 11),
        description="ACME COFFEE STORE",
        section="purchases",
        card_last4="1111",
        cardholder="TEST HOLDER",
        external_id="REF1",
        fingerprint="f" * 64,
    )


def test_confirm_changes_eleven_columns_and_keeps_the_rest(session: Session) -> None:
    before = fed(session, "a", date(2026, 5, 10), pending=True)
    held = statement(session)
    after = confirm(session, before.id, held.id)
    assert (
        after.statement_id,
        after.posted_date,
        after.transaction_date,
        after.description,
        after.section,
        after.card_last4,
        after.cardholder,
        after.external_id,
        after.fingerprint,
        after.source,
        after.is_pending,
    ) == (
        held.id,
        date(2026, 5, 12),
        date(2026, 5, 11),
        "ACME COFFEE STORE",
        "purchases",
        "1111",
        "TEST HOLDER",
        "REF1",
        "f" * 64,
        DataSource.STATEMENT,
        False,
    )
    assert (after.id, after.account_id, after.amount_cents, after.created_at) == (
        before.id,
        before.account_id,
        before.amount_cents,
        before.created_at,
    )
    assert find_feed_transactions(session, 1, ["a"]) == {"a": after}


def test_confirm_works_on_a_row_without_a_feed_id(session: Session) -> None:
    row = stored(session, date(2026, 5, 10), "d" * 64)
    after = confirm(session, row.id, statement(session).id)
    assert (after.id, after.fingerprint) == (row.id, "f" * 64)


def test_confirm_an_unknown_row_raises(session: Session) -> None:
    held = statement(session)
    with pytest.raises(ValueError) as caught:
        confirm(session, 99, held.id)
    assert str(caught.value) == "transaction not found"


# ----- find_unlinked_statement_transactions (R7) -----


def test_unlinked_rows_leave_out_accounts_sources_amounts_and_linked_rows(
    session: Session,
) -> None:
    day = date(2026, 5, 10)
    kept = stored(session, day, "1" * 64)
    stored(session, day, "2" * 64, account_id=2)
    fed(session, "a", day)
    stored(session, day, "3" * 64, cents=-451)
    linked = stored(session, day, "4" * 64)
    link_feed_transaction(session, 1, "b", linked.id)
    assert find_unlinked_statement_transactions(session, 1, -450, START, END) == [kept]


def test_unlinked_rows_include_both_ends_of_the_range_in_id_order(session: Session) -> None:
    last = stored(session, END, "1" * 64)
    stored(session, END + timedelta(days=1), "2" * 64)
    stored(session, START - timedelta(days=1), "3" * 64)
    first = stored(session, START, "4" * 64)
    found = find_unlinked_statement_transactions(session, 1, -450, START, END)
    assert [row.id for row in found] == [last.id, first.id]


# ----- link_feed_transaction (R8) -----


def test_link_stores_the_feed_id(session: Session) -> None:
    row = stored(session, date(2026, 5, 10), "1" * 64)
    assert link_feed_transaction(session, 1, "a", row.id) is None
    item = session.scalars(select(FeedItemRow)).one()
    assert (item.account_id, item.feed_id, item.transaction_id) == (1, "a", row.id)
    assert find_feed_transactions(session, 1, ["a"]) == {"a": row}


def test_link_the_same_feed_id_twice_in_one_account_fails(session: Session) -> None:
    first = stored(session, date(2026, 5, 10), "1" * 64)
    second = stored(session, date(2026, 5, 10), "2" * 64)
    link_feed_transaction(session, 1, "a", first.id)
    with pytest.raises(IntegrityError):
        link_feed_transaction(session, 1, "a", second.id)
    session.rollback()


def test_link_two_feed_ids_to_one_transaction_fails(session: Session) -> None:
    row = stored(session, date(2026, 5, 10), "1" * 64)
    link_feed_transaction(session, 1, "a", row.id)
    with pytest.raises(IntegrityError):
        link_feed_transaction(session, 1, "b", row.id)
    session.rollback()


# ----- statement_covers (R9) -----


def test_covers_is_false_with_no_statement(session: Session) -> None:
    assert statement_covers(session, 1, date(2026, 5, 10)) is False


def test_covers_holds_from_the_first_to_the_last_day_only(session: Session) -> None:
    statement(session)
    assert statement_covers(session, 1, START) is True
    assert statement_covers(session, 1, END) is True
    assert statement_covers(session, 1, START - timedelta(days=1)) is False
    assert statement_covers(session, 1, END + timedelta(days=1)) is False


def test_covers_ignores_another_accounts_statement(session: Session) -> None:
    statement(session, account_id=2)
    assert statement_covers(session, 1, date(2026, 5, 10)) is False


def test_covers_finds_the_day_in_the_second_of_two_statements(session: Session) -> None:
    statement(session)
    statement(session, date(2026, 6, 1), date(2026, 6, 30), digest="2")
    assert statement_covers(session, 1, date(2026, 6, 15)) is True
