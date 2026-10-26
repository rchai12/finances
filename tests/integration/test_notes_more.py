from datetime import UTC, date, datetime

import anyio
import pytest
from fastapi.testclient import TestClient
from mcp.client import Client

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    dismiss_advice,
    list_advice,
    list_changes,
    list_open_advice,
    log_advice,
    propose_category,
)
from finances.mcp_server.server import build_server
from finances.web.app import create_app
from tests.support import WEB_PORT, plain_lines, run, table_rows

KEPT = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
GONE = datetime(2026, 5, 25, 13, 0, tzinfo=UTC)
PROPOSALS = ["ID", "Date", "Account", "Description", "Amount", "Now", "Proposed", "Reason", "State"]
NOTES = ["ID", "When (UTC)", "Subject", "Note", "State"]


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def home(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: KEPT)
    monkeypatch.setattr("finances.db.repositories.advice._now", lambda: GONE)
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        log_advice(session, "First.")
        log_advice(session, "Second.")
        log_advice(session, "Third.")
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
        propose_category(session, 1, "Coffee & Dessert", "ACME is a coffee shop")
    engine.dispose()
    return tmp_settings


def test_open_notes_skip_dismissed_ones_and_honour_limit(home: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        dismiss_advice(session, 2)
        assert [item.id for item in list_open_advice(session)] == [3, 1]
        assert [item.id for item in list_open_advice(session, limit=1)] == [3]
    engine.dispose()


def test_dismiss_advice_stamps_now_and_a_refusal_changes_nothing(home: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        found = dismiss_advice(session, 1)
        assert found.dismissed_at == GONE
        with pytest.raises(ValueError, match="note 1 is already dismissed"):
            dismiss_advice(session, 1)
        with pytest.raises(ValueError, match="note not found"):
            dismiss_advice(session, 9)
        assert list_advice(session)[-1].dismissed_at == GONE
    engine.dispose()


def test_list_advice_shows_when_a_note_was_dismissed(home: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        dismiss_advice(session, 1)
    engine.dispose()
    found = call("list_advice").structured_content["advice"]
    by_id = {item["id"]: item["dismissed_at"] for item in found}
    assert by_id[1] == "2026-05-25T13:00:00+00:00"
    assert by_id[2] is None
    assert by_id[3] is None


def test_the_list_shows_proposals_then_notes(home: Settings) -> None:
    listed = run("review", "list")
    assert listed.exit_code == 0
    assert plain_lines(listed.stdout) == ["Notes:"]
    assert table_rows(listed.stdout) == [
        PROPOSALS,
        [
            "1",
            "2026-05-01",
            "Test Card",
            "ACME COFFEE",
            "-$5.00",
            "",
            "Coffee & Dessert",
            "ACME is a coffee shop",
            "open",
        ],
        NOTES,
        ["3", "2026-05-25 12:00", "", "Third.", ""],
        ["2", "2026-05-25 12:00", "", "Second.", ""],
        ["1", "2026-05-25 12:00", "", "First.", ""],
    ]


def test_dismissing_a_note_is_not_in_history(home: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        before = list_changes(session)
        dismiss_advice(session, 1)
        assert list_changes(session) == before
    engine.dispose()


def test_a_refused_month_shows_no_notes_block(home: Settings) -> None:
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    response = client.get("/insights?month=May")
    assert response.status_code == 400
    assert "From the agent" not in response.text


def test_a_form_without_the_token_is_refused(home: Settings) -> None:
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/review")
    response = client.post("/notes/dismiss", data={"id": "1"}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")
