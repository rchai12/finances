from datetime import date

import anyio
import pytest
from fastapi.testclient import TestClient
from mcp.client import Client

from finances.analysis.insights import insights_report
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import (
    list_changes,
    list_finding_statuses,
    reopen_finding,
    set_finding_status,
)
from finances.domain.audit import PERSON
from finances.domain.findings import HANDLED, IGNORED
from finances.domain.insights import Finding
from finances.mcp_server.server import build_server
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, add_findings_data, page, post, texts

MAY = date(2026, 5, 1)
JUNE = date(2026, 6, 1)
FINDINGS = ["Severity", "Type", "About", "Saves a month", "Detail"]
TYPES = (
    "type must be one of: spike, frequent_small, subscription_overlap, price_increase, interest, "
    "fees, over_budget, duplicate, large_first_charge"
)


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    upgrade_to_head()
    add_findings_data()
    return tmp_settings


def of_type(session, month: date, finding_type: str) -> Finding:
    report = insights_report(session, month)
    return next(item for item in report.findings if item.type == finding_type)


def test_ignored_stores_no_month_and_handled_stores_the_month(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        ignored = set_finding_status(session, of_type(session, MAY, "interest"), IGNORED)
        handled = set_finding_status(session, of_type(session, MAY, "spike"), HANDLED)
        assert (ignored.month, handled.month) == (None, MAY)
        with pytest.raises(ValueError, match="status must be one of: handled, ignored"):
            set_finding_status(session, of_type(session, MAY, "price_increase"), "done")
    engine.dispose()


def test_reopening_june_leaves_a_may_handled_status(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        set_finding_status(session, of_type(session, MAY, "interest"), HANDLED)
        with pytest.raises(ValueError, match="this finding is open"):
            reopen_finding(session, "interest", "", JUNE)
        remaining = list_finding_statuses(session)
        assert [(item.status, item.month) for item in remaining] == [(HANDLED, MAY)]
    engine.dispose()


def test_list_finding_statuses_is_ordered_by_id(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        set_finding_status(session, of_type(session, MAY, "spike"), HANDLED)
        set_finding_status(session, of_type(session, MAY, "interest"), IGNORED)
        assert [item.id for item in list_finding_statuses(session)] == [1, 2]
    engine.dispose()


def test_a_subject_longer_than_100_is_cut(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        finding = Finding("spike", "medium", MAY, "x" * 101, 1, "detail")
        stored = set_finding_status(session, finding, HANDLED)
        assert stored.subject == "x" * 100
    engine.dispose()


def test_the_dashboard_leaves_out_a_handled_finding(
    money: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("finances.web.app._today", lambda: date(2026, 5, 25))
    engine = get_engine()
    with session_scope(engine) as session:
        set_finding_status(session, of_type(session, MAY, "interest"), HANDLED)
    engine.dispose()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    found = page(client, "/")
    start = found.rows.index(FINDINGS)
    assert found.rows[start + 1][1:] == [
        "spike",
        "Dining",
        "$140.00",
        "Dining: $200.00 this month, against $60.00 a month before.",
    ]
    assert "Findings: 4. Could save up to $171.99 a month." in texts(found, "summary")


def test_get_insights_lists_only_open_findings(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        set_finding_status(session, of_type(session, MAY, "spike"), HANDLED)
    engine.dispose()
    found = call("get_insights", {"month": "2026-05"}).structured_content
    assert len(found["findings"]) == 4
    assert {item["type"] for item in found["findings"]} == {
        "interest",
        "price_increase",
        "frequent_small",
        "subscription_overlap",
    }


def test_an_empty_month_on_the_form_uses_this_month(
    money: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("finances.web.app._today", lambda: date(2026, 5, 20))
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/insights")
    response = post(
        client, "/findings/status", type="spike", about="Dining", month="", status="handled"
    )
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/insights?month=2026-05&notice=finding-handled",
    )


def test_history_through_the_web_is_a_person(money: Settings) -> None:
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/insights")
    post(
        client, "/findings/status", type="spike", about="Dining", month="2026-05", status="handled"
    )
    engine = get_engine()
    with session_scope(engine) as session:
        found = list_changes(session, limit=1)[0]
    engine.dispose()
    assert (found.who, found.action) == (PERSON, "finding_handled")


def test_reopen_finding_refuses_an_unknown_type(money: Settings) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        with pytest.raises(ValueError, match=TYPES):
            reopen_finding(session, "nope", "", MAY)
    engine.dispose()


def test_a_forged_form_is_refused(money: Settings) -> None:
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/insights")
    for path in ("/findings/status", "/findings/reopen"):
        shown = client.post(path, data={"csrf": "nope"}, follow_redirects=False)
        assert shown.status_code == 403
        assert shown.text == "Bad form token"


def test_a_bad_month_on_the_form_is_refused(money: Settings) -> None:
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/insights")
    response = post(
        client, "/findings/status", type="spike", about="Dining", month="May", status="handled"
    )
    assert (response.status_code, texts(Page(response.text), "error")) == (
        400,
        ["month must be a year and month, like 2026-05"],
    )
