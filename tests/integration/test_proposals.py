from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.categorize.service import categorize
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    accept_proposal,
    create_account,
    create_rule,
    create_transfer_pair,
    decline_proposal,
    list_advice,
    list_category_assignments,
    list_changes,
    list_proposals,
    log_advice,
    propose_category,
    set_category_by_hand,
)
from finances.domain.models import CONFIRMED, MANUAL
from finances.domain.proposals import Advice, Proposal

NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """Coffee with no category (1), groceries set by a rule (2), books set by hand (3), and a
    card payment paired as a transfer (4 and 5)."""
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        create_account(opened, "Test Checking", "Test Bank", "checking")
        rows = [
            (1, date(2026, 5, 1), -500, "ACME COFFEE"),
            (1, date(2026, 5, 2), -2599, "FOOBAR GROCERY"),
            (1, date(2026, 5, 3), -1500, "BAZ BOOKS"),
            (2, date(2026, 5, 4), -5000, "PAYMENT TO CARD"),
            (1, date(2026, 5, 5), 5000, "PAYMENT THANK YOU"),
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
        create_rule(opened, "FOOBAR", "Groceries")
        categorize(opened)
        set_category_by_hand(opened, 3, "Education")
        create_transfer_pair(opened, 4, 5, CONFIRMED)
        yield opened


def test_a_proposal_changes_nothing(session: Session) -> None:
    found = propose_category(session, 1, "coffee & dessert", "  ACME is a   coffee shop ")
    assert found == Proposal(
        1, "category", 1, "Coffee & Dessert", "ACME is a coffee shop", "open", NOON, None
    )
    assert 1 not in list_category_assignments(session)
    assert list_proposals(session) == [found]


def test_a_rules_category_can_be_proposed_over(session: Session) -> None:
    assert (
        propose_category(session, 2, "Dining", "FOOBAR GROCERY has a deli counter").value
        == "Dining"
    )


@pytest.mark.parametrize(
    ("transaction_id", "category", "reason", "message"),
    [
        (1, "Dining", "", "a reason must be 1 to 200 characters"),
        (1, "Dining", "x" * 201, "a reason must be 1 to 200 characters"),
        (99, "Dining", "why", "transaction not found"),
        (1, "Nope", "why", "category not found"),
        (1, "Food", "why", "rules and transactions take a category, not a group"),
        (3, "Dining", "why", "a person has already decided this transaction"),
        (4, "Dining", "why", "a person has already decided this transaction"),
    ],
)
def test_refused_proposals(
    session: Session, transaction_id: int, category: str, reason: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        propose_category(session, transaction_id, category, reason)
    assert list_proposals(session) == []


def test_one_open_proposal_per_transaction(session: Session) -> None:
    propose_category(session, 1, "Dining", "first")
    with pytest.raises(ValueError, match="this transaction already has an open proposal"):
        propose_category(session, 1, "Coffee & Dessert", "second")


def test_accepting_is_the_persons_choice(session: Session) -> None:
    propose_category(session, 1, "Coffee & Dessert", "ACME is a coffee shop")
    found = accept_proposal(session, 1)
    assert (found.status, found.decided_at) == ("accepted", NOON)
    assignment = list_category_assignments(session)[1]
    assert (assignment.source, assignment.rule_id) == (MANUAL, None)
    assert [
        (c.who, c.action, c.kind, c.record_id, c.before, c.after) for c in list_changes(session)[:2]
    ] == [
        ("person", "proposal_accepted", "proposal", 1, None, "transaction 1: Coffee & Dessert"),
        ("person", "category_set", "transaction", 1, None, "Coffee & Dessert"),
    ]


def test_an_out_of_date_proposal_cannot_be_accepted(session: Session) -> None:
    propose_category(session, 1, "Coffee & Dessert", "ACME is a coffee shop")
    set_category_by_hand(session, 1, "Dining")
    with pytest.raises(
        ValueError, match="proposal 1 is out of date: the transaction was decided since"
    ):
        accept_proposal(session, 1)
    assert list_proposals(session)[0].status == "open"


def test_declining_and_not_again(session: Session) -> None:
    propose_category(session, 1, "Coffee & Dessert", "ACME is a coffee shop")
    found = decline_proposal(session, 1)
    assert (found.status, found.decided_at) == ("declined", NOON)
    assert 1 not in list_category_assignments(session)
    assert list_changes(session)[0].action == "proposal_declined"
    with pytest.raises(ValueError, match="a person declined this proposal already"):
        propose_category(session, 1, "coffee & dessert", "really")
    assert propose_category(session, 1, "Dining", "then a cafe").id == 2


@pytest.mark.parametrize(
    ("decide", "message"), [(accept_proposal, "accepted"), (decline_proposal, "accepted")]
)
def test_a_decided_proposal_is_not_decided_again(session: Session, decide, message: str) -> None:
    propose_category(session, 1, "Dining", "why")
    accept_proposal(session, 1)
    with pytest.raises(ValueError, match=f"proposal 1 is already {message}"):
        decide(session, 1)
    with pytest.raises(ValueError, match="proposal not found"):
        decide(session, 9)


def test_listing_by_status(session: Session) -> None:
    propose_category(session, 1, "Dining", "one")
    propose_category(session, 2, "Dining", "two")
    decline_proposal(session, 1)
    assert [item.id for item in list_proposals(session)] == [2, 1]
    assert [item.id for item in list_proposals(session, status="open")] == [2]
    assert [item.id for item in list_proposals(session, status="declined", limit=1)] == [1]
    with pytest.raises(ValueError, match="status must be one of: open, accepted, declined"):
        list_proposals(session, status="nope")


def test_the_advice_log(session: Session) -> None:
    first = log_advice(session, "  Suggested a coffee budget.  ", " budgets ")
    second = log_advice(session, "Groceries rose in May.")
    assert first == Advice(1, NOON, "budgets", "Suggested a coffee budget.")
    assert list_advice(session) == [second, first]
    assert list_advice(session, limit=1) == [second]
    for text, subject, message in (
        ("", "", "advice must be 1 to 1000 characters"),
        ("x" * 1001, "", "advice must be 1 to 1000 characters"),
        ("ok", "s" * 101, "a subject is at most 100 characters"),
    ):
        with pytest.raises(ValueError, match=message):
            log_advice(session, text, subject)
