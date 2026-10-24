from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_tags,
    create_account,
    create_person,
    record_settlement,
    set_account_owner,
    set_note,
    share_transaction,
)
from finances.domain.shared import SIZE
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, post, texts

JOINT = "say who paid: this transaction is joint or has no owner"
PATHS = (
    "/shared/settle",
    "/shared/settlements/delete",
    "/transactions/1/share",
    "/transactions/1/share/clear",
)


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: date(2026, 6, 1))
    return found


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Sam and Alex; a card owned by Sam with a purchase of -$20.01 (1), shared with Alex, and
    a refund of $6.00 (2); Alex paid Sam $4.00 on 2026-05-20."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        sam = create_person(session, "Sam")
        create_person(session, "Alex")
        account = create_account(session, "Test Card", "Test Bank", "credit_card")
        set_account_owner(session, account.id, sam.id)
        for number, (day, cents) in enumerate(((1, -2001), (3, 600)), start=1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description="FOOBAR GROCERY",
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        share_transaction(session, 1, "Alex")
        record_settlement(session, "Alex", "Sam", 400, date(2026, 5, 20))
    engine.dispose()
    client.get("/shared")
    return client


@pytest.fixture
def household(client: TestClient) -> TestClient:
    """Sam and Alex; a joint checking purchase of -$20.00 (1)."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_person(session, "Sam")
        create_person(session, "Alex")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        set_account_owner(session, checking.id, None)
        session.add(
            TransactionRow(
                account_id=checking.id,
                posted_date=date(2026, 5, 1),
                amount_cents=-2000,
                description="FOOBAR MARKET",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
    engine.dispose()
    client.get("/shared")
    return client


@pytest.mark.parametrize("path", PATHS)
def test_get_on_the_new_paths_is_405(home: TestClient, path: str) -> None:
    assert home.get(path).status_code == 405


def test_shared_needs_a_migrated_database(client: TestClient) -> None:
    response = client.get("/shared")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_a_blank_date_uses_today_from_the_app(
    home: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("finances.web.app._today", lambda: date(2026, 7, 4))
    response = post(home, "/shared/settle", payer="Alex", payee="Sam", amount="1.00", day="")
    assert response.status_code == 303
    found = page(home, "/shared")
    assert ["2", "2026-07-04", "Alex", "Sam", "$1.00", "Delete"] in found.rows


def test_a_refused_share_keeps_tags_note_and_the_form(home: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        add_tags(session, [2], "trip")
        set_note(session, 2, "split with a friend")
    engine.dispose()
    response = post(home, "/transactions/2/share", debtor="Alex", payer="", share="30")
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == [SIZE]
    assert texts(found, "tags") == ["trip"]
    assert texts(found, "note") == ["split with a friend"]
    assert found.find("/transactions/2/share")["inputs"]["share"] == ("text", "30")


def test_stopping_a_share_that_is_not_there(home: TestClient) -> None:
    response = post(home, "/transactions/2/share/clear")
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["the transaction is not shared"]


def test_paid_by_shares_a_joint_purchase(household: TestClient) -> None:
    refused = post(household, "/transactions/1/share", debtor="Alex", payer="", share="")
    assert refused.status_code == 400
    assert texts(Page(refused.text), "error") == [JOINT]
    stored = post(household, "/transactions/1/share", debtor="Alex", payer="Sam", share="")
    assert (stored.status_code, stored.headers["location"]) == (
        303,
        "/transactions/1?notice=share-saved",
    )
    assert texts(page(household, "/transactions/1"), "share") == [
        "Transaction 1: Alex owes Sam $10.00."
    ]


def test_a_blank_share_owes_half(home: TestClient) -> None:
    response = post(home, "/transactions/2/share", debtor="Alex", payer="", share="")
    assert response.status_code == 303
    found = page(home, "/transactions/2")
    assert texts(found, "share") == ["Transaction 2: Sam owes Alex $3.00."]


@pytest.mark.parametrize("path", ("/transactions/99/share", "/transactions/99/share/clear"))
def test_a_share_on_a_missing_transaction(home: TestClient, path: str) -> None:
    response = post(home, path, debtor="Alex", payer="", share="")
    assert response.status_code == 404
    assert ("error", "transaction not found") in Page(response.text).paragraphs


def test_an_empty_shared_page(client: TestClient) -> None:
    upgrade_to_head()
    found = page(client, "/shared")
    assert texts(found, "owed") == ["Nobody owes anybody."]
    assert texts(found, "empty") == [
        "No shared transactions. Share one from its page.",
        "No settlements.",
    ]


@pytest.mark.parametrize("path", PATHS)
def test_a_form_without_a_valid_token_is_refused(home: TestClient, path: str) -> None:
    response = home.post(path, data={}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")


def test_deleting_a_settlement_with_no_id(home: TestClient) -> None:
    response = post(home, "/shared/settlements/delete", settlement="x")
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["settlement not found"]
