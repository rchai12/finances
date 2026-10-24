from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.shared import owed_report
from finances.categorize.transfers import pair_transfers
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_person,
    create_transfer_pair,
    delete_feed_transaction,
    delete_settlement,
    insert_feed_transaction,
    list_changes,
    list_settlements,
    list_shares,
    record_settlement,
    set_account_owner,
    set_cardholder_alias,
    share_transaction,
    unshare_transaction,
    update_feed_transaction,
)
from finances.domain.audit import SYSTEM
from finances.domain.models import CONFIRMED, DataSource, NewTransaction
from finances.domain.shared import Owed, Settlement, Share

DAY = date(2026, 5, 20)
JOINT = "say who paid: this transaction is joint or has no owner"
NOT_A_TRANSFER = "a shared transaction cannot be in a transfer"
SIZE = "a share must be more than zero and at most the transaction's amount"


def add(
    session: Session,
    account_id: int,
    day: int,
    cents: int,
    description: str,
    *,
    pending: bool = False,
    cardholder: str | None = None,
) -> int:
    row = TransactionRow(
        account_id=account_id,
        posted_date=date(2026, 5, day),
        amount_cents=cents,
        description=description,
        source="statement",
        is_pending=pending,
        cardholder=cardholder,
        fingerprint=f"{account_id}-{day}-{cents}-{int(pending)}".ljust(64, "0"),
    )
    session.add(row)
    session.flush()
    return row.id


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        sam = create_person(opened, "Sam")
        alex = create_person(opened, "Alex")
        card = create_account(opened, "Test Card", "Test Bank", "credit_card")
        checking = create_account(opened, "Test Checking", "Test Bank", "checking")
        savings = create_account(opened, "Test Savings", "Test Bank", "savings")
        set_account_owner(opened, card.id, sam.id)
        set_account_owner(opened, checking.id, None)
        set_cardholder_alias(opened, "ALEX CARD", alex.id)
        first = add(opened, card.id, 1, -2001, "FOOBAR GROCERY")
        second = add(opened, card.id, 2, -2000, "ACME COFFEE", cardholder="ALEX CARD")
        third = add(opened, checking.id, 3, -1800, "FOOBAR MARKET")
        fourth = add(opened, card.id, 4, -1500, "ACME PENDING", pending=True)
        fifth = add(opened, checking.id, 5, -5000, "PROBE TRANSFER")
        sixth = add(opened, savings.id, 5, 5000, "PROBE TRANSFER")
        assert (first, second, third, fourth, fifth, sixth) == (1, 2, 3, 4, 5, 6)
        yield opened


def add_feed(session: Session, feed_id: str) -> int:
    item = NewTransaction(
        account_id=1,
        statement_id=None,
        posted_date=date(2026, 5, 10),
        transaction_date=None,
        amount_cents=-2000,
        description="FOOBAR GROCERY",
        section=None,
        card_last4=None,
        cardholder=None,
        external_id=None,
        source=DataSource.AGGREGATOR,
        is_pending=False,
        fingerprint=feed_id.ljust(64, "0"),
    )
    return insert_feed_transaction(session, item, feed_id).id


def rewrite(
    session: Session,
    transaction_id: int,
    *,
    amount_cents: int,
    description: str,
    fingerprint: str,
    feed_id: str,
) -> None:
    update_feed_transaction(
        session,
        transaction_id,
        feed_id=feed_id,
        posted_date=date(2026, 5, 10),
        transaction_date=None,
        amount_cents=amount_cents,
        description=description,
        card_last4=None,
        is_pending=False,
        fingerprint=fingerprint,
    )


def test_sharing_uses_the_owner_and_replaces(session: Session) -> None:
    found = share_transaction(session, 1, "alex")
    assert found == Share(1, "Sam", "Alex", 1000)
    logged = list_changes(session, action="share_set")
    assert [(item.kind, item.record_id, item.before, item.after) for item in logged] == [
        ("transaction", 1, None, "Alex owes Sam")
    ]
    again = share_transaction(session, 1, "alex", size_cents=1200)
    assert again == Share(1, "Sam", "Alex", 1200)
    replaced = list_changes(session, action="share_set")
    assert (replaced[0].before, replaced[0].after) == ("Alex owes Sam", "Alex owes Sam")


def test_the_cardholder_comes_before_the_owner(session: Session) -> None:
    found = share_transaction(session, 2, "Sam")
    assert found == Share(2, "Alex", "Sam", 1000)


def test_a_joint_purchase_needs_who_paid(session: Session) -> None:
    with pytest.raises(ValueError) as caught:
        share_transaction(session, 3, "Alex")
    assert str(caught.value) == JOINT
    assert list_shares(session) == []
    found = share_transaction(session, 3, "Alex", payer="Sam")
    assert found == Share(3, "Sam", "Alex", 900)


