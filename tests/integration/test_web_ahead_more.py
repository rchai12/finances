from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    set_account_active,
)
from finances.domain.models import DataSource
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, texts

TODAY = date(2026, 5, 25)


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return found


def add_tx(session, account_id: int, day: date, cents: int, description: str) -> None:
    session.add(
        TransactionRow(
            account_id=account_id,
            posted_date=day,
            amount_cents=cents,
            description=description,
            source="statement",
            fingerprint=f"{account_id}-{day}-{cents}-{description}".ljust(64, "0")[:64],
        )
    )


def test_leading_zero_days_is_seven(client: TestClient) -> None:
    upgrade_to_head()
    found = page(client, "/ahead?days=07")
    assert texts(found, "summary")[0] == "Forecast from 2026-05-25 to 2026-05-31."
    assert found.forms[0]["inputs"]["days"] == ("number", "7")


def test_days_are_checked_before_account(client: TestClient) -> None:
    upgrade_to_head()
    response = client.get("/ahead?days=0&account=Nope")
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["days must be a whole number from 1 to 90"]


def test_spaces_only_account_shows_every_account(client: TestClient) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        add_balance_snapshot(session, checking.id, date(2026, 5, 24), 1000, DataSource.STATEMENT)
    engine.dispose()
    found = page(client, "/ahead?account=%20%20")
    assert found.rows[0][0] == "Account"
    assert found.rows[1][0] == "Test Checking"


def test_one_account_with_nothing_expected(client: TestClient) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        quiet = create_account(session, "Test Quiet", "Test Bank", "checking")
        add_balance_snapshot(session, quiet.id, date(2026, 5, 20), 500, DataSource.STATEMENT)
    engine.dispose()
    found = page(client, "/ahead?account=Test+Quiet")
    assert texts(found, "empty") == ["Nothing expected."]
    assert texts(found, "summary")[-1] == "Lowest: $5.00 on 2026-05-25."


def test_an_inactive_account_is_found_through_its_link(client: TestClient) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        closed = create_account(session, "Old Card", "Test Bank", "credit_card")
        add_balance_snapshot(session, closed.id, date(2026, 5, 20), -1000, DataSource.STATEMENT)
        set_account_active(session, closed.id, False)
        open_one = create_account(session, "Test Checking", "Test Bank", "checking")
        add_balance_snapshot(session, open_one.id, date(2026, 5, 24), 5000, DataSource.STATEMENT)
    engine.dispose()
    names = [row[0] for row in page(client, "/ahead").rows[1:] if row]
    assert "Old Card" not in names
    assert "Test Checking" in names
    found = page(client, "/ahead?account=Old+Card")
    assert texts(found, "summary")[0] == ("Forecast for Old Card from 2026-05-25 to 2026-06-23.")


def test_the_dashboard_window_is_seven_days(client: TestClient) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        for day in (date(2026, 5, 10), date(2026, 5, 17), date(2026, 5, 24)):
            add_tx(session, card.id, day, -900, "QUUX WEEKLY A")
        for day in (date(2026, 5, 11), date(2026, 5, 18), date(2026, 5, 25)):
            add_tx(session, card.id, day, -800, "QUUX WEEKLY B")
    engine.dispose()
    found = page(client, "/")
    start = found.rows.index(["Date", "What", "Merchant", "Amount"])
    coming = []
    for row in found.rows[start + 1 :]:
        if len(row) != 4:
            break
        coming.append(row)
    merchants = [row[2] for row in coming]
    assert merchants == ["QUUX WEEKLY A"]


def test_an_unknown_query_field_is_ignored(client: TestClient) -> None:
    upgrade_to_head()
    response = client.get("/ahead?foo=bar")
    assert response.status_code == 200
    assert texts(page(client, "/ahead?foo=bar"), "summary")[0] == (
        "Forecast from 2026-05-25 to 2026-06-23."
    )
