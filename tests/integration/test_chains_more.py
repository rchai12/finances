from datetime import UTC, date, datetime

import pytest

from finances.analysis.review import open_suggestions, review_items
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    accept_proposal,
    accepting_order,
    create_account,
    decline_proposal,
    decline_proposals,
    proposal_out_of_date,
    propose_category,
    propose_group,
    propose_new_category,
    set_category_by_hand,
    waits_for,
)
from finances.views.review import review_rows
from tests.support import failed_cleanly, run

NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    for module in ("proposals", "new_categories"):
        monkeypatch.setattr(
            f"finances.db.repositories.{module}._now",
            lambda: NOON,
        )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, description in ((1, "FOOBAR PET SUPPLY"), (2, "ACME COFFEE")):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, number),
                    amount_cents=-2599,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    return tmp_settings


def test_accepting_order_parents_first_then_ids_as_given(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_group(session, 1, "Pets", "pet costs")
        propose_new_category(session, 1, "Dog Food", "Pets", "a pet shop")
        propose_category(session, 1, "Dog Food", "dog food")
        for index in range(4, 9):
            propose_group(session, 1, f"Extra{index}", "padding")
        propose_group(session, 1, "Solo", "alone")
        assert accepting_order(session, [3, 9, 1, 2]) == [1, 2, 3, 9]
        assert accepting_order(session, [9, 2]) == [9, 2]
        assert accepting_order(session, [3, 9, 1, 2, 3]) == [1, 2, 3, 9]
    engine.dispose()


def test_a_parent_declined_alone_makes_the_child_out_of_date(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_group(session, 1, "Pets", "pet costs")
        parent = propose_new_category(session, 1, "Dog Food", "Pets", "a pet shop")
        child = propose_category(session, 1, "Dog Food", "dog food")
        decline_proposal(session, parent.id)
        assert waits_for(session, child) is None
        assert proposal_out_of_date(session, child) is True
    engine.dispose()


def test_a_waiting_proposal_whose_transaction_was_decided_is_out_of_date(
    card: Settings,
) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_group(session, 1, "Pets", "pet costs")
        propose_new_category(session, 1, "Dog Food", "Pets", "a pet shop")
        child = propose_category(session, 1, "Dog Food", "dog food")
        set_category_by_hand(session, 1, "Dining")
        assert proposal_out_of_date(session, child) is True
        states = [
            row.state for row in review_rows(review_items(session)) if row.id == str(child.id)
        ]
        assert states == ["out of date"]
    engine.dispose()


def test_open_suggestions_leave_out_a_waiting_proposal(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_group(session, 1, "Pets", "pet costs")
        propose_new_category(session, 1, "Dog Food", "Pets", "a pet shop")
        propose_category(session, 1, "Dog Food", "dog food")
        propose_category(session, 2, "Dining", "a cafe")
        assert open_suggestions(session) == {2: "Dining"}
    engine.dispose()


def test_decline_proposals_refuses_an_already_declined_id(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_group(session, 1, "Pets", "pet costs")
        propose_group(session, 1, "Solo", "alone")
        decline_proposal(session, 2)
        with pytest.raises(ValueError, match="proposal 2 is already declined"):
            decline_proposals(session, [2])
    engine.dispose()
    assert failed_cleanly(
        run("review", "decline", "--id", "1", "--id", "2"),
        "proposal 2 is already declined",
    )
    listed = run("review", "list").stdout
    assert "Pets" in listed


def test_declining_a_child_first_still_cascades_the_rest(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_group(session, 1, "Pets", "pet costs")
        propose_new_category(session, 1, "Dog Food", "Pets", "a pet shop")
        propose_category(session, 1, "Dog Food", "dog food")
        found = decline_proposals(session, [3, 2])
        assert [(item.id, waited) for item, waited in found] == [(3, False), (2, False)]
    engine.dispose()
    assert "Pets" in run("review", "list").stdout
    assert "Dog Food" not in run("review", "list").stdout


def test_propose_category_needs_an_open_new_category_or_a_real_one(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        made = propose_new_category(session, 1, "Yard", "Home", "yard work")
        decline_proposal(session, made.id)
        with pytest.raises(ValueError, match="category not found"):
            propose_category(session, 1, "Yard", "yard work")
        again = propose_new_category(session, 1, "Patio", "Home", "patio")
        accept_proposal(session, again.id)
    engine.dispose()
    run("categories", "delete", "--name", "Patio")
    engine = get_engine()
    with session_scope(engine) as session:
        with pytest.raises(ValueError, match="category not found"):
            propose_category(session, 1, "Patio", "patio")
    engine.dispose()
