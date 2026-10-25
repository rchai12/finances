from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    count_open_proposals,
    create_account,
    propose_group,
    propose_new_category,
)
from finances.web.app import create_app
from tests.support import WEB_PORT, page, post, texts

WAITING = (
    "Proposals declined, with the ones that waited for them. The agent will not propose them again."
)


@pytest.fixture
def home(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """1 a group Pets; 2 a category Dog Food in it, which waits for 1."""
    for module in ("proposals", "new_categories"):
        monkeypatch.setattr(
            f"finances.db.repositories.{module}._now",
            lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
        )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=date(2026, 5, 1),
                amount_cents=-2599,
                description="FOOBAR PET SUPPLY",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
        session.flush()
        propose_group(session, 1, "Pets", "pet costs")
        propose_new_category(session, 1, "Dog Food", "Pets", "a pet shop")
    engine.dispose()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/review")
    return client


def open_count() -> int:
    engine = get_engine()
    with session_scope(engine) as session:
        found = count_open_proposals(session)
    engine.dispose()
    return found


def test_the_review_page_shows_what_waits(home: TestClient) -> None:
    rows = page(home, "/review").rows
    assert [row[-1] for row in rows if row and row[0] in ("1", "2")] == ["waits for #1", "open"]


def test_declining_a_parent_says_what_else_was_declined(home: TestClient) -> None:
    response = post(home, "/review", decision="decline", id="1")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/review?notice=proposals-declined-waiting",
    )
    assert texts(page(home, response.headers["location"]), "notice") == [WAITING]
    assert open_count() == 0


def test_declining_with_nothing_waiting_keeps_the_old_notice(home: TestClient) -> None:
    response = post(home, "/review", decision="decline", id="2")
    assert response.headers["location"] == "/review?notice=proposals-declined"
    assert open_count() == 1
