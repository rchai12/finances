from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    accept_proposal,
    create_account,
    create_category,
    create_group,
    create_rule,
    delete_category,
    delete_rule,
    edit_rule,
    get_category_by_name,
    list_changes,
    list_proposals,
    proposal_out_of_date,
    propose_category,
    propose_category_change,
    propose_new_category,
    propose_rule,
    propose_rule_change,
    set_category_by_hand,
    waits_for,
)
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, run, table_rows

NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
RENAME_TEXT = "category Dining: rename to Restaurants"


@pytest.fixture
def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Rule 1 puts ACME in Dining; transaction 2 is Groceries by hand."""
    for module in ("proposals", "category_changes", "new_categories", "rule_changes"):
        monkeypatch.setattr(
            f"finances.db.repositories.{module}._now",
            lambda: NOON,
        )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-500, "ACME COFFEE"), (-2599, "FOOBAR GROCERY")), start=1
        ):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, number),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        create_rule(session, "ACME", "Dining")
        categorize(session)
        set_category_by_hand(session, 2, "Groceries")
    engine.dispose()
    return tmp_settings


def decide(client: TestClient, decision: str, *ids: str):
    data = {"csrf": client.cookies["fin_csrf"], "decision": decision, "id": list(ids)}
    return client.post("/review", data=data, follow_redirects=False)


def test_a_refused_delete_then_a_rename_leave_only_the_accepted_history(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        with pytest.raises(ValueError, match="choose a category to move them to"):
            propose_category_change(session, "Dining", "why", delete=True)
        dining_id = get_category_by_name(session, "Dining").id
        made = propose_category_change(session, "Dining", "clearer", rename_to="Restaurants")
        accept_proposal(session, made.id)
        assert [
            (item.action, item.kind, item.record_id, item.before, item.after)
            for item in list_changes(session, limit=2)
        ] == [
            ("proposal_accepted", "proposal", 1, None, RENAME_TEXT),
            ("category_renamed", "category", dining_id, "Dining", "Restaurants"),
        ]
    engine.dispose()


def test_renaming_a_group_carries_an_open_new_category(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_group(session, "Spare")
        propose_new_category(session, 1, "Treats", "Spare", "sweets")
        made = propose_category_change(session, "Spare", "clearer", rename_to="Extra")
        accept_proposal(session, made.id)
        carried = list_proposals(session, status="open")[0]
        assert (carried.kind, carried.group, carried.value) == ("new_category", "Extra", "Treats")
        assert proposal_out_of_date(session, carried) is False
    engine.dispose()


def test_a_rule_change_stays_usable_after_a_rename(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_rule(session, "XYZ", "Groceries")
        create_rule(session, "OLD", "Education")
        propose_rule(session, 2, "FOOBAR", "Dining", "a grocery")
        usable = propose_rule_change(session, 1, "a coffee shop", priority=5)
        stale = propose_rule_change(session, 2, "unused", priority=5)
        gone = propose_rule_change(session, 3, "gone", delete=True)
        edit_rule(session, 2, priority=9)
        delete_rule(session, 3)
        made = propose_category_change(session, "Dining", "clearer", rename_to="Restaurants")
        accept_proposal(session, made.id)
        open_ones = {item.id: item for item in list_proposals(session, status="open")}
        assert proposal_out_of_date(session, open_ones[usable.id]) is False
        assert open_ones[usable.id].before == 'contains "ACME" -> Restaurants (priority 0)'
        assert open_ones[usable.id].value == "Restaurants"
        assert open_ones[stale.id].before == 'contains "XYZ" -> Groceries (priority 0)'
        assert proposal_out_of_date(session, open_ones[stale.id]) is True
        assert proposal_out_of_date(session, open_ones[gone.id]) is True
        assert open_ones[1].value == "Restaurants"
    engine.dispose()


def test_a_waiting_category_stays_waiting_after_a_delete(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_rule(session, "FOOBAR", "Groceries")
        parent = propose_new_category(session, 2, "Snacks", "Food", "chips")
        waiting = propose_category(session, 2, "Snacks", "a snack")
        edit = propose_rule_change(session, 2, "a deli", category="Dining")
        made = propose_category_change(
            session, "Dining", "a duplicate", delete=True, move_to="Coffee & Dessert"
        )
        accept_proposal(session, made.id)
        assert waits_for(session, waiting) == parent.id
        assert proposal_out_of_date(session, waiting) is False
        assert proposal_out_of_date(session, edit) is True
    engine.dispose()
    assert [row[8] for row in table_rows(run("review", "list").stdout)[1:] if row[0] == "3"] == [
        "out of date"
    ]
    assert [row[8] for row in table_rows(run("review", "list").stdout)[1:] if row[0] == "2"] == [
        "waits for #1"
    ]


def test_a_delete_whose_move_to_was_removed_is_out_of_date(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        made = propose_category_change(
            session, "Dining", "a duplicate", delete=True, move_to="Coffee & Dessert"
        )
        delete_category(session, "Coffee & Dessert")
        assert proposal_out_of_date(session, made) is True
        with pytest.raises(ValueError, match="the categories changed since"):
            accept_proposal(session, made.id)
    engine.dispose()


def test_a_rename_whose_new_name_was_taken_is_out_of_date(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        made = propose_category_change(session, "Dining", "clearer", rename_to="Restaurants")
        create_category(session, "Restaurants", "Food")
        assert proposal_out_of_date(session, made) is True
        with pytest.raises(ValueError, match="the categories changed since"):
            accept_proposal(session, made.id)
    engine.dispose()


def test_a_deleted_category_puts_the_change_out_of_date(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        made = propose_category_change(session, "Dining", "clearer", rename_to="Restaurants")
        delete_category(session, "Dining", "Coffee & Dessert")
        assert proposal_out_of_date(session, made) is True
    engine.dispose()


def test_the_review_page_lists_and_accepts_a_category_change(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_category_change(session, "Dining", "clearer", rename_to="Restaurants")
    engine.dispose()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    listed = client.get("/review")
    assert listed.status_code == 200
    rows = Page(listed.text).rows
    assert [
        "1",
        "",
        "",
        "",
        "",
        "Dining",
        "rename to Restaurants",
        "clearer",
        "open",
    ] in rows
    response = decide(client, "accept", "1")
    assert response.status_code == 303
    assert ["Food", "Restaurants", ""] in table_rows(run("categories", "list").stdout)


def test_a_category_change_is_stamped_in_utc(tmp_settings: Settings) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=date(2026, 5, 1),
                amount_cents=-500,
                description="ACME COFFEE",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
        session.flush()
        made = propose_category_change(session, "Dining", "clearer", rename_to="Restaurants")
    engine.dispose()
    assert made.created_at.tzinfo is UTC
