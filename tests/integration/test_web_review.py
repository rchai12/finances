from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    list_category_assignments,
    list_proposals,
    log_advice,
    propose_category,
    set_category_by_hand,
)
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts

HEADINGS = ["ID", "Date", "Account", "Description", "Amount", "Now", "Proposed", "Reason", "State"]
NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("finances.db.repositories.proposals._now", lambda: NOON)
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    return found


@pytest.fixture
def review(client: TestClient) -> TestClient:
    """Three proposals (one per transaction); the third's transaction was then set by hand, so
    it is out of date. One note."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, description in ((1, "ACME COFFEE"), (2, "BAZ CAFE"), (3, "FOOBAR GROCERY")):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, number),
                    amount_cents=-500,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        propose_category(session, 1, "Coffee & Dessert", "ACME is a coffee shop")
        propose_category(session, 2, "Dining", "BAZ CAFE serves lunch")
        propose_category(session, 3, "Groceries", "FOOBAR is a grocer")
        set_category_by_hand(session, 3, "Dining")
        log_advice(session, "Suggested a coffee budget.", "budgets")
    engine.dispose()
    client.get("/review")
    return client


def decide(client: TestClient, decision: str, *ids: str):
    data = {"csrf": client.cookies["fin_csrf"], "decision": decision, "id": list(ids)}
    return client.post("/review", data=data, follow_redirects=False)


def state() -> dict[int, str]:
    engine = get_engine()
    with session_scope(engine) as session:
        found = {item.id: item.status for item in list_proposals(session)}
    engine.dispose()
    return found


def test_the_review_page(review: TestClient) -> None:
    response = review.get("/review")
    assert response.status_code == 200
    assert 'href="/review" aria-current="page">Review</a>' in response.text
    found = Page(response.text)
    assert found.rows == [
        HEADINGS,
        [
            "3",
            "2026-05-03",
            "Test Card",
            "FOOBAR GROCERY",
            "-$5.00",
            "Dining",
            "Groceries",
            "FOOBAR is a grocer",
            "out of date",
        ],
        [
            "2",
            "2026-05-02",
            "Test Card",
            "BAZ CAFE",
            "-$5.00",
            "",
            "Dining",
            "BAZ CAFE serves lunch",
            "open",
        ],
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
        ["When (UTC)", "Subject", "Note", "State", ""],
        ["2026-05-25 12:00", "budgets", "Suggested a coffee budget.", "", "Dismiss"],
    ]
    form = found.find("/review")
    assert form["method"] == "post"
    assert form["inputs"]["id"][0] == "checkbox"


def test_accepting_several(review: TestClient) -> None:
    response = decide(review, "accept", "1", "2")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/review?notice=proposals-accepted",
    )
    assert ("notice", "Proposals accepted, as your choice.") in page(
        review, response.headers["location"]
    ).paragraphs
    assert state() == {3: "open", 2: "accepted", 1: "accepted"}
    engine = get_engine()
    with session_scope(engine) as session:
        assert {key: value.source for key, value in list_category_assignments(session).items()} == {
            1: "manual",
            2: "manual",
            3: "manual",
        }
    engine.dispose()


def test_declining_an_out_of_date_one(review: TestClient) -> None:
    response = decide(review, "decline", "3")
    assert response.headers["location"] == "/review?notice=proposals-declined"
    assert ("notice", "Proposals declined. The agent will not propose them again.") in page(
        review, response.headers["location"]
    ).paragraphs
    assert state()[3] == "declined"


def test_all_or_none(review: TestClient) -> None:
    response = decide(review, "accept", "1", "3")
    assert response.status_code == 400
    assert ("error", "proposal 3 is out of date: the transaction was decided since") in Page(
        response.text
    ).paragraphs
    assert state() == {3: "open", 2: "open", 1: "open"}


@pytest.mark.parametrize(
    ("decision", "ids"),
    [("accept", ()), ("approve", ("1",)), ("accept", ("one",)), ("accept", ("١",))],
)
def test_nothing_chosen_or_a_bad_form(review: TestClient, decision: str, ids: tuple) -> None:
    response = decide(review, decision, *ids)
    assert response.status_code == 400
    assert ("error", "choose at least one proposal") in Page(response.text).paragraphs
    assert set(state().values()) == {"open"}


def test_the_form_token_is_checked(review: TestClient) -> None:
    response = review.post(
        "/review", data={"decision": "accept", "id": "1"}, follow_redirects=False
    )
    assert (response.status_code, response.text) == (403, "Bad form token")


def test_the_suggestions_beside_uncategorized_transactions(review: TestClient) -> None:
    found = page(review, "/categories")
    assert found.rows[:3] == [
        ["ID", "Date", "Account", "Merchant", "Amount", "Suggested"],
        ["2", "2026-05-02", "Test Card", "BAZ CAFE", "-$5.00", "Dining"],
        ["1", "2026-05-01", "Test Card", "ACME COFFEE", "-$5.00", "Coffee & Dessert"],
    ]
    assert found.links.count("/review") == 3


def test_nothing_yet(client: TestClient) -> None:
    upgrade_to_head()
    assert texts(page(client, "/review"), "empty") == ["No open proposals.", "No notes yet."]


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get("/review")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs
