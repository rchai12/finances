from collections.abc import Iterator
from datetime import UTC, date, datetime

import anyio
import pytest
from fastapi.testclient import TestClient
from mcp.client import Client
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.categorize.service import Accepted, CategorizeResult, accept_proposals, categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_alias,
    create_account,
    create_rule,
    decline_proposal,
    list_aliases,
    list_categories,
    list_category_assignments,
    list_changes,
    list_proposals,
    proposal_out_of_date,
    propose_merchant_alias,
)
from finances.domain.proposals import Proposal, proposal_text
from finances.mcp_server.server import build_server
from finances.web.app import create_app
from tests.support import WEB_PORT

NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
ROWS = (
    (date(2026, 5, 1), -450, "SQ *ACME CAFE 12345"),
    (date(2026, 5, 2), -500, "ACME COFFEE"),
    (date(2026, 5, 3), -450, "ACME CAFE #2"),
)
STORED = Proposal(
    1,
    "alias",
    1,
    "ACME COFFEE",
    "the same shop",
    "open",
    NOON,
    None,
    None,
    None,
    None,
    None,
    "ACME CAFE",
)
OUT_OF_DATE = "proposal 1 is out of date: the merchant aliases changed since"


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
                fingerprint=f"a{number:02d}".ljust(64, "0"),
            )
        )
    session.flush()
    create_rule(session, "ACME COFFEE", "Dining")
    categorize(session)


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


def test_a_stored_alias_proposal_changes_nothing(session: Session) -> None:
    found = propose_merchant_alias(session, 1, " acme   coffee ", "the same shop")
    assert found == STORED
    assert proposal_text(found) == "alias: ACME CAFE -> ACME COFFEE"
    assert list_aliases(session) == []
    assert assigned(session) == {2: "Dining"}


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"reason": "", "target": "SQ *ACME CAFE 12345"},
            "a reason must be 1 to 200 characters",
        ),
        ({"example_id": 99}, "transaction not found"),
    ],
)
def test_refused_alias_proposals(session: Session, kwargs: dict, message: str) -> None:
    arguments = {"example_id": 1, "target": "ACME COFFEE", "reason": "the same shop", **kwargs}
    with pytest.raises(ValueError, match=message):
        propose_merchant_alias(
            session, arguments["example_id"], arguments["target"], arguments["reason"]
        )


def test_a_persons_alias_is_read_when_proposing(session: Session) -> None:
    add_alias(session, "ACME CAFE", "BAZ CAFE")
    with pytest.raises(ValueError, match="this merchant is already merged into another"):
        propose_merchant_alias(session, 1, "ACME COFFEE", "the same shop")


def test_a_declined_alias_keys_on_source_and_target(session: Session) -> None:
    propose_merchant_alias(session, 1, "ACME COFFEE", "the same shop")
    decline_proposal(session, 1)
    with pytest.raises(ValueError, match="a person declined this proposal already"):
        propose_merchant_alias(session, 1, "ACME COFFEE", "again")
    found = propose_merchant_alias(session, 1, "BAZ CAFE", "a different shop")
    assert (found.source, found.value, found.status) == ("ACME CAFE", "BAZ CAFE", "open")


def test_an_open_alias_keys_on_the_source_only(session: Session) -> None:
    propose_merchant_alias(session, 1, "ACME COFFEE", "the same shop")
    with pytest.raises(ValueError, match="this merchant already has an open proposal"):
        propose_merchant_alias(session, 3, "BAZ CAFE", "another shop")


def test_an_alias_proposal_out_of_date_after_a_person_merges(session: Session) -> None:
    propose_merchant_alias(session, 1, "ACME COFFEE", "the same shop")
    add_alias(session, "ACME CAFE", "BAZ CAFE")
    found = list_proposals(session)[0]
    assert proposal_out_of_date(session, found) is True
    with pytest.raises(ValueError, match=OUT_OF_DATE):
        accept_proposals(session, [1])
    assert [(item.source, item.target) for item in list_aliases(session)] == [
        ("ACME CAFE", "BAZ CAFE")
    ]


def test_an_unrelated_alias_does_not_stale_the_proposal(session: Session) -> None:
    propose_merchant_alias(session, 1, "ACME COFFEE", "the same shop")
    add_alias(session, "QUX CAFE", "BAZ CAFE")
    found = list_proposals(session)[0]
    assert proposal_out_of_date(session, found) is False
    accepted = accept_proposals(session, [1])
    assert accepted.proposals[0].status == "accepted"


def test_accepting_an_alias_runs_the_rules_once(session: Session) -> None:
    propose_merchant_alias(session, 1, "ACME COFFEE", "the same shop")
    found = accept_proposals(session, [1])
    assert found == Accepted(
        [
            Proposal(
                1,
                "alias",
                1,
                "ACME COFFEE",
                "the same shop",
                "accepted",
                NOON,
                NOON,
                None,
                None,
                None,
                None,
                "ACME CAFE",
            )
        ],
        CategorizeResult(3, 2, 0),
    )
    assert assigned(session) == {1: "Dining", 2: "Dining", 3: "Dining"}
    assert [(c.who, c.action) for c in list_changes(session)[:2]] == [
        ("person", "proposal_accepted"),
        ("person", "alias_added"),
    ]


def test_accepting_an_alias_on_the_review_page(card: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_merchant_alias(session, 1, "ACME COFFEE", "the same shop")
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
        assert assigned(session)[1] == "Dining"
    engine.dispose()


def test_list_proposals_shows_alias_beside_a_category(card: Settings) -> None:
    call(
        "propose_merchant_alias",
        {"example_id": 1, "target": "ACME COFFEE", "reason": "the same shop"},
    )
    call("propose_category", {"transaction_id": 3, "category": "Groceries", "reason": "a grocer"})
    listed = call("list_proposals").structured_content["proposals"]
    by_kind = {item["kind"]: item["alias"] for item in listed}
    assert by_kind == {
        "alias": {"source": "ACME CAFE", "target": "ACME COFFEE"},
        "category": None,
    }
