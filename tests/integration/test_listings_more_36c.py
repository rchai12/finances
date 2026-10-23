from datetime import date

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.backups import backup_files
from finances.analysis.simplefin import mapping_status
from finances.analysis.transfers import pair_of, suggestion_listing
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_transfer_pair, map_feed_account
from finances.domain.models import CONFIRMED


def add_transaction(session: Session, account_id: int, day: int, cents: int) -> int:
    row = TransactionRow(
        account_id=account_id,
        posted_date=date(2026, 5, day),
        amount_cents=cents,
        description="PROBE TRANSFER",
        source="statement",
        fingerprint=f"p{account_id}-{day}-{cents}".ljust(64, "0")[:64],
    )
    session.add(row)
    session.flush()
    return row.id


def test_pair_of_each_side_and_a_transaction_in_none(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        out_id = add_transaction(session, checking.id, 3, -2000)
        in_id = add_transaction(session, savings.id, 4, 2000)
        other = add_transaction(session, checking.id, 5, -1250)
        pair = create_transfer_pair(session, out_id, in_id, CONFIRMED)
        from_out = pair_of(session, out_id)
        from_in = pair_of(session, in_id)
        assert from_out is not None and from_in is not None
        assert from_out.pair.id == from_in.pair.id == pair.id
        assert (from_out.out.id, from_out.into.id) == (out_id, in_id)
        assert pair_of(session, other) is None


def test_mapping_status_asks_the_keychain_once_for_two_mappings_under_one_link(
    db_engine: Engine,
) -> None:
    with session_scope(db_engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        map_feed_account(session, card.id, "ACT-1", "alex")
        map_feed_account(session, checking.id, "ACT-2", "alex")
        asked: list[str] = []

        def keychain(link: str) -> str:
            asked.append(link)
            return "yes"

        found = mapping_status(session, keychain)
        assert [item.feed_account for item in found] == ["ACT-1", "ACT-2"]
        assert [item.keychain for item in found] == ["yes", "yes"]
        assert asked == ["alex"]


def test_backup_files_on_an_empty_list() -> None:
    assert backup_files([]) == []


def test_suggestion_listing_with_nothing_waiting(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Checking", "Test Bank", "checking")
        assert suggestion_listing(session) == []