def test_share_transaction_refusals_store_nothing(session: Session) -> None:
    with pytest.raises(ValueError) as missing:
        share_transaction(session, 99, "Alex")
    assert str(missing.value) == "transaction not found"
    with pytest.raises(ValueError) as pending:
        share_transaction(session, 4, "Nobody")
    assert str(pending.value) == "a pending transaction cannot be shared"
    with pytest.raises(ValueError) as nobody:
        share_transaction(session, 6, "Alex")
    assert str(nobody.value) == JOINT
    create_transfer_pair(session, 5, 6, CONFIRMED)
    with pytest.raises(ValueError) as paired:
        share_transaction(session, 5, "Alex")
    assert str(paired.value) == "a transfer cannot be shared"
    with pytest.raises(ValueError) as payer:
        share_transaction(session, 1, "Alex", payer="Nobody")
    assert str(payer.value) == "person not found"
    with pytest.raises(ValueError) as debtor:
        share_transaction(session, 1, "Nobody")
    assert str(debtor.value) == "person not found"
    with pytest.raises(ValueError) as self_owe:
        share_transaction(session, 1, "Sam")
    assert str(self_owe.value) == "a person cannot owe themselves"
    with pytest.raises(ValueError) as size:
        share_transaction(session, 1, "Alex", size_cents=0)
    assert str(size.value) == SIZE
    assert list_shares(session) == []


def test_unshare_removes_the_share(session: Session) -> None:
    share_transaction(session, 1, "Alex")
    unshare_transaction(session, 1)
    assert list_shares(session) == []
    cleared = list_changes(session, action="share_cleared")
    assert [(item.kind, item.record_id, item.before) for item in cleared] == [
        ("transaction", 1, "Alex owes Sam")
    ]
    with pytest.raises(ValueError) as missing:
        unshare_transaction(session, 99)
    assert str(missing.value) == "transaction not found"
    with pytest.raises(ValueError) as none:
        unshare_transaction(session, 1)
    assert str(none.value) == "the transaction is not shared"


def test_settlements_and_their_refusals(session: Session) -> None:
    found = record_settlement(session, "Alex", "Sam", 400, DAY)
    assert found == Settlement(1, "Alex", "Sam", 400, DAY)
    later = record_settlement(session, "Sam", "Alex", 100, date(2026, 5, 21))
    assert list_settlements(session) == [found, later]
    added = list_changes(session, action="settlement_added")
    assert [(item.kind, item.record_id, item.after) for item in added] == [
        ("settlement", 2, "Sam paid Alex"),
        ("settlement", 1, "Alex paid Sam"),
    ]
    deleted = delete_settlement(session, 1)
    assert deleted == found
    assert list_settlements(session) == [later]
    gone = list_changes(session, action="settlement_deleted")
    assert [(item.kind, item.record_id, item.before) for item in gone] == [
        ("settlement", 1, "Alex paid Sam")
    ]
    with pytest.raises(ValueError) as payer:
        record_settlement(session, "Nobody", "Sam", 400, DAY)
    assert str(payer.value) == "person not found"
    with pytest.raises(ValueError) as payee:
        record_settlement(session, "Alex", "Nobody", 400, DAY)
    assert str(payee.value) == "person not found"
    with pytest.raises(ValueError) as self_pay:
        record_settlement(session, "Alex", "Alex", 400, DAY)
    assert str(self_pay.value) == "a person cannot pay themselves"
    with pytest.raises(ValueError) as zero:
        record_settlement(session, "Alex", "Sam", 0, DAY)
    assert str(zero.value) == "a settlement must be more than zero"
    with pytest.raises(ValueError) as missing:
        delete_settlement(session, 99)
    assert str(missing.value) == "settlement not found"


def test_a_shared_transaction_is_never_a_transfer(session: Session) -> None:
    share_transaction(session, 5, "Alex", payer="Sam")
    assert pair_transfers(session).paired == 0
    with pytest.raises(ValueError) as caught:
        create_transfer_pair(session, 5, 6, CONFIRMED)
    assert str(caught.value) == NOT_A_TRANSFER


def test_feed_delete_and_amount_change_look_after_a_share(session: Session) -> None:
    deleted_id = add_feed(session, "gone-1")
    share_transaction(session, deleted_id, "Alex")
    assert delete_feed_transaction(session, deleted_id) is True
    assert list_shares(session) == []
    kept_id = add_feed(session, "keep-1")
    share_transaction(session, kept_id, "Alex")
    rewrite(
        session,
        kept_id,
        amount_cents=-1800,
        description="FOOBAR GROCERY",
        fingerprint="u" * 64,
        feed_id="post-1",
    )
    assert list_shares(session) == []
    cleared = list_changes(session, action="share_cleared")
    assert [(item.who, item.before, item.record_id) for item in cleared] == [
        (SYSTEM, "Alex owes Sam", kept_id)
    ]
    same_id = add_feed(session, "same-1")
    kept = share_transaction(session, same_id, "Alex")
    rewrite(
        session,
        same_id,
        amount_cents=-2000,
        description="FOOBAR MARKET",
        fingerprint="s" * 64,
        feed_id="post-2",
    )
    assert list_shares(session) == [kept]


def test_owed_report_after_a_share_and_a_settlement(session: Session) -> None:
    share_transaction(session, 1, "Alex")
    record_settlement(session, "Alex", "Sam", 400, DAY)
    assert owed_report(session) == [Owed("Alex", "Sam", 600)]
