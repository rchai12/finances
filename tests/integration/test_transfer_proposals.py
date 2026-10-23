from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.review import open_suggestions
from finances.categorize.transfers import pair_transfers
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    accept_proposal,
    create_account,
    create_transfer_pair,
    decline_proposal,
    find_transfer_pair,
    list_changes,
    list_transfer_rejections,
    propose_not_transfer,
    propose_transfer,
    reject_transfer,
)
from finances.domain.models import CONFIRMED
from finances.domain.proposals import Proposal

NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """A move to savings with two possible inflows (1 out; 2 and 3 in), waiting for review; a
    card payment the rules pair (4 and 5); a coffee (6) and money in of another amount (7)."""
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Checking", "Test Bank", "checking")
        create_account(opened, "Test Savings", "Test Bank", "savings")
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        rows = [
            (1, date(2026, 5, 5), -2000, "TRANSFER TO SAVINGS"),
            (2, date(2026, 5, 5), 2000, "TRANSFER FROM CHECKING"),
            (2, date(2026, 5, 6), 2000, "TRANSFER FROM CHECKING"),
            (1, date(2026, 5, 10), -5000, "PAYMENT TO CARD"),
            (3, date(2026, 5, 11), 5000, "PAYMENT THANK YOU"),
            (1, date(2026, 5, 12), -700, "ACME COFFEE"),
            (2, date(2026, 5, 12), 900, "INTEREST PAID"),
        ]
        for number, (account, day, cents, description) in enumerate(rows, start=1):
            opened.add(
                TransactionRow(
                    account_id=account,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        opened.flush()
        pair_transfers(opened)
        yield opened


def test_a_transfer_proposal_changes_nothing(session: Session) -> None:
    found = propose_transfer(session, 1, 2, "  same day,   same amount ")
    assert found == Proposal(1, "transfer", 1, "", "same day, same amount", "open", NOON, None, 2)
    assert find_transfer_pair(session, 1) is None


@pytest.mark.parametrize(
    ("out_id", "in_id", "reason", "message"),
    [
        (1, 2, "", "a reason must be 1 to 200 characters"),
        (1, 99, "why", "transaction not found"),
        (1, 6, "why", "a transfer goes from one account to another"),
        (6, 7, "why", "a transfer pairs money out with the same amount in"),
        (4, 5, "why", "a person or the rules already paired one of these transactions"),
    ],
)
def test_refused_pair_proposals(
    session: Session, out_id: int, in_id: int, reason: str, message: str
) -> None:
    for propose in (propose_transfer, propose_not_transfer):
        with pytest.raises(ValueError, match=message):
            propose(session, out_id, in_id, reason)


def test_a_pair_said_not_to_be_a_transfer(session: Session) -> None:
    reject_transfer(session, 1, 3)
    with pytest.raises(ValueError, match="a person said these two are not a transfer"):
        propose_transfer(session, 1, 3, "why")


def test_one_open_proposal_per_pair(session: Session) -> None:
    propose_transfer(session, 1, 2, "why")
    with pytest.raises(ValueError, match="these two already have an open proposal"):
        propose_not_transfer(session, 1, 2, "why not")


def test_declined_then_only_the_other_kind(session: Session) -> None:
    propose_transfer(session, 1, 2, "why")
    decline_proposal(session, 1)
    with pytest.raises(ValueError, match="a person declined this proposal already"):
        propose_transfer(session, 1, 2, "really")
    assert propose_not_transfer(session, 1, 2, "then not").kind == "not_transfer"


def test_accepting_a_transfer(session: Session) -> None:
    propose_transfer(session, 1, 2, "same day")
    found = accept_proposal(session, 1)
    assert found.status == "accepted"
    pair = find_transfer_pair(session, 1)
    assert (pair.out_transaction_id, pair.in_transaction_id, pair.status) == (1, 2, "confirmed")
    assert [(c.who, c.action, c.kind, c.before, c.after) for c in list_changes(session)[:2]] == [
        ("person", "proposal_accepted", "proposal", None, "1 -> 2: a transfer"),
        ("person", "transfer_confirmed", "transfer", None, "1 -> 2"),
    ]


def test_accepting_not_a_transfer(session: Session) -> None:
    propose_not_transfer(session, 1, 3, "the next day is interest")
    accept_proposal(session, 1)
    assert (1, 3) in list_transfer_rejections(session)
    assert find_transfer_pair(session, 1) is None
    assert [c.action for c in list_changes(session)[:2]] == [
        "proposal_accepted",
        "transfer_rejected",
    ]


@pytest.mark.parametrize("decided", ["paired", "rejected"])
def test_an_out_of_date_pair_proposal(session: Session, decided: str) -> None:
    propose_transfer(session, 1, 2, "same day")
    if decided == "paired":
        create_transfer_pair(session, 1, 3, CONFIRMED)
    else:
        reject_transfer(session, 1, 2)
    with pytest.raises(
        ValueError, match="proposal 1 is out of date: the transactions were decided since"
    ):
        accept_proposal(session, 1)


def test_suggestions_are_categories_only(session: Session) -> None:
    propose_transfer(session, 1, 2, "same day")
    assert open_suggestions(session) == {}
