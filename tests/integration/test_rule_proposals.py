from collections.abc import Iterator
from datetime import UTC, date, datetime

import anyio
import pytest
from fastapi.testclient import TestClient
from mcp.client import Client
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.categorize.service import Accepted, CategorizeResult, accept_proposals
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_rule,
    decline_proposal,
    list_categories,
    list_category_assignments,
    list_changes,
    list_proposals,
    list_rules,
    propose_category,
    propose_rule,
    rename_category,
    set_category_by_hand,
)
from finances.domain.proposals import Proposal
from finances.mcp_server.server import build_server
from finances.web.app import create_app
from tests.support import WEB_PORT, run, table_rows

NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
ROWS = (
    (date(2026, 5, 1), -700, "SQ *ACME COFFEE 12345"),
    (date(2026, 5, 2), -700, "ACME COFFEE #12"),
    (date(2026, 5, 3), -700, "ACME COFFEE ROASTERS"),
    (date(2026, 5, 4), -3000, "FOOBAR GROCERY"),
)
STORED = Proposal(
    1, "rule", 1, "Dining", "a cafe", "open", NOON, None, None, "ACME COFFEE", "equals", 5
)


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def add_card(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    for number, (day, cents, description) in enumerate(ROWS, start=1):
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=day,
                amount_cents=cents,
                description=description,
                source="statement",
                fingerprint=f"r{number:02d}".ljust(64, "0"),
            )
        )
    session.flush()


def assigned(session: Session) -> dict[int, str]:
    names = {item.id: item.name for item in list_categories(session)}
    return {txn: names[row.category_id] for txn, row in list_category_assignments(session).items()}


@pytest.fixture
def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
    with session_scope(db_engine) as opened:
        add_card(opened)
        yield opened


@pytest.fixture
def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as opened:
        add_card(opened)
    engine.dispose()
    return tmp_settings


def test_a_stored_rule_proposal_changes_nothing(session: Session) -> None:
    found = propose_rule(
        session, 1, " acme   coffee ", "dining", "a cafe", match="equals", priority=5
    )
    assert found == STORED
    assert list_rules(session) == []
    assert list_category_assignments(session) == {}


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"reason": "", "pattern": ""}, "a reason must be 1 to 200 characters"),
        ({"pattern": ""}, "a rule pattern must be 1 to 100 characters"),
        ({"match": "prefix"}, "match must be one of: contains, starts_with, equals"),
        ({"example_id": 99}, "transaction not found"),
        ({"category": "Food"}, "rules and transactions take a category, not a group"),
        ({"pattern": "TEA"}, "the rule does not match the example transaction"),
    ],
)
def test_refused_rule_proposals(session: Session, kwargs: dict, message: str) -> None:
    arguments = {
        "example_id": 1,
        "pattern": "ACME COFFEE",
        "category": "Dining",
        "reason": "a cafe",
        "match": "equals",
        "priority": 5,
        **kwargs,
    }
    with pytest.raises(ValueError, match=message):
        propose_rule(
            session,
            arguments["example_id"],
            arguments["pattern"],
            arguments["category"],
            arguments["reason"],
            match=arguments["match"],
            priority=arguments["priority"],
        )
    assert list_proposals(session) == []


def test_equals_matches_the_cleaned_merchant(session: Session) -> None:
    found = propose_rule(session, 1, "ACME COFFEE", "Dining", "a cafe", match="equals")
    assert found.pattern == "ACME COFFEE"
    assert found.target_id == 1


def test_the_same_match_and_pattern_cannot_be_proposed_again(session: Session) -> None:
    create_rule(session, "acme coffee", "Dining", "equals")
    with pytest.raises(ValueError, match="a rule with this pattern and match already exists"):
        propose_rule(session, 1, "ACME COFFEE", "Dining", "a cafe", match="equals")
    found = propose_rule(session, 1, "ACME COFFEE", "Dining", "a cafe", match="contains")
    assert (found.match, found.pattern) == ("contains", "ACME COFFEE")


def test_declined_then_another_category_is_stored(session: Session) -> None:
    propose_rule(session, 1, "ACME COFFEE", "Dining", "why", match="contains")
    decline_proposal(session, 1)
    with pytest.raises(ValueError, match="a person declined this proposal already"):
        propose_rule(session, 1, "ACME COFFEE", "Dining", "again", match="contains", priority=9)
    found = propose_rule(
        session, 1, "ACME COFFEE", "Coffee & Dessert", "then that", match="contains"
    )
    assert found.value == "Coffee & Dessert"


def test_one_open_proposal_per_match_and_pattern(session: Session) -> None:
    propose_rule(session, 1, "ACME COFFEE", "Dining", "why", match="contains")
    with pytest.raises(ValueError, match="this rule already has an open proposal"):
        propose_rule(session, 3, "acme coffee", "Coffee & Dessert", "why not", match="contains")


