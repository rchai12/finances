from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.review import open_suggestions
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    log_advice,
    propose_category,
    set_category_by_hand,
)
from finances.web.app import create_app
from tests.support import WEB_PORT, page


def add_coffee(session: Session, number: int, description: str) -> None:
    session.add(
        TransactionRow(
            account_id=1,
            posted_date=date(2026, 5, number),
            amount_cents=-500,
            description=description,
            source="statement",
            fingerprint=f"p{number:02d}".ljust(64, "0"),
        )
    )
    session.flush()


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        add_coffee(opened, 1, "ACME PROBE COFFEE")
        yield opened


def test_open_suggestions_leave_out_a_set_by_hand_transaction(session: Session) -> None:
    propose_category(session, 1, "Dining", "ACME PROBE is a cafe")
    set_category_by_hand(session, 1, "Groceries")
    assert open_suggestions(session) == {}


def test_open_suggestions_leave_out_a_deleted_transaction(session: Session) -> None:
    propose_category(session, 1, "Dining", "ACME PROBE is a cafe")
    session.delete(session.get(TransactionRow, 1))
    session.flush()
    assert open_suggestions(session) == {}


def test_open_suggestions_keep_a_current_open_proposal(session: Session) -> None:
    propose_category(session, 1, "Dining", "ACME PROBE is a cafe")
    assert open_suggestions(session) == {1: "Dining"}


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    return found


@pytest.fixture
def proposed(client: TestClient) -> TestClient:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        add_coffee(session, 1, "ACME PROBE COFFEE")
        propose_category(session, 1, "Coffee & Dessert", "ACME PROBE is a cafe")
    engine.dispose()
    client.get("/review")
    return client


def decide(client: TestClient, decision: str, *ids: str):
    data = {"csrf": client.cookies["fin_csrf"], "decision": decision, "id": list(ids)}
    return client.post("/review", data=data, follow_redirects=False)


def test_a_declined_proposal_cannot_be_made_again(proposed: TestClient) -> None:
    assert decide(proposed, "decline", "1").status_code == 303
    engine = get_engine()
    with session_scope(engine) as session:
        with pytest.raises(ValueError, match="a person declined this proposal already"):
            propose_category(session, 1, "Coffee & Dessert", "again")
    engine.dispose()


def test_the_suggested_column_is_empty_after_a_decline(proposed: TestClient) -> None:
    decide(proposed, "decline", "1")
    found = page(proposed, "/categories")
    assert found.rows[:2] == [
        ["ID", "Date", "Account", "Merchant", "Amount", "Suggested"],
        ["1", "2026-05-01", "Test Card", "ACME PROBE COFFEE", "-$5.00", ""],
    ]


def test_the_notes_table_shows_at_most_twenty_newest_first(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    times = [datetime(2026, 5, 25, 12, minute, tzinfo=UTC) for minute in range(21)]
    stamps = iter(times)
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: next(stamps))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        for index in range(21):
            log_advice(session, f"Probe note {index}.", f"n{index:02d}")
    engine.dispose()
    rows = page(client, "/review").rows
    assert rows[0] == ["When (UTC)", "Subject", "Note", "State", ""]
    assert rows[1] == ["2026-05-25 12:20", "n20", "Probe note 20.", "", "Dismiss"]
    assert rows[20] == ["2026-05-25 12:01", "n01", "Probe note 1.", "", "Dismiss"]
    assert len(rows) == 21


def test_the_review_link_is_current_only_on_its_page(client: TestClient) -> None:
    upgrade_to_head()
    review = client.get("/review")
    history = client.get("/history")
    assert 'href="/review" aria-current="page">Review</a>' in review.text
    assert 'href="/review">Review</a>' in history.text
    assert 'aria-current="page">Review</a>' not in history.text
