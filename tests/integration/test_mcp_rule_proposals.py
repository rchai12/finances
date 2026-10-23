from datetime import UTC, date, datetime

import anyio
import pytest
from mcp.client import Client

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from finances.mcp_server.server import build_server
from tests.support import run, table_rows

PROPOSED = {
    "example_id": 1,
    "pattern": "acme   coffee",
    "category": "dining",
    "reason": "a cafe",
    "match": "equals",
    "priority": 5,
}


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Two card purchases: 1 cleans to ACME COFFEE, 2 to FOOBAR GROCERY. No rules."""
    monkeypatch.setattr(
        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-700, "SQ *ACME COFFEE 12345"), (-3000, "FOOBAR GROCERY")), start=1
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
    engine.dispose()
    return tmp_settings


def test_the_agent_proposes_a_rule(card: Settings) -> None:
    made = call("propose_rule", PROPOSED)
    assert made.structured_content == {
        "proposal": {
            "id": 1,
            "kind": "rule",
            "transaction_id": 1,
            "in_id": None,
            "category": "Dining",
            "rule": {"match": "equals", "pattern": "ACME COFFEE", "priority": 5},
            "alias": None,
            "reason": "a cafe",
            "status": "open",
            "created_at": "2026-05-25T12:00:00+00:00",
            "decided_at": None,
            "out_of_date": False,
        }
    }


def test_a_refused_rule(card: Settings) -> None:
    refused = call("propose_rule", {**PROPOSED, "pattern": "TEA"})
    assert [item.text for item in refused.content] == [
        "Error executing tool propose_rule: the rule does not match the example transaction"
    ]


def test_a_person_accepts_it_in_the_terminal(card: Settings) -> None:
    call("propose_rule", PROPOSED)
    rows = table_rows(run("review", "list").stdout)
    assert rows[1] == [
        "1",
        "2026-05-01",
        "Test Card",
        "SQ *ACME COFFEE 12345",
        "-$7.00",
        "",
        'a rule: equals "ACME COFFEE" -> Dining (priority 5)',
        "a cafe",
        "open",
    ]
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        'Accepted proposal 1: a rule, equals "ACME COFFEE" -> Dining (priority 5).\n'
        "Categorized 2 transactions: 1 changed, 1 without a category.\n",
    )
