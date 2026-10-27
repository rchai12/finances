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


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def moved(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """$20.00 out of checking (1) and into savings (2) the same day."""
    monkeypatch.setattr(
        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Checking", "Test Bank", "checking")
        create_account(session, "Test Savings", "Test Bank", "savings")
        for number, (account, cents, description) in enumerate(
            ((1, -2000, "TRANSFER TO SAVINGS"), (2, 2000, "TRANSFER FROM CHECKING")), start=1
        ):
            session.add(
                TransactionRow(
                    account_id=account,
                    posted_date=date(2026, 5, 5),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    return tmp_settings


def test_the_agent_proposes_a_transfer(moved: Settings) -> None:
    made = call("propose_transfer", {"out_id": 1, "in_id": 2, "reason": "same day, same amount"})
    assert made.structured_content == {
        "proposal": {
            "id": 1,
            "kind": "transfer",
            "transaction_id": 1,
            "in_id": 2,
            "category": None,
            "rule": None,
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "category_change": None,
            "reason": "same day, same amount",
            "status": "open",
            "created_at": "2026-05-25T12:00:00+00:00",
            "decided_at": None,
            "out_of_date": False,
        }
    }
    refused = call("propose_not_transfer", {"out_id": 1, "in_id": 2, "reason": "why not"})
    assert [item.text for item in refused.content] == [
        "Error executing tool propose_not_transfer: these two already have an open proposal"
    ]


def test_a_person_reviews_it_in_the_terminal(moved: Settings) -> None:
    call("propose_transfer", {"out_id": 1, "in_id": 2, "reason": "same day, same amount"})
    rows = table_rows(run("review", "list").stdout)
    assert rows[1] == [
        "1",
        "2026-05-05",
        "Test Checking",
        "TRANSFER TO SAVINGS",
        "-$20.00",
        "",
        "a transfer with transaction 2",
        "same day, same amount",
        "open",
    ]
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: transactions 1 and 2 are a transfer.\n",
    )
