from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_transfer_pair, find_transfer_pair
from finances.domain.models import AUTO, CONFIRMED
from finances.views.transfers import TransferLine, transfer_lines, transfer_of

CHECKING, SAVINGS, CARD = 1, 2, 3


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    """Test Checking (1), Test Savings (2), Test Card (3); pair 1 is 1 and 2, pair 2 is 3 and 4."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Checking", "Test Bank", "checking")
        create_account(opened, "Test Savings", "Test Bank", "savings")
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        for account, day, cents in (
            (CHECKING, 3, -2000),
            (SAVINGS, 4, 2000),
            (CHECKING, 9, -50000),
            (CARD, 10, 50000),
            (CARD, 11, -1250),
        ):
            opened.add(
                TransactionRow(
                    account_id=account,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description="PROBE",
                    source="statement",
                    fingerprint=f"v{day}".ljust(64, "0"),
                )
            )
        opened.flush()
        create_transfer_pair(opened, 1, 2, CONFIRMED)
        create_transfer_pair(opened, 3, 4, AUTO)
        yield opened


# find_transfer_pair


def test_a_pair_is_found_by_its_out_side(session: Session) -> None:
    found = find_transfer_pair(session, 3)
    assert found is not None
    assert (found.id, found.out_transaction_id, found.in_transaction_id) == (2, 3, 4)


def test_a_pair_is_found_by_its_in_side(session: Session) -> None:
    found = find_transfer_pair(session, 2)
    assert found is not None
    assert (found.id, found.out_transaction_id, found.in_transaction_id, found.status) == (
        1,
        1,
        2,
        CONFIRMED,
    )


def test_a_transaction_in_no_pair(session: Session) -> None:
    assert find_transfer_pair(session, 5) is None


# transfer_of


@pytest.mark.parametrize("transaction_id", [3, 4])
def test_both_sides_show_their_pairs_line(session: Session, transaction_id: int) -> None:
    line = transfer_of(session, transaction_id)
    assert line == TransferLine(
        "2", "2026-05-09", "Test Checking", "Test Card", "$500.00", "3", "4", "auto"
    )
    assert line == transfer_lines(session)[0]


def test_the_in_side_of_the_other_pair(session: Session) -> None:
    assert transfer_of(session, 2) == transfer_lines(session)[1]


@pytest.mark.parametrize("transaction_id", [5, 99])
def test_no_line_without_a_pair(session: Session, transaction_id: int) -> None:
    assert transfer_of(session, transaction_id) is None
