from datetime import date

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import BalanceSnapshotRow, StatementRow, TransactionRow
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    create_statement,
    existing_fingerprints,
    find_statement_by_hash,
    insert_transactions,
    latest_balance,
    list_statements,
    list_transactions,
)
from finances.domain.models import DataSource, NewTransaction


def test_create_statement_returns_the_row_and_a_later_session_sees_it(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        account = create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
        made = create_statement(
            session,
            account_id=account.id,
            source_filename="feb.pdf",
            file_sha256="b" * 64,
            parser_name="fake_bank",
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
            opening_balance_cents=-(2**40),
            closing_balance_cents=7,
            lines_parsed=3,
            rows_inserted=2,
            rows_duplicate=1,
        )
        assert made.id == 1
        assert made.imported_at.utcoffset() is not None
        assert made.opening_balance_cents == -(2**40)
        assert find_statement_by_hash(session, "b" * 64) == made
        assert find_statement_by_hash(session, "c" * 64) is None
    with session_scope(db_engine) as session:
        found = find_statement_by_hash(session, "b" * 64)
        assert found is not None
        assert found.source_filename == "feb.pdf"
        assert found.rows_duplicate == 1


def test_list_statements_is_latest_period_then_highest_id(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        first = create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
        second = create_account(session, "Test Checking", "Test Bank", "checking", last4="2222")
        _statement(session, first.id, "feb.pdf", "b" * 64, date(2026, 2, 28))
        _statement(session, second.id, "jan.pdf", "a" * 64, date(2026, 1, 31))
        _statement(session, first.id, "feb-again.pdf", "d" * 64, date(2026, 2, 28))
        names = [item.source_filename for item in list_statements(session)]
        assert names == ["feb-again.pdf", "feb.pdf", "jan.pdf"]
        assert [item.source_filename for item in list_statements(session, second.id)] == ["jan.pdf"]
        assert list_statements(session, 99) == []


def test_existing_fingerprints_keeps_to_one_account_across_chunks(db_engine: Engine) -> None:
    kept = f"{600:064d}"
    other = "b" * 64
    with session_scope(db_engine) as session:
        first = create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
        second = create_account(session, "Test Checking", "Test Bank", "checking", last4="2222")
        insert_transactions(
            session,
            [
                _new(first.id, kept),
                _new(second.id, kept, day=2),
                _new(second.id, other, day=3),
            ],
        )

        def asked():
            yield from (f"{number:064d}" for number in range(1100))
            yield other

        found = existing_fingerprints(session, first.id, asked())
        assert type(found) is set
        assert found == {kept}
        assert existing_fingerprints(session, second.id, iter([kept, other, "c" * 64])) == {
            kept,
            other,
        }
        assert existing_fingerprints(session, first.id, []) == set()
        assert existing_fingerprints(session, first.id, iter(())) == set()


def test_insert_transactions_copies_every_field_and_returns_the_count(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        account = create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
        statement = _statement(session, account.id, "feb.pdf", "b" * 64, date(2026, 2, 28))
        row = NewTransaction(
            account_id=account.id,
            statement_id=statement.id,
            posted_date=date(2026, 2, 5),
            transaction_date=date(2026, 2, 4),
            amount_cents=-9007199254740993,
            description="ACME COFFEE",
            section="purchases",
            card_last4="2222",
            cardholder="A PERSON",
            external_id="7838",
            source=DataSource.AGGREGATOR,
            is_pending=True,
            fingerprint="f" * 64,
        )
        assert insert_transactions(session, [row]) == 1
        assert insert_transactions(session, []) == 0
        stored = list_transactions(session, account_id=account.id)
        assert len(stored) == 1
        found = stored[0]
        assert found.statement_id == statement.id
        assert found.amount_cents == -9007199254740993
        assert found.source is DataSource.AGGREGATOR
        assert found.is_pending is True
        assert found.transaction_date == date(2026, 2, 4)
        assert (found.section, found.card_last4, found.cardholder, found.external_id) == (
            "purchases",
            "2222",
            "A PERSON",
            "7838",
        )
        assert found.created_at.utcoffset() is not None


def test_list_transactions_orders_by_date_then_id_and_includes_both_ends(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        account = create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
        other = create_account(session, "Test Checking", "Test Bank", "checking", last4="2222")
        insert_transactions(
            session,
            [
                _new(account.id, "a" * 64, day=2, amount=-2),
                _new(account.id, "b" * 64, day=2, amount=-1),
                _new(account.id, "c" * 64, day=1, amount=-3),
                _new(account.id, "d" * 64, day=3, amount=-4),
                _new(other.id, "e" * 64, day=3, amount=-5),
            ],
        )
        ordered = list_transactions(session, account_id=account.id, limit=10)
        assert [(item.posted_date.day, item.amount_cents) for item in ordered] == [
            (3, -4),
            (2, -1),
            (2, -2),
            (1, -3),
        ]
        both = list_transactions(
            session, account_id=account.id, start=date(2026, 2, 2), end=date(2026, 2, 2), limit=10
        )
        assert {item.posted_date for item in both} == {date(2026, 2, 2)}
        assert len(both) == 2
        assert {
            item.posted_date.day
            for item in list_transactions(session, start=date(2026, 2, 3), limit=10)
        } == {3}
        assert {
            item.posted_date.day
            for item in list_transactions(session, end=date(2026, 2, 1), limit=10)
        } == {1}
        only_other = list_transactions(session, account_id=other.id)
        assert len(only_other) == 1
        assert only_other[0].fingerprint == "e" * 64


def test_list_transactions_defaults_to_100_rows(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        account = create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
        insert_transactions(
            session,
            [
                _new(account.id, f"{number:064d}", day=1 + (number % 28), amount=-number)
                for number in range(101)
            ],
        )
        found = list_transactions(session)
        assert len(found) == 100
        assert found[0].posted_date >= found[-1].posted_date


def test_list_transactions_rejects_a_limit_below_one(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        with pytest.raises(ValueError) as caught:
            list_transactions(session, limit=0)
        assert str(caught.value) == "limit must be at least 1"
        with pytest.raises(ValueError) as negative:
            list_transactions(session, limit=-5)
        assert str(negative.value) == "limit must be at least 1"


def test_add_balance_snapshot_keeps_the_first_balance_for_a_day(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        account = create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
        other = create_account(session, "Test Checking", "Test Bank", "checking", last4="2222")
        assert latest_balance(session, account.id) is None
        first = add_balance_snapshot(
            session, account.id, date(2026, 2, 28), -12345, DataSource.STATEMENT
        )
        again = add_balance_snapshot(
            session, account.id, date(2026, 2, 28), 999, DataSource.STATEMENT
        )
        assert again == first
        assert again.balance_cents == -12345
        add_balance_snapshot(session, account.id, date(2026, 2, 28), 5, DataSource.AGGREGATOR)
        add_balance_snapshot(session, account.id, date(2026, 1, 31), 1, DataSource.STATEMENT)
        add_balance_snapshot(session, other.id, date(2026, 6, 30), 2, DataSource.STATEMENT)
        count = session.scalar(
            select(func.count())
            .select_from(BalanceSnapshotRow)
            .where(BalanceSnapshotRow.account_id == account.id)
        )
        assert count == 3
        latest = latest_balance(session, account.id)
        assert latest is not None
        assert (latest.as_of_date, latest.balance_cents, latest.source) == (
            date(2026, 2, 28),
            5,
            DataSource.AGGREGATOR,
        )
        assert latest_balance(session, other.id).balance_cents == 2
        assert latest_balance(session, 99) is None


def test_repository_writes_are_not_committed(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        account = create_account(session, "Test Card", "Test Bank", "credit_card", last4="1111")
        account_id = account.id
    session = Session(db_engine)
    create_statement(
        session,
        account_id=account_id,
        source_filename="feb.pdf",
        file_sha256="b" * 64,
        parser_name="fake_bank",
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 28),
        opening_balance_cents=0,
        closing_balance_cents=0,
        lines_parsed=0,
        rows_inserted=0,
        rows_duplicate=0,
    )
    insert_transactions(session, [_new(account_id, "f" * 64)])
    add_balance_snapshot(session, account_id, date(2026, 2, 28), -50, DataSource.STATEMENT)
    session.rollback()
    session.close()
    with session_scope(db_engine) as session:
        assert session.scalar(select(func.count()).select_from(StatementRow)) == 0
        assert session.scalar(select(func.count()).select_from(TransactionRow)) == 0
        assert session.scalar(select(func.count()).select_from(BalanceSnapshotRow)) == 0


def _statement(session: Session, account_id: int, name: str, digest: str, period_end: date):
    return create_statement(
        session,
        account_id=account_id,
        source_filename=name,
        file_sha256=digest,
        parser_name="fake_bank",
        period_start=date(period_end.year, period_end.month, 1),
        period_end=period_end,
        opening_balance_cents=0,
        closing_balance_cents=0,
        lines_parsed=0,
        rows_inserted=0,
        rows_duplicate=0,
    )


def _new(account_id: int, fingerprint: str, day: int = 5, amount: int = -450) -> NewTransaction:
    return NewTransaction(
        account_id=account_id,
        statement_id=None,
        posted_date=date(2026, 2, day),
        transaction_date=None,
        amount_cents=amount,
        description="ACME COFFEE",
        section=None,
        card_last4=None,
        cardholder=None,
        external_id=None,
        source=DataSource.STATEMENT,
        is_pending=False,
        fingerprint=fingerprint,
    )
