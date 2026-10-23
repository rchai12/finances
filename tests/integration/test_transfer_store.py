import json
from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from finances.analysis.transfers import pair_listing
from finances.categorize.transfers import TransferResult, pair_transfers, transfer_suggestions
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow, TransferPairRow, TransferRejectionRow
from finances.db.repositories import (
    create_account,
    create_transfer_pair,
    delete_feed_transaction,
    insert_feed_transaction,
    list_transfer_movements,
    list_transfer_pairs,
    list_transfer_rejections,
    map_feed_account,
    reject_transfer,
    unpair_transfer,
)
from finances.domain.models import AUTO, CONFIRMED, DataSource, NewTransaction, TransferPair
from finances.domain.transfers import Movement
from finances.sync import transport
from finances.views.transfers import transfer_lines
from finances.web.app import create_app

CHECKING, SAVINGS, CARD = 1, 2, 3
NOT_FOUND = "transaction not found"
SAME_ACCOUNT = "a transfer goes from one account to another"
NOT_MATCHING = "a transfer pairs money out with the same amount in"


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    """A migrated database with Test Checking (1), Test Savings (2), and Test Card (3)."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Checking", "Test Bank", "checking")
        create_account(opened, "Test Savings", "Test Bank", "savings")
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        yield opened


def add(session: Session, account: int, day: int, cents: int, *, pending: bool = False) -> int:
    row = TransactionRow(
        account_id=account,
        posted_date=date(2026, 5, day),
        amount_cents=cents,
        description="PROBE TRANSFER",
        source="statement",
        is_pending=pending,
        fingerprint=f"s{account}-{day}-{cents}".ljust(64, "0"),
    )
    session.add(row)
    session.flush()
    return row.id


def add_feed(session: Session, account: int, day: int, cents: int, feed_id: str) -> int:
    item = NewTransaction(
        account_id=account,
        statement_id=None,
        posted_date=date(2026, 5, day),
        transaction_date=None,
        amount_cents=cents,
        description="PROBE TRANSFER",
        section=None,
        card_last4=None,
        cardholder=None,
        external_id=None,
        source=DataSource.AGGREGATOR,
        is_pending=False,
        fingerprint=feed_id.ljust(64, "0"),
    )
    return insert_feed_transaction(session, item, feed_id).id


def count(session: Session, row_class: type) -> int:
    return session.scalar(select(func.count()).select_from(row_class))


# Movements


def test_movements_leave_out_pending_zero_and_paired(session: Session) -> None:
    out_id = add(session, CHECKING, 3, -500)
    in_id = add(session, SAVINGS, 3, 500)
    add(session, CHECKING, 4, -700, pending=True)
    add(session, SAVINGS, 4, 0)
    kept = add(session, CARD, 5, 1250)
    create_transfer_pair(session, out_id, in_id, CONFIRMED)
    assert list_transfer_movements(session) == [Movement(kept, CARD, 1250, date(2026, 5, 5))]


# Pairing by hand


@pytest.mark.parametrize(
    ("sides", "message"),
    [
        ((99, "in"), NOT_FOUND),
        (("out", 99), NOT_FOUND),
        (("out", "same"), SAME_ACCOUNT),
        (("in", "out"), NOT_MATCHING),
        (("out", "other"), NOT_MATCHING),
    ],
)
def test_a_refused_pair(session: Session, sides: tuple, message: str) -> None:
    made = {
        "out": add(session, CHECKING, 3, -500),
        "in": add(session, SAVINGS, 3, 500),
        "same": add(session, CHECKING, 4, 500),
        "other": add(session, SAVINGS, 4, 499),
    }
    out_id, in_id = (made.get(side, side) for side in sides)
    with pytest.raises(ValueError, match=f"^{message}$"):
        create_transfer_pair(session, out_id, in_id, CONFIRMED)
    assert list_transfer_pairs(session) == []


def test_either_side_already_in_a_transfer(session: Session) -> None:
    out_id = add(session, CHECKING, 3, -500)
    in_id = add(session, SAVINGS, 3, 500)
    other_out = add(session, CARD, 3, -500)
    other_in = add(session, CARD, 4, 500)
    create_transfer_pair(session, out_id, in_id, AUTO)
    with pytest.raises(ValueError, match=f"^transaction {out_id} is already in a transfer$"):
        create_transfer_pair(session, out_id, other_in, CONFIRMED)
    with pytest.raises(ValueError, match=f"^transaction {in_id} is already in a transfer$"):
        create_transfer_pair(session, other_out, in_id, CONFIRMED)


def test_the_out_side_is_named_before_the_in_side(session: Session) -> None:
    out_id = add(session, CHECKING, 3, -500)
    in_id = add(session, SAVINGS, 3, 500)
    other_out = add(session, CARD, 3, -500)
    other_in = add(session, CARD, 4, 500)
    create_transfer_pair(session, out_id, other_in, AUTO)
    create_transfer_pair(session, other_out, in_id, AUTO)
    with pytest.raises(ValueError, match=f"^transaction {out_id} is already in a transfer$"):
        create_transfer_pair(session, out_id, in_id, CONFIRMED)


def test_a_wrong_status(session: Session) -> None:
    out_id = add(session, CHECKING, 3, -500)
    in_id = add(session, SAVINGS, 3, 500)
    with pytest.raises(ValueError, match="^status must be auto or confirmed$"):
        create_transfer_pair(session, out_id, in_id, "maybe")


def test_confirming_removes_a_rejection(session: Session) -> None:
    out_id = add(session, CHECKING, 3, -500)
    in_id = add(session, SAVINGS, 3, 500)
    reject_transfer(session, out_id, in_id)
    made = create_transfer_pair(session, out_id, in_id, CONFIRMED)
    assert made == TransferPair(made.id, out_id, in_id, CONFIRMED)
    assert list_transfer_rejections(session) == set()
    assert list_transfer_pairs(session) == [made]


# Rejecting and unpairing


def test_rejecting_twice_keeps_one_row(session: Session) -> None:
    out_id = add(session, CHECKING, 3, -500)
    in_id = add(session, SAVINGS, 3, 500)
    reject_transfer(session, out_id, in_id)
    reject_transfer(session, out_id, in_id)
    assert count(session, TransferRejectionRow) == 1
    assert list_transfer_rejections(session) == {(out_id, in_id)}


def test_rejecting_removes_only_that_pair(session: Session) -> None:
    out_id = add(session, CHECKING, 3, -500)
    in_id = add(session, SAVINGS, 3, 500)
    other_out = add(session, CHECKING, 4, -900)
    other_in = add(session, CARD, 4, 900)
    create_transfer_pair(session, out_id, in_id, AUTO)
    kept = create_transfer_pair(session, other_out, other_in, AUTO)
    reject_transfer(session, out_id, in_id)
    assert list_transfer_pairs(session) == [kept]


@pytest.mark.parametrize("sides", [(99, "in"), ("in", "out")])
def test_a_refused_rejection(session: Session, sides: tuple) -> None:
    made = {"out": add(session, CHECKING, 3, -500), "in": add(session, SAVINGS, 3, 500)}
    out_id, in_id = (made.get(side, side) for side in sides)
    with pytest.raises(ValueError):
        reject_transfer(session, out_id, in_id)
    assert list_transfer_rejections(session) == set()


def test_unpairing_records_a_rejection(session: Session) -> None:
    out_id = add(session, CHECKING, 3, -500)
    in_id = add(session, SAVINGS, 3, 500)
    made = create_transfer_pair(session, out_id, in_id, AUTO)
    assert unpair_transfer(session, made.id) == made
    assert list_transfer_pairs(session) == []
    assert list_transfer_rejections(session) == {(out_id, in_id)}


def test_unpairing_an_unknown_transfer(session: Session) -> None:
    with pytest.raises(ValueError, match="^transfer not found$"):
        unpair_transfer(session, 9)


# A feed row that goes away


def test_a_paired_feed_row_can_be_deleted(session: Session) -> None:
    out_id = add(session, CHECKING, 3, -500)
    in_id = add_feed(session, SAVINGS, 3, 500, "F-1")
    create_transfer_pair(session, out_id, in_id, AUTO)
    assert delete_feed_transaction(session, in_id) is True
    assert list_transfer_pairs(session) == []
    assert session.get(TransactionRow, out_id) is not None


def test_a_rejected_feed_row_can_be_deleted(session: Session) -> None:
    out_id = add_feed(session, CHECKING, 3, -500, "F-1")
    in_id = add(session, SAVINGS, 3, 500)
    other_in = add(session, CARD, 3, 500)
    reject_transfer(session, out_id, in_id)
    reject_transfer(session, out_id, other_in)
    assert delete_feed_transaction(session, out_id) is True
    assert list_transfer_rejections(session) == set()


# The service and the lines


def test_pairing_with_a_rejection(session: Session) -> None:
    out_id = add(session, CHECKING, 3, -500)
    in_id = add(session, SAVINGS, 4, 500)
    other_in = add(session, CARD, 5, 500)
    second_out = add(session, CHECKING, 10, -900)
    second_in = add(session, SAVINGS, 10, 900)
    second_other = add(session, CARD, 11, 900)
    assert transfer_suggestions(session) == [
        (out_id, in_id),
        (out_id, other_in),
        (second_out, second_in),
        (second_out, second_other),
    ]
    reject_transfer(session, out_id, other_in)
    assert transfer_suggestions(session) == [(second_out, second_in), (second_out, second_other)]
    assert pair_transfers(session) == TransferResult(paired=1, waiting=2)
    assert list_transfer_pairs(session)[0].status == AUTO
    assert transfer_suggestions(session) == [(second_out, second_in), (second_out, second_other)]
    assert pair_transfers(session) == TransferResult(paired=0, waiting=2)


def test_transfer_lines_latest_outflow_first_then_highest_pair(session: Session) -> None:
    early_out, early_in = add(session, CHECKING, 2, -500), add(session, SAVINGS, 3, 500)
    late_out, late_in = add(session, CHECKING, 9, -2599), add(session, CARD, 9, 2599)
    same_out, same_in = add(session, SAVINGS, 9, -100), add(session, CHECKING, 9, 100)
    create_transfer_pair(session, late_out, late_in, AUTO)
    create_transfer_pair(session, early_out, early_in, CONFIRMED)
    create_transfer_pair(session, same_out, same_in, AUTO)
    lines = transfer_lines(pair_listing(session))
    assert [line.pair for line in lines] == ["3", "1", "2"]
    first = lines[1]
    assert (first.date, first.from_account, first.to_account, first.amount, first.how) == (
        "2026-05-09",
        "Test Checking",
        "Test Card",
        "$25.99",
        "auto",
    )
    assert (first.out_id, first.in_id) == (str(late_out), str(late_in))


# Sync now


def test_sync_now_pairs_a_clear_transfer_the_feed_brought(
    tmp_settings: Settings, keychain, monkeypatch: pytest.MonkeyPatch
) -> None:
    upgrade_to_head()
    noon = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Checking", "Test Bank", "checking")
        create_account(session, "Test Savings", "Test Bank", "savings")
        out_id = add(session, CHECKING, 1, -2000)
        session.get(TransactionRow, out_id).posted_date = noon.date()
        map_feed_account(session, SAVINGS, "ACT-1", "kim")
    keychain.passwords[("finances-simplefin", "kim")] = "https://u:p@bridge.simplefin.org/x"
    stamp = int(noon.timestamp())
    body = {
        "errlist": [],
        "connections": [{"conn_id": "C", "name": "Test Bank", "org_id": "O", "sfin_url": "x"}],
        "accounts": [
            {
                "id": "ACT-1",
                "name": "Savings",
                "conn_id": "C",
                "currency": "USD",
                "balance": "20.00",
                "balance-date": stamp,
                "transactions": [
                    {"id": "F1", "posted": stamp, "amount": "20.00", "description": "FROM CHECKING"}
                ],
            }
        ],
    }
    monkeypatch.setattr(transport, "urllib_transport", lambda *_: (200, json.dumps(body).encode()))
    port = 8765
    client = TestClient(create_app(port), base_url=f"http://127.0.0.1:{port}")
    client.get("/sync")
    response = client.post(
        "/sync/run", data={"csrf": client.cookies["fin_csrf"]}, follow_redirects=False
    )
    assert response.status_code == 200
    with session_scope(engine) as session:
        pairs = list_transfer_pairs(session)
        assert [(pair.out_transaction_id, pair.status) for pair in pairs] == [(out_id, AUTO)]
        assert count(session, TransferPairRow) == 1
    engine.dispose()
