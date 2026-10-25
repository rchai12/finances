from datetime import UTC, date, datetime

import anyio
import pytest
from mcp.client import Client

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule
from finances.mcp_server.server import build_server
from tests.support import run, table_rows

PROPOSED = {"example_id": 1, "target": "acme   coffee", "reason": "the same shop"}


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Two card purchases: 1 cleans to ACME CAFE, 2 to ACME COFFEE; a rule puts ACME COFFEE in
    Dining, so 2 is categorized and 1 is not."""
    monkeypatch.setattr(
        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-450, "SQ *ACME CAFE 12345"), (-500, "ACME COFFEE")), start=1
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
        create_rule(session, "ACME COFFEE", "Dining")
        categorize(session)
    engine.dispose()
    return tmp_settings


def test_the_agent_proposes_an_alias(card: Settings) -> None:
    made = call("propose_merchant_alias", PROPOSED)
    assert made.structured_content == {
        "proposal": {
            "id": 1,
            "kind": "alias",
            "transaction_id": 1,
            "in_id": None,
            "category": None,
            "rule": None,
            "alias": {"source": "ACME CAFE", "target": "ACME COFFEE"},
            "new": None,
            "reason": "the same shop",
            "status": "open",
            "created_at": "2026-05-25T12:00:00+00:00",
            "decided_at": None,
            "out_of_date": False,
        }
    }


def test_a_refused_alias(card: Settings) -> None:
    refused = call("propose_merchant_alias", {**PROPOSED, "target": "Acme Cafe"})
    assert [item.text for item in refused.content] == [
        "Error executing tool propose_merchant_alias: a merchant cannot be merged into itself"
    ]


def test_a_person_accepts_it_in_the_terminal(card: Settings) -> None:
    call("propose_merchant_alias", PROPOSED)
    rows = table_rows(run("review", "list").stdout)
    assert rows[1] == [
        "1",
        "2026-05-01",
        "Test Card",
        "SQ *ACME CAFE 12345",
        "-$4.50",
        "",
        "merge ACME CAFE into ACME COFFEE",
        "the same shop",
        "open",
    ]
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: ACME CAFE merged into ACME COFFEE.\n"
        "Categorized 2 transactions: 1 changed, 0 without a category.\n",
    )
    assert table_rows(run("aliases", "list").stdout) == [
        ["From", "To"],
        ["ACME CAFE", "ACME COFFEE"],
    ]
