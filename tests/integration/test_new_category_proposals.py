from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    accept_proposal,
    create_account,
    create_category,
    create_group,
    decline_proposal,
    delete_category,
    get_category_by_name,
    list_changes,
    proposal_out_of_date,
    propose_group,
    propose_new_category,
)
from finances.domain.proposals import group_kind_word, proposal_text
from finances.views.review import accepted_text, proposed_text
from finances.web.app import create_app
from tests.support import WEB_PORT, Page

KIND = "a group's kind must be spending, transfer, or income"
NAME = "a group name must be 1 to 50 characters"
OPEN = "this name already has an open proposal"
DECLINED = "a person declined this proposal already"
OUT_OF_DATE = "the categories changed since"
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
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=date(2026, 5, 1),
                amount_cents=-2599,
                description="FOOBAR PET SUPPLY",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
    engine.dispose()
    return tmp_settings


def decide(client: TestClient, decision: str, *ids: str):
    data = {"csrf": client.cookies["fin_csrf"], "decision": decision, "id": list(ids)}
    return client.post("/review", data=data, follow_redirects=False)


def test_kind_savings_is_refused_and_a_long_name_is_checked_first(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        with pytest.raises(ValueError, match=KIND):
            propose_group(session, 1, "Scratch", "why", kind="savings")
        with pytest.raises(ValueError, match="a reason must be 1 to 200 characters"):
            propose_group(session, 1, "Scratch", " ")
        with pytest.raises(ValueError, match=NAME):
            propose_group(session, 1, "x" * 51, "why", kind="savings")
        with pytest.raises(ValueError, match="a category name must be 1 to 50 characters"):
            propose_new_category(session, 1, "x" * 51, "Home", "why")
        with pytest.raises(ValueError, match="transaction not found"):
            propose_new_category(session, 9, "Scratch", "Home", "why")
        with pytest.raises(ValueError, match="group not found"):
            propose_new_category(session, 1, "Scratch", "Nosuch", "why")
    engine.dispose()


def test_a_stored_transfer_group_and_a_category_group_spelling(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        group = propose_group(session, 1, "Moves", "moved money", kind="transfer")
        category = propose_new_category(session, 1, "Pet Supplies", "home", "a pet shop")
    engine.dispose()
    assert (group.transfer, group.income, group.group, group.tax) == (True, False, None, None)
    assert category.group == "Home"


def test_a_declined_group_does_not_block_a_category_of_the_same_name(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        made = propose_group(session, 1, "Pets", "pet costs")
        decline_proposal(session, made.id)
        found = propose_new_category(session, 1, "Pets", "Home", "a pet shop")
        assert found.kind == "new_category"
        open_group = propose_group(session, 1, "Scratch", "why")
        with pytest.raises(ValueError, match=OPEN):
            propose_new_category(session, 1, "Scratch", "Home", "why")
        decline_proposal(session, open_group.id)
        declined = propose_new_category(session, 1, "Yard", "Home", "yard work")
        decline_proposal(session, declined.id)
        with pytest.raises(ValueError, match=DECLINED):
            propose_new_category(session, 1, "Yard", "Home", "again")
        again = propose_new_category(session, 1, "Yard", "Food", "in food")
        assert again.group == "Food"
    engine.dispose()


def test_a_category_whose_group_was_deleted_is_out_of_date(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_group(session, "Scratch")
        made = propose_new_category(session, 1, "ScratchCat", "Scratch", "why")
        delete_category(session, "Scratch")
        assert proposal_out_of_date(session, made) is True
        with pytest.raises(ValueError, match=OUT_OF_DATE):
            accept_proposal(session, made.id)
        create_group(session, "Temp")
        later = propose_new_category(session, 1, "TempCat", "Temp", "why")
        delete_category(session, "Temp")
        create_category(session, "Temp", "Home")
        assert proposal_out_of_date(session, later) is True
    engine.dispose()


def test_accepting_records_category_added_then_tax_when_proposed(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        taxed = propose_new_category(session, 1, "Pet Supplies", "Home", "a pet shop", tax=True)
        accept_proposal(session, taxed.id)
        taxed_actions = [item.action for item in list_changes(session, limit=3)]
        assert taxed_actions == ["proposal_accepted", "category_tax_set", "category_added"]
        plain = propose_new_category(session, 1, "Yard", "Home", "yard work")
        accept_proposal(session, plain.id)
        plain_actions = [item.action for item in list_changes(session, limit=3)]
        assert plain_actions == ["proposal_accepted", "category_added", "proposal_accepted"]
        assert "category_tax_set" not in plain_actions
    engine.dispose()


def test_the_texts_for_a_group_and_a_category(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        moves = propose_group(session, 1, "Moves", "moved money", kind="transfer")
        gigs = propose_group(session, 1, "Side Gigs", "side work", kind="income", sensitive=True)
        supplies = propose_new_category(session, 1, "Pet Supplies", "Home", "a pet shop")
    engine.dispose()
    assert proposed_text(moves) == "a new group: Moves (transfer)"
    assert proposed_text(gigs) == "a new group: Side Gigs (income, sensitive)"
    assert proposed_text(supplies) == "a new category: Pet Supplies in Home"
    assert accepted_text(moves) == f"Accepted proposal {moves.id}: the group Moves."
    assert accepted_text(gigs) == f"Accepted proposal {gigs.id}: the group Side Gigs."
    assert (
        accepted_text(supplies)
        == f"Accepted proposal {supplies.id}: the category Pet Supplies in Home."
    )
    assert proposal_text(moves) == "group: Moves (transfer)"
    assert proposal_text(gigs) == "group: Side Gigs (income, sensitive)"
    assert proposal_text(supplies) == "category: Pet Supplies in Home"
    assert group_kind_word(transfer=True) == "transfer"


def test_the_review_page_lists_and_accepts_a_group(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_group(session, 1, "Pets", "pet costs")
    engine.dispose()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    listed = client.get("/review")
    assert listed.status_code == 200
    rows = Page(listed.text).rows
    assert any("a new group: Pets" in cell for row in rows for cell in row)
    response = decide(client, "accept", "1")
    assert response.status_code == 303
    engine = get_engine()
    with session_scope(engine) as session:
        found = get_category_by_name(session, "Pets")
    engine.dispose()
    assert found is not None
    assert found.group_id is None


def test_a_group_proposal_stamps_the_clock(tmp_settings: Settings) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=date(2026, 5, 1),
                amount_cents=-2599,
                description="FOOBAR PET SUPPLY",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
        session.flush()
        made = propose_group(session, 1, "Scratch", "why")
    engine.dispose()
    assert made.created_at.tzinfo is UTC
