from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_person, set_account_owner
from tests.support import failed_cleanly, run, table_rows

JOINT = "say who paid: this transaction is joint or has no owner"
PENDING = "a pending transaction cannot be shared"
NOT_MIGRATED = "database is not up to date (run: fin db upgrade)"


@pytest.fixture
def household(tmp_settings: Settings) -> Settings:
    """Sam and Alex; a joint checking purchase (1) and a pending card purchase (2)."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        sam = create_person(session, "Sam")
        create_person(session, "Alex")
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        set_account_owner(session, card.id, sam.id)
        set_account_owner(session, checking.id, None)
        session.add(
            TransactionRow(
                account_id=checking.id,
                posted_date=date(2026, 5, 1),
                amount_cents=-2000,
                description="FOOBAR MARKET",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
        session.add(
            TransactionRow(
                account_id=card.id,
                posted_date=date(2026, 5, 2),
                amount_cents=-1500,
                description="ACME PENDING",
                source="statement",
                is_pending=True,
                fingerprint="t02".ljust(64, "0"),
            )
        )
    engine.dispose()
    return tmp_settings


def test_paid_by_shares_a_joint_purchase(household: Settings) -> None:
    assert failed_cleanly(
        run("shared", "add", "--id", "1", "--with", "Alex"),
        JOINT,
    )
    stored = run("shared", "add", "--id", "1", "--with", "Alex", "--paid-by", "Sam")
    assert (stored.exit_code, stored.stdout) == (0, "Transaction 1: Alex owes Sam $10.00.\n")
    assert table_rows(run("shared", "list").stdout) == [
        ["ID", "Paid by", "Owes", "Owed"],
        ["1", "Sam", "Alex", "$10.00"],
    ]


def test_a_pending_purchase_cannot_be_shared(household: Settings) -> None:
    assert failed_cleanly(
        run("shared", "add", "--id", "2", "--with", "Alex"),
        PENDING,
    )


def test_list_needs_a_migrated_database(tmp_settings: Settings) -> None:
    assert failed_cleanly(run("shared", "list"), NOT_MIGRATED)
