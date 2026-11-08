from datetime import UTC, date, datetime

import anyio
import pytest
from fastapi.testclient import TestClient
from mcp.client import Client

from finances.analysis.insights import insights_report
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import (
    decline_proposal,
    proposal_out_of_date,
    propose_finding_status,
    set_finding_status,
)
from finances.domain.findings import HANDLED, IGNORED, FindingStatus, status_for, status_of
from finances.domain.insights import Finding
from finances.mcp_server.server import build_server
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, add_findings_data, run, table_rows

MAY = date(2026, 5, 1)
JUNE = date(2026, 6, 1)
NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def decide(client: TestClient, decision: str, *ids: str):
    data = {"csrf": client.cookies["fin_csrf"], "decision": decision, "id": list(ids)}
    return client.post("/review", data=data, follow_redirects=False)


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    upgrade_to_head()
    add_findings_data()
    return tmp_settings


def of_type(session, month: date, finding_type: str) -> Finding:
    report = insights_report(session, month)
    return next(
        item
        for item in (*report.findings, *(c.finding for c in report.closed))
        if item.type == finding_type
    )


def test_status_for_matches_status_of_for_the_same_parts() -> None:
    statuses = [
        FindingStatus(1, "spike", "Dining", MAY, HANDLED, NOON),
    ]
    finding = Finding("spike", "medium", MAY, "Dining", 14000, "detail")
    assert status_for("spike", "Dining", MAY, statuses) == status_of(finding, statuses)
    assert status_for("spike", "Dining", JUNE, statuses) is None


def test_a_stored_proposal_keeps_target_zero_month_and_a_cut_subject(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        long = "X" * 150
        finding = Finding("interest", "high", MAY, long, 100, "detail")
        made = propose_finding_status(session, finding, IGNORED, "known")
        assert (made.target_id, made.finding_month, len(made.finding_subject or "")) == (
            0,
            MAY,
            100,
        )
    engine.dispose()


def test_a_declined_handled_for_may_allows_handled_for_june(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        may = of_type(session, MAY, "interest")
        june = of_type(session, JUNE, "interest")
        first = propose_finding_status(session, may, HANDLED, "may only")
        decline_proposal(session, first.id)
        second = propose_finding_status(session, june, HANDLED, "june too")
        assert second.id == 2
    engine.dispose()


def test_an_open_handled_for_may_allows_handled_for_june(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        may = of_type(session, MAY, "interest")
        june = of_type(session, JUNE, "interest")
        propose_finding_status(session, may, HANDLED, "may only")
        second = propose_finding_status(session, june, HANDLED, "june too")
        assert second.finding_month == JUNE
    engine.dispose()


def test_an_ignored_proposal_goes_out_of_date_when_ignored_from_june(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        may = of_type(session, MAY, "interest")
        june = of_type(session, JUNE, "interest")
        made = propose_finding_status(session, may, IGNORED, "known")
        set_finding_status(session, june, IGNORED)
        assert proposal_out_of_date(session, made) is True
    engine.dispose()


def test_the_review_page_lists_and_accepts_a_finding_proposal(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        propose_finding_status(session, of_type(session, MAY, "spike"), HANDLED, "a one-off")
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
        "spike for Dining in 2026-05",
        "mark handled",
        "a one-off",
        "open",
    ] in rows
    response = decide(client, "accept", "1")
    assert response.status_code == 303
    assert table_rows(run("insights", "--month", "2026-05").stdout)[-1][5] == "handled"


def test_propose_finding_status_with_no_month_uses_this_month(
    money: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 5, 25))
    proposal = call(
        "propose_finding_status",
        {"type": "interest", "status": "ignored", "reason": "known"},
    ).structured_content["proposal"]
    assert proposal["finding"] == {
        "type": "interest",
        "about": "",
        "month": "2026-05",
        "status": "ignored",
    }
