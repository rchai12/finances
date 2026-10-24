from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import add_tags, create_account, set_note
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Card: 1 ACME COFFEE tagged tax and trip with a note, 2 FOOBAR GROCERY tagged trip,
    3 BAZ CAFE with neither."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-450, "ACME COFFEE"), (-2599, "FOOBAR GROCERY"), (-500, "BAZ CAFE")), start=1
        ):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, number),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        add_tags(session, [1, 2], "trip")
        add_tags(session, [1], "tax")
        set_note(session, 1, "split with a friend")
    engine.dispose()
    client.get("/transactions")
    return client


def test_a_transaction_with_tags_and_a_note(home: TestClient) -> None:
    found = page(home, "/transactions/1")
    assert texts(found, "tags") == ["tax, trip"]
    assert "/transactions?tag=trip" in found.links
    assert [form["inputs"]["tag"] for form in found.all("/transactions/1/tags/remove")] == [
        ("hidden", "tax"),
        ("hidden", "trip"),
    ]
    assert texts(found, "note") == ["split with a friend"]
    assert sorted(found.find("/transactions/1/tags/add")["inputs"]) == ["csrf", "tag"]


def test_a_transaction_with_neither(home: TestClient) -> None:
    found = page(home, "/transactions/3")
    assert (texts(found, "tags"), texts(found, "note")) == (["No tags."], [])


def test_adding_and_removing_a_tag(home: TestClient) -> None:
    added = post(home, "/transactions/3/tags/add", tag=" Work  Trip ")
    assert (added.status_code, added.headers["location"]) == (
        303,
        "/transactions/3?notice=tag-added",
    )
    found = page(home, "/transactions/3?notice=tag-added")
    assert (texts(found, "notice"), texts(found, "tags")) == (["Tag added."], ["work trip"])
    removed = post(home, "/transactions/1/tags/remove", tag="TRIP")
    assert (removed.status_code, removed.headers["location"]) == (
        303,
        "/transactions/1?notice=tag-removed",
    )
    found = page(home, "/transactions/1?notice=tag-removed")
    assert (texts(found, "notice"), texts(found, "tags")) == (["Tag removed."], ["tax"])


def test_saving_and_removing_the_note(home: TestClient) -> None:
    saved = post(home, "/transactions/3/note", text="  paid back  ")
    assert (saved.status_code, saved.headers["location"]) == (
        303,
        "/transactions/3?notice=note-saved",
    )
    found = page(home, "/transactions/3?notice=note-saved")
    assert (texts(found, "notice"), texts(found, "note")) == (["Note saved."], ["paid back"])
    removed = post(home, "/transactions/3/note", text="")
    assert (removed.status_code, removed.headers["location"]) == (
        303,
        "/transactions/3?notice=note-removed",
    )
    found = page(home, "/transactions/3?notice=note-removed")
    assert (texts(found, "notice"), texts(found, "note")) == (["Note removed."], [])


@pytest.mark.parametrize(
    ("path", "fields", "status", "message"),
    [
        ("/transactions/1/tags/add", {"tag": "   "}, 400, "a tag must be 1 to 30 characters"),
        ("/transactions/1/note", {"text": "x" * 501}, 400, "a note is at most 500 characters"),
        ("/transactions/99/tags/remove", {"tag": "trip"}, 404, "transaction not found"),
    ],
)
def test_a_refused_form(
    home: TestClient, path: str, fields: dict, status: int, message: str
) -> None:
    response = post(home, path, **fields)
    assert response.status_code == status
    assert texts(Page(response.text), "error") == [message]


def test_the_tag_filter(home: TestClient) -> None:
    found = page(home, "/transactions?tag=TRIP")
    assert [row[2] for row in found.rows[1:]] == ["FOOBAR GROCERY", "ACME COFFEE"]
    assert found.find("/transactions")["selects"]["tag"] == [
        ("", False),
        ("tax", False),
        ("trip", False),
    ]
    assert found.find("/transactions/bulk")["inputs"]["back"] == ("hidden", "tag=TRIP")
    chosen = page(home, "/transactions?tag=trip").find("/transactions")["selects"]["tag"]
    assert chosen == [("", False), ("tax", False), ("trip", True)]


def test_a_tag_filter_that_is_refused(home: TestClient) -> None:
    response = home.get("/transactions?tag=" + "x" * 31)
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["a tag must be 1 to 30 characters"]
