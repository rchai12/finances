from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_person,
    record_settlement,
    set_account_owner,
    share_transaction,
)
from finances.domain.shared import SIZE
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts


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


def test_the_shared_page(home: TestClient) -> None:
    response = home.get("/shared")
    assert response.status_code == 200
    assert 'href="/shared" aria-current="page">Shared</a>' in response.text
    found = Page(response.text)
    assert texts(found, "owed") == ["Alex owes Sam $6.00."]
    assert found.rows == [
        ["ID", "Paid by", "Owes", "Owed"],
        ["1", "Sam", "Alex", "$10.00"],
        ["ID", "Date", "From", "To", "Amount", ""],
        ["1", "2026-05-20", "Alex", "Sam", "$4.00", "Delete"],
    ]
    form = found.find("/shared/settle")
    assert form["selects"]["payer"] == [("Alex", False), ("Sam", False)]
    assert form["inputs"]["day"] == ("date", "2026-06-01")
    assert 'href="/shared">Shared</a>' in home.get("/people").text


def test_settling_on_the_page(home: TestClient) -> None:
    response = post(
        home, "/shared/settle", payer="Alex", payee="Sam", amount="2.00", day="2026-05-25"
    )
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/shared?notice=settled",
    )
    found = page(home, "/shared?notice=settled")
    assert texts(found, "notice") == ["Settlement recorded."]
    assert texts(found, "owed") == ["Alex owes Sam $4.00."]


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"payee": "Sam", "amount": "x", "day": ""}, "invalid money text"),
        ({"payee": "Alex", "amount": "1.00", "day": ""}, "a person cannot pay themselves"),
        (
            {"payee": "Sam", "amount": "1.00", "day": "2026-13-01"},
            "date must be a date as YYYY-MM-DD",
        ),
    ],
)
def test_a_refused_settlement(home: TestClient, fields: dict, message: str) -> None:
    response = post(home, "/shared/settle", payer="Alex", **fields)
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == [message]
    assert found.find("/shared/settle")["inputs"]["amount"] == ("text", fields["amount"])


def test_deleting_a_settlement(home: TestClient) -> None:
    response = post(home, "/shared/settlements/delete", settlement="1")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/shared?notice=settlement-deleted",
    )
    found = page(home, "/shared?notice=settlement-deleted")
    assert texts(found, "notice") == ["Settlement deleted."]
    assert texts(found, "owed") == ["Alex owes Sam $10.00."]
    refused = post(home, "/shared/settlements/delete", settlement="9")
    assert refused.status_code == 400
    assert texts(Page(refused.text), "error") == ["settlement not found"]


def test_a_shared_transactions_page(home: TestClient) -> None:
    found = page(home, "/transactions/1")
    assert texts(found, "share") == ["Transaction 1: Alex owes Sam $10.00."]
    assert sorted(found.find("/transactions/1/share/clear")["inputs"]) == ["csrf"]
    assert found.all("/transactions/1/share") == []


def test_sharing_and_unsharing_on_a_transactions_page(home: TestClient) -> None:
    form = page(home, "/transactions/2").find("/transactions/2/share")
    assert form["selects"]["payer"] == [("", True), ("Alex", False), ("Sam", False)]
    shared = post(home, "/transactions/2/share", debtor="Alex", payer="", share="2.00")
    assert (shared.status_code, shared.headers["location"]) == (
        303,
        "/transactions/2?notice=share-saved",
    )
    found = page(home, "/transactions/2?notice=share-saved")
    assert texts(found, "notice") == ["Share saved."]
    assert texts(found, "share") == ["Transaction 2: Sam owes Alex $2.00."]
    removed = post(home, "/transactions/1/share/clear")
    assert (removed.status_code, removed.headers["location"]) == (
        303,
        "/transactions/1?notice=share-removed",
    )
    assert texts(page(home, "/transactions/1?notice=share-removed"), "notice") == ["Share removed."]
    assert texts(page(home, "/shared"), "owed") == ["Sam owes Alex $6.00."]


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"debtor": "Sam", "payer": "", "share": ""}, "a person cannot owe themselves"),
        ({"debtor": "Alex", "payer": "", "share": "30"}, SIZE),
    ],
)
def test_a_refused_share(home: TestClient, fields: dict, message: str) -> None:
    response = post(home, "/transactions/2/share", **fields)
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == [message]
    assert found.find("/transactions/2/share")["inputs"]["share"] == ("text", fields["share"])
