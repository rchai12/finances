from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import AuditRow
from finances.db.repositories import record_change
from finances.domain.audit import KINDS, Change
from finances.views.audit import change_link
from finances.web.app import create_app
from tests.support import WEB_PORT, page

AT = datetime(2026, 5, 25, 14, 3, tzinfo=UTC)


def change(kind: str, before: str | None = None, after: str | None = None) -> Change:
    return Change(1, AT, "person", "x", kind, 4, before, after)


@pytest.mark.parametrize(
    ("kind", "before", "after", "link"),
    [
        ("proposal", None, "transaction 7: Dining", "/review"),
        ("alias", None, "ACME CAFE -> ACME COFFEE", "/categories"),
        ("settlement", None, "Sam paid Alex", "/shared"),
        ("finding", None, "spike for Dining in 2026-05", "/insights?month=2026-05"),
        ("finding", "interest in 2026-06", None, "/insights?month=2026-06"),
        ("finding", None, "interest in every month", "/insights"),
        ("finding", "interest in every month", None, "/insights"),
    ],
)
def test_the_kinds_that_had_no_link(
    kind: str, before: str | None, after: str | None, link: str
) -> None:
    assert change_link(change(kind, before, after)) == link


def test_every_kind_has_a_link() -> None:
    assert [kind for kind in KINDS if change_link(change(kind, None, "x in 2026-05")) is None] == []


def test_a_kind_with_no_link_gives_none() -> None:
    assert change_link(change("nope")) is None


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    upgrade_to_head()
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


def test_the_page_shows_a_proposal_and_a_finding(client: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        record_change(session, action="proposal_accepted", kind="proposal", record_id=3, after="x")
        record_change(
            session,
            action="finding_handled",
            kind="finding",
            record_id=1,
            after="spike for Dining in 2026-05",
        )
    engine.dispose()
    response = client.get("/history")
    assert response.status_code == 200
    found = page(client, "/history")
    assert "/review" in found.links
    assert "/insights?month=2026-05" in found.links


def test_a_kind_with_no_link_shows_as_plain_text(client: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        session.add(AuditRow(at=AT, who="person", action="x", kind="nope", record_id=9))
    engine.dispose()
    response = client.get("/history")
    assert response.status_code == 200
    assert "<td>nope 9</td>" in response.text
