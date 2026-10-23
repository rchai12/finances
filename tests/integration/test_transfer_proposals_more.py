from collections.abc import Iterator
from datetime import UTC, date, datetime

import anyio
import pytest
from fastapi.testclient import TestClient
from mcp.client import Client
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    accept_proposal,
    create_account,
    create_transfer_pair,
    decline_proposal,
    find_transfer_pair,
    list_proposals,
    list_transfer_rejections,
    propose_not_transfer,
    propose_transfer,
)
from finances.domain.models import CONFIRMED
from finances.mcp_server.server import build_server
from finances.web.app import create_app
from tests.support import WEB_PORT, failed_cleanly, page, run, table_rows

NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
PAIR = {
    "id": 1,
    "kind": "not_transfer",
    "transaction_id": 1,
    "in_id": 2,
    "category": None,
    "rule": None,
    "reason": "interest, not a transfer",
    "status": "open",
    "created_at": "2026-05-25T12:00:00+00:00",
    "decided_at": None,
    "out_of_date": False,
}


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def add_move(session: Session) -> None:
    create_account(session, "Test Checking", "Test Bank", "checking")
    create_account(session, "Test Savings", "Test Bank", "savings")
    create_account(session, "Test Card", "Test Bank", "credit_card")
    rows = [
        (1, date(2026, 5, 5), -2000, "TRANSFER TO SAVINGS"),
        (2, date(2026, 5, 5), 2000, "TRANSFER FROM CHECKING"),
        (2, date(2026, 5, 6), 2000, "TRANSFER FROM CHECKING"),
    ]
    for number, (account, day, cents, description) in enumerate(rows, start=1):
        session.add(
            TransactionRow(
                account_id=account,
                posted_date=day,
                amount_cents=cents,
                description=description,
                source="statement",
                fingerprint=f"p{number:02d}".ljust(64, "0"),
            )
        )
    session.flush()


@pytest.fixture
def moved(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        add_move(session)
    engine.dispose()
    return tmp_settings


@pytest.fixture
def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
    with session_scope(db_engine) as opened:
        add_move(opened)
        yield opened


def test_the_not_transfer_tool_and_in_id_on_the_list(moved: Settings) -> None:
    made = call(
        "propose_not_transfer",
        {"out_id": 1, "in_id": 2, "reason": "interest, not a transfer"},
    )
    assert made.structured_content == {"proposal": PAIR}
    call(
        "propose_category",
        {"transaction_id": 1, "category": "Coffee & Dessert", "reason": "a cafe"},
    )
    listed = call("list_proposals").structured_content["proposals"]
    by_kind = {item["kind"]: item["in_id"] for item in listed}
    assert by_kind == {"not_transfer": 2, "category": None}


def test_reviewing_not_a_transfer_in_the_terminal(moved: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_not_transfer(session, 1, 2, "interest, not a transfer")
    engine.dispose()
    rows = table_rows(run("review", "list").stdout)
    assert rows[1][6:] == ["not a transfer with transaction 2", "interest, not a transfer", "open"]
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: transactions 1 and 2 are not a transfer.\n",
    )


def test_a_deleted_transaction_makes_a_pair_out_of_date(moved: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_transfer(session, 1, 2, "same day")
        session.delete(session.get(TransactionRow, 2))
        session.flush()
    engine.dispose()
    rows = table_rows(run("review", "list").stdout)
    assert rows[1][-1] == "out of date"
    assert failed_cleanly(
        run("review", "accept", "--id", "1"),
        "proposal 1 is out of date: the transactions were decided since",
    )


def test_accepting_a_transfer_on_the_review_page(moved: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_transfer(session, 1, 2, "same day")
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
    shown = page(client, "/transactions/1")
    assert (
        "",
        "Pair 1 (confirmed): $20.00 from Test Checking (transaction 1)"
        " to Test Savings (transaction 2).",
    ) in shown.paragraphs


def test_declining_not_a_transfer_changes_nothing(session: Session) -> None:
    propose_not_transfer(session, 1, 2, "why not")
    decline_proposal(session, 1)
    assert find_transfer_pair(session, 1) is None
    assert list_transfer_rejections(session) == set()
    with pytest.raises(ValueError, match="a person declined this proposal already"):
        propose_not_transfer(session, 1, 2, "again")


def test_pairing_another_way_first_blocks_accept(session: Session) -> None:
    propose_transfer(session, 1, 2, "same day")
    create_transfer_pair(session, 1, 3, CONFIRMED)
    with pytest.raises(
        ValueError, match="proposal 1 is out of date: the transactions were decided since"
    ):
        accept_proposal(session, 1)
    pair = find_transfer_pair(session, 1)
    assert (pair.out_transaction_id, pair.in_transaction_id, pair.status) == (1, 3, "confirmed")
    assert list_proposals(session)[0].status == "open"