def test_accepting_a_rule_runs_the_rules_once(session: Session) -> None:
    propose_rule(session, 1, "ACME COFFEE", "Dining", "a cafe", match="equals", priority=5)
    found = accept_proposals(session, [1])
    assert found == Accepted(
        [
            Proposal(
                1,
                "rule",
                1,
                "Dining",
                "a cafe",
                "accepted",
                NOON,
                NOON,
                None,
                "ACME COFFEE",
                "equals",
                5,
            )
        ],
        CategorizeResult(4, 2, 2),
    )
    assert assigned(session) == {1: "Dining", 2: "Dining"}
    assert [(c.who, c.action) for c in list_changes(session)[:2]] == [
        ("person", "proposal_accepted"),
        ("person", "rule_added"),
    ]


def test_a_rule_then_a_category_runs_once_at_the_end(session: Session) -> None:
    propose_rule(session, 1, "ACME COFFEE", "Dining", "a cafe", match="contains")
    propose_category(session, 4, "Groceries", "a grocer")
    found = accept_proposals(session, [1, 2])
    assert found.categorized == CategorizeResult(4, 3, 0)
    assert assigned(session) == {1: "Dining", 2: "Dining", 3: "Dining", 4: "Groceries"}


def test_only_a_category_does_not_run_the_rules(session: Session) -> None:
    propose_category(session, 4, "Groceries", "a grocer")
    found = accept_proposals(session, [1])
    assert found.categorized is None
    assert assigned(session) == {4: "Groceries"}


@pytest.mark.parametrize(
    ("change", "stale"),
    [
        ("rename", True),
        ("same_rule", True),
        ("starts_with", False),
    ],
)
def test_a_rule_proposal_out_of_date(session: Session, change: str, stale: bool) -> None:
    propose_rule(session, 1, "ACME COFFEE", "Dining", "a cafe", match="equals")
    if change == "rename":
        rename_category(session, "Dining", "Eating Out")
    elif change == "same_rule":
        create_rule(session, "ACME COFFEE", "Dining", "equals")
    else:
        create_rule(session, "ACME COFFEE", "Dining", "starts_with")
    if stale:
        with pytest.raises(
            ValueError, match="proposal 1 is out of date: the rules or categories changed since"
        ):
            accept_proposals(session, [1])
    else:
        found = accept_proposals(session, [1])
        assert found.proposals[0].status == "accepted"


def test_accepting_a_rule_on_the_review_page(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_rule(session, 1, "ACME COFFEE", "Dining", "a cafe", match="equals")
    engine.dispose()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/review")
    response = client.post(
        "/review",
        data={"csrf": client.cookies["fin_csrf"], "decision": "accept", "id": ["1"]},
        follow_redirects=False,
    )
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/review?notice=proposals-accepted",
    )
    engine = get_engine()
    with session_scope(engine) as session:
        assert assigned(session) == {1: "Dining", 2: "Dining"}
    engine.dispose()


def test_an_out_of_date_choice_on_the_review_page_adds_no_rule(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_rule(session, 1, "ACME COFFEE", "Dining", "a cafe", match="equals")
        propose_category(session, 4, "Groceries", "a grocer")
        set_category_by_hand(session, 4, "Dining")
    engine.dispose()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/review")
    response = client.post(
        "/review",
        data={"csrf": client.cookies["fin_csrf"], "decision": "accept", "id": ["1", "2"]},
        follow_redirects=False,
    )
    assert response.status_code == 400
    engine = get_engine()
    with session_scope(engine) as session:
        assert list_rules(session) == []
        assert list_proposals(session)[0].status == "open"
    engine.dispose()


def test_list_proposals_shows_rule_beside_a_category(card: Settings) -> None:
    call(
        "propose_rule",
        {
            "example_id": 1,
            "pattern": "ACME COFFEE",
            "category": "Dining",
            "reason": "a cafe",
            "match": "equals",
            "priority": 5,
        },
    )
    call("propose_category", {"transaction_id": 4, "category": "Groceries", "reason": "a grocer"})
    listed = call("list_proposals").structured_content["proposals"]
    by_kind = {item["kind"]: item["rule"] for item in listed}
    assert by_kind == {
        "category": None,
        "rule": {"match": "equals", "pattern": "ACME COFFEE", "priority": 5},
    }


def test_an_out_of_date_rule_shows_in_the_terminal(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_rule(session, 1, "ACME COFFEE", "Dining", "a cafe", match="equals")
        rename_category(session, "Dining", "Eating Out")
    engine.dispose()
    rows = table_rows(run("review", "list").stdout)
    assert rows[1][-1] == "out of date"
