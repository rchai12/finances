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
    create_rule,
    create_transfer_pair,
    decided_by_a_person,
    delete_rule,
    list_changes,
    proposal_out_of_date,
    propose_category,
    propose_rule_change,
    set_category_by_hand,
    set_split,
)
from finances.domain.models import CONFIRMED
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, run, table_rows

BEFORE = 'contains "ACME" -> Dining (priority 0)'
AFTER = 'contains "ACME" -> Coffee & Dessert (priority 5)'
NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Rule 1 puts ACME in Dining; transaction 2 is Groceries by hand; 3 has no category."""
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
    monkeypatch.setattr("finances.db.repositories.rule_changes._now", lambda: NOON)
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        create_account(session, "Test Checking", "Test Bank", "checking")
        for number, (account, cents, description) in enumerate(
            (
                (1, -500, "ACME COFFEE"),
                (1, -2599, "FOOBAR GROCERY"),
                (1, -1500, "BAZ BOOKS"),
                (1, -5000, "PAYMENT TO CARD"),
                (2, 5000, "PAYMENT THANK YOU"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=account,
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
        create_transfer_pair(session, 4, 5, CONFIRMED)
    engine.dispose()
    return tmp_settings


def decide(client: TestClient, decision: str, *ids: str):
    data = {"csrf": client.cookies["fin_csrf"], "decision": decision, "id": list(ids)}
    return client.post("/review", data=data, follow_redirects=False)


def test_a_choice_stays_open_until_a_person_changes_the_name(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        made = propose_category(session, 2, "Dining", "a deli")
        assert made.before == "Groceries"
        set_category_by_hand(session, 2, "Groceries")
        assert proposal_out_of_date(session, made) is False
    engine.dispose()
    run("transactions", "set-category", "--id", "2", "--clear")
    engine = get_engine()
    with session_scope(engine) as session:
        assert proposal_out_of_date(session, made) is False
        set_category_by_hand(session, 2, "Dining")
        assert proposal_out_of_date(session, made) is True
    engine.dispose()
    assert table_rows(run("review", "list").stdout)[1][8] == "out of date"


def test_a_proposal_with_before_none_goes_out_of_date_when_set_by_hand(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        made = propose_category(session, 3, "Dining", "a bookshop")
        assert made.before is None
        set_category_by_hand(session, 3, "Education")
        assert proposal_out_of_date(session, made) is True
    engine.dispose()


def test_decided_by_a_person_still_includes_a_choice(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        assert decided_by_a_person(session, 1) is False
        assert decided_by_a_person(session, 2) is True
        assert decided_by_a_person(session, 3) is False
        assert decided_by_a_person(session, 4) is True
        set_split(session, 3, [(-800, "Groceries"), (-700, "Dining")])
        assert decided_by_a_person(session, 3) is True
    engine.dispose()


def test_a_split_and_a_transfer_are_still_refused(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        set_split(session, 3, [(-800, "Groceries"), (-700, "Dining")])
        with pytest.raises(ValueError, match="a person has already decided this transaction"):
            propose_category(session, 3, "Dining", "why")
        with pytest.raises(ValueError, match="a person has already decided this transaction"):
            propose_category(session, 4, "Dining", "why")
    engine.dispose()


def test_a_duplicate_pattern_and_match_is_refused(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_rule(session, "FOOBAR", "Groceries")
        create_rule(session, "ACME", "Groceries", match="starts_with")
        with pytest.raises(ValueError, match="a rule with this pattern and match already exists"):
            propose_rule_change(session, 1, "why", pattern="FOOBAR")
        with pytest.raises(ValueError, match="a rule with this pattern and match already exists"):
            propose_rule_change(session, 1, "why", match="starts_with")
        with pytest.raises(ValueError, match="a rule pattern must be 1 to 100 characters"):
            propose_rule_change(session, 1, "why", pattern="x" * 101)
        with pytest.raises(ValueError, match="match must be one of: contains, starts_with, equals"):
            propose_rule_change(session, 1, "why", match="prefix")
    engine.dispose()


def test_a_delete_stores_the_rules_current_fields(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        made = propose_rule_change(session, 1, "too broad", delete=True)
        assert (made.value, made.pattern, made.match, made.priority) == (
            "Dining",
            "ACME",
            "contains",
            0,
        )
        assert made.before == BEFORE
    engine.dispose()


def test_history_records_the_edit_and_the_delete(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        edited = propose_rule_change(
            session, 1, "a coffee shop", category="Coffee & Dessert", priority=5
        )
        accept_proposal(session, edited.id)
        assert [
            (item.action, item.kind, item.record_id, item.before, item.after)
            for item in list_changes(session, limit=2)
        ] == [
            ("proposal_accepted", "proposal", 1, None, f"rule 1: {AFTER}"),
            ("rule_edited", "rule", 1, BEFORE, AFTER),
        ]
        deleted = propose_rule_change(session, 1, "too broad", delete=True)
        accept_proposal(session, deleted.id)
        assert [
            (item.action, item.kind, item.record_id, item.before, item.after)
            for item in list_changes(session, limit=2)
        ] == [
            ("proposal_accepted", "proposal", 2, None, "delete rule 1"),
            ("rule_deleted", "rule", 1, AFTER, None),
        ]
    engine.dispose()


def test_the_review_page_lists_and_accepts_a_rule_change(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_rule_change(session, 1, "a coffee shop", category="Coffee & Dessert", priority=5)
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
        BEFORE,
        f"rule 1: {AFTER}",
        "a coffee shop",
        "open",
    ] in rows
    response = decide(client, "accept", "1")
    assert response.status_code == 303
    assert table_rows(run("rules", "list").stdout)[1] == [
        "1",
        "5",
        "contains",
        "ACME",
        "Coffee & Dessert",
    ]


def test_a_deleted_rule_puts_the_proposal_out_of_date(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        made = propose_rule_change(session, 1, "a coffee shop", priority=5)
        delete_rule(session, 1)
        assert proposal_out_of_date(session, made) is True
        with pytest.raises(
            ValueError, match="proposal 1 is out of date: the rules or categories changed since"
        ):
            accept_proposal(session, made.id)
    engine.dispose()


def test_a_rule_change_is_stamped_in_utc(tmp_settings: Settings) -> None:
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
        create_rule(session, "ACME", "Dining")
        made = propose_rule_change(session, 1, "a coffee shop", priority=5)
    engine.dispose()
    assert made.created_at.tzinfo is UTC
