from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import log_advice
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts

FROM_THE_AGENT = ["When (UTC)", "Subject", "Note", ""]
NOTES = ["When (UTC)", "Subject", "Note", "State", ""]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Note 1 (budgets) at 12:00 and note 2 (no subject) at 12:05."""
    stamps = iter([datetime(2026, 5, 25, 12, minute, tzinfo=UTC) for minute in (0, 5)])
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: next(stamps))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        log_advice(session, "Suggested a coffee budget.", "budgets")
        log_advice(session, "Watch ACME COFFEE.")
    engine.dispose()
    client.get("/review")
    return client


def table(found: Page, heading: list[str]) -> list[list[str]]:
    """The rows of the table whose heading row is this one, without the heading."""
    rows = found.rows
    if heading not in rows:
        return []
    start = rows.index(heading) + 1
    end = next((i for i in range(start, len(rows)) if rows[i] and rows[i][0] == "When (UTC)"), None)
    found_rows = rows[start:end]
    return [row for row in found_rows if len(row) == len(heading)]


def test_the_insights_page_shows_the_notes(home: TestClient) -> None:
    found = page(home, "/insights?month=2026-05")
    assert table(found, FROM_THE_AGENT) == [
        ["2026-05-25 12:05", "", "Watch ACME COFFEE.", "Dismiss"],
        ["2026-05-25 12:00", "budgets", "Suggested a coffee budget.", "Dismiss"],
    ]
    form = found.all("/notes/dismiss")[0]
    assert form["inputs"]["back"] == ("hidden", "insights")
    assert form["inputs"]["month"] == ("hidden", "2026-05")


def test_dismissing_on_insights_returns_to_the_month(home: TestClient) -> None:
    response = post(home, "/notes/dismiss", id="1", back="insights", month="2026-05")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/insights?month=2026-05&notice=note-dismissed",
    )
    found = page(home, response.headers["location"])
    assert texts(found, "notice") == ["Note dismissed."]
    assert table(found, FROM_THE_AGENT) == [
        ["2026-05-25 12:05", "", "Watch ACME COFFEE.", "Dismiss"],
    ]
    assert table(page(home, "/review"), NOTES) == [
        ["2026-05-25 12:05", "", "Watch ACME COFFEE.", "", "Dismiss"],
        ["2026-05-25 12:00", "budgets", "Suggested a coffee budget.", "dismissed", ""],
    ]


def test_dismissing_on_review_returns_to_review(home: TestClient) -> None:
    response = post(home, "/notes/dismiss", id="2", back="review")
    assert response.headers["location"] == "/review?notice=note-dismissed"


def test_a_month_that_is_not_one_is_left_out(home: TestClient) -> None:
    response = post(home, "/notes/dismiss", id="2", back="insights", month="May")
    assert response.headers["location"] == "/insights?notice=note-dismissed"


@pytest.mark.parametrize("note", ["9", "x", ""])
def test_a_note_that_is_not_there(home: TestClient, note: str) -> None:
    response = post(home, "/notes/dismiss", id=note, back="review")
    assert (response.status_code, texts(Page(response.text), "error")) == (
        400,
        ["note not found"],
    )


def test_no_block_without_notes(client: TestClient) -> None:
    upgrade_to_head()
    assert "From the agent" not in client.get("/insights?month=2026-05").text
