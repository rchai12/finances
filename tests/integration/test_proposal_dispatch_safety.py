from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import (
    AuditRow,
    CategoryRow,
    ProposalRow,
    TransactionCategoryRow,
    TransactionRow,
    TransferPairRow,
    TransferRejectionRow,
)
from finances.db.repositories import (
    accept_proposal,
    create_account,
    decline_proposal,
    find_transfer_pair,
    list_category_assignments,
    list_changes,
    list_transfer_rejections,
    propose_category,
    propose_group,
    propose_new_category,
    propose_not_transfer,
    propose_transfer,
)
from finances.db.repositories import proposals as repo
from finances.domain.models import CONFIRMED, MANUAL
from finances.domain.proposals import ACCEPTED, OPEN


@pytest.fixture
def prepared(db_engine):
    with session_scope(db_engine) as session:
        a = create_account(session, "Synthetic Checking", "Synthetic Bank", "checking")
        b = create_account(session, "Synthetic Savings", "Synthetic Bank", "savings")
        for number, account, cents in ((1, a.id, -700), (2, b.id, 700)):
            session.add(
                TransactionRow(
                    account_id=account,
                    posted_date=date(2026, 1, 1),
                    amount_cents=cents,
                    description="ACME SYNTHETIC",
                    source="statement",
                    fingerprint=str(number).ljust(64, "0"),
                )
            )
    return db_engine


def snapshot(engine):
    with Session(engine) as session:
        return {
            cls.__tablename__: session.execute(
                select(*cls.__table__.columns).order_by(*cls.__table__.primary_key.columns)
            ).all()
            for cls in (
                TransactionCategoryRow,
                TransferPairRow,
                TransferRejectionRow,
                AuditRow,
                ProposalRow,
            )
        }


@pytest.mark.parametrize("operation", ["accept", "stale"])
def test_refusal_caught_inside_transaction_leaves_persisted_state(prepared, monkeypatch, operation):
    with session_scope(prepared) as session:
        original = propose_category(session, 1, "Dining", "Synthetic reason")
    before = snapshot(prepared)
    unknown = replace(original, kind="private_unknown")
    row = SimpleNamespace(**vars(unknown))
    with session_scope(prepared) as session:
        monkeypatch.setattr(repo, "_open_row", lambda s, n: row)
        with pytest.raises(ValueError, match="^unsupported proposal kind$"):
            if operation == "accept":
                accept_proposal(session, original.id)
            else:
                repo.proposal_out_of_date(session, unknown)
        assert row.status == OPEN and row.decided_at is None
        # Commit the successful surrounding transaction: rollback cannot hide a write.
    assert snapshot(prepared) == before


@pytest.mark.parametrize("kind", ["category", "transfer", "not_transfer"])
def test_supported_decisions_persist_with_audit(prepared, kind):
    with session_scope(prepared) as session:
        if kind == "category":
            item = propose_category(session, 1, "Dining", "Synthetic reason")
        elif kind == "transfer":
            item = propose_transfer(session, 1, 2, "Synthetic reason")
        else:
            item = propose_not_transfer(session, 1, 2, "Synthetic reason")
        result = accept_proposal(session, item.id)
        assert result.status == ACCEPTED and result.decided_at is not None
    with Session(prepared) as session:
        row = session.get(ProposalRow, item.id)
        assert row.status == ACCEPTED and row.decided_at is not None
        audits = [a for a in list_changes(session) if a.action == "proposal_accepted"]
        assert len(audits) == 1 and audits[0].record_id == item.id
        assignments = list_category_assignments(session)
        pair = find_transfer_pair(session, 1)
        rejected = list_transfer_rejections(session)
        if kind == "category":
            assert assignments[1].source == MANUAL
            assert session.get(CategoryRow, assignments[1].category_id).name == "Dining"
            assert pair is None and rejected == set()
        elif kind == "transfer":
            assert (pair.out_transaction_id, pair.in_transaction_id, pair.status) == (
                1,
                2,
                CONFIRMED,
            )
            assert not assignments and rejected == set()
        else:
            assert (1, 2) in rejected
            assert not assignments and pair is None


@pytest.mark.parametrize("state", ["missing", "accepted", "declined"])
def test_missing_and_decided_refuse_before_dispatch(prepared, monkeypatch, state):
    with session_scope(prepared) as session:
        item = propose_category(session, 1, "Dining", "Synthetic reason")
        if state == "accepted":
            accept_proposal(session, item.id)
        elif state == "declined":
            decline_proposal(session, item.id)
    before = snapshot(prepared)
    waiting = Mock(side_effect=AssertionError("dependency dispatch must not run"))
    monkeypatch.setattr(repo, "waits_for", waiting)
    with session_scope(prepared) as session:
        message = (
            "proposal not found" if state == "missing" else f"proposal {item.id} is already {state}"
        )
        with pytest.raises(ValueError) as stopped:
            accept_proposal(session, 999 if state == "missing" else item.id)
        assert str(stopped.value) == message
    waiting.assert_not_called()
    assert snapshot(prepared) == before


def test_open_dependency_refuses_before_staleness(prepared, monkeypatch):
    with session_scope(prepared) as session:
        parent = propose_group(session, 1, "Synthetic Group", "Synthetic reason")
        child = propose_new_category(session, 1, "Synthetic Leaf", parent.value, "Synthetic reason")
    before = snapshot(prepared)
    stale = Mock(side_effect=AssertionError("staleness must not run"))
    monkeypatch.setattr(repo, "proposal_out_of_date", stale)
    with session_scope(prepared) as session:
        with pytest.raises(ValueError) as stopped:
            accept_proposal(session, child.id)
        assert str(stopped.value) == f"proposal {child.id} waits for proposal {parent.id}"
    stale.assert_not_called()
    assert snapshot(prepared) == before
