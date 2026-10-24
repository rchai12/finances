from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.search import TransactionQuery, search_transactions
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_tags,
    create_account,
    set_category_by_hand,
    set_note,
    set_split,
    tagged_with,
)
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts

PATHS = (
    "/transactions/1/tags/add",
    "/transactions/1/tags/remove",
    "/transactions/1/note",
)


def _row(session: Session, cents: int, description: str, number: int) -> None:
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


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        yield opened


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
            _row(session, cents, description, number)
        session.flush()
        add_tags(session, [1, 2], "trip")
        add_tags(session, [1], "tax")
        set_note(session, 1, "split with a friend")
    engine.dispose()
    client.get("/transactions")
    return client


@pytest.mark.parametrize("path", PATHS)
def test_get_on_the_new_paths_is_405(home: TestClient, path: str) -> None:
    assert home.get(path).status_code == 405


def test_a_refused_tag_keeps_tags_and_note_on_the_400_page(home: TestClient) -> None:
    response = post(home, "/transactions/1/tags/add", tag="   ")
    found = Page(response.text)
    assert response.status_code == 400
    assert texts(found, "error") == ["a tag must be 1 to 30 characters"]
    assert texts(found, "tags") == ["tax, trip"]
    assert texts(found, "note") == ["split with a friend"]


def test_tagged_with_normalizes_and_refuses_a_blank(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    _row(session, -450, "ACME COFFEE", 1)
    _row(session, -2599, "FOOBAR GROCERY", 2)
    session.flush()
    add_tags(session, [1, 2], "trip")
    assert tagged_with(session, "  TRIP ") == {1, 2}
    with pytest.raises(ValueError) as raised:
        tagged_with(session, "")
    assert str(raised.value) == "a tag must be 1 to 30 characters"


def test_search_by_tag_and_category_and_a_split_is_found_per_part(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    _row(session, -450, "ACME COFFEE", 1)
    _row(session, -2000, "FOOBAR GROCERY", 2)
    session.flush()
    set_category_by_hand(session, 1, "Dining")
    add_tags(session, [1, 2], "trip")
    set_split(session, 2, [(-1200, "Groceries"), (-800, "Home & Garden")])
    both = search_transactions(session, TransactionQuery(tag="trip", category="Dining"))
    assert [(item.transaction.id, item.flow.category) for item in both] == [(1, "Dining")]
    parts = search_transactions(session, TransactionQuery(tag="trip"))
    found = [(item.transaction.id, item.flow.amount_cents, item.flow.category) for item in parts]
    assert found == [
        (2, -1200, "Groceries"),
        (2, -800, "Home & Garden"),
        (1, -450, "Dining"),
    ]


def test_select_all_keeps_the_tag_filter(home: TestClient) -> None:
    found = page(home, "/transactions?tag=trip")
    assert "/transactions?tag=trip&select=all" in found.links


def test_a_form_without_a_valid_token_is_refused(home: TestClient) -> None:
    response = home.post("/transactions/1/tags/add", data={"tag": "work"}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")
