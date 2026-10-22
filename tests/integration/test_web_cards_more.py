import json
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import add_balance_snapshot, create_account
from finances.domain.models import DataSource
from finances.sync import transport
from finances.web.app import create_app
from tests.integration.test_web_cards import Layout
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page

TODAY = date(2026, 5, 25)
ALEX = "https://alex-user:alex-pass@bridge.simplefin.org/simplefin"


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return found


def test_an_unmapped_simplefin_account_is_a_map_card(
    client: TestClient, keychain, monkeypatch: pytest.MonkeyPatch
) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Probe Bank", "credit_card")
    engine.dispose()
    keychain.passwords[("finances-simplefin", "alex")] = ALEX
    noon = datetime(TODAY.year, TODAY.month, TODAY.day, 12, tzinfo=UTC)
    body = {
        "errlist": [],
        "connections": [{"conn_id": "C-1", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}],
        "accounts": [
            {
                "id": "ACT-1",
                "name": "Probe Card",
                "conn_id": "C-1",
                "currency": "USD",
                "balance": "-1.00",
                "balance-date": int(noon.timestamp()),
                "transactions": [],
            }
        ],
    }
    monkeypatch.setattr(transport, "urllib_transport", lambda *_: (200, json.dumps(body).encode()))
    response = client.get("/sync/accounts?link=alex")
    assert response.status_code == 200
    found = Layout(response.text)
    assert found.problems == []
    assert found.cards == 1
    assert response.text.count("<section") == 1
    assert 'class="map card"' in response.text


def test_the_error_page_has_no_card(client: TestClient) -> None:
    upgrade_to_head()
    response = client.get("/ahead?days=0")
    assert response.status_code == 400
    found = Layout(response.text)
    assert found.cards == 0
    assert found.problems == []


def test_the_not_migrated_page_has_no_card(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 503
    found = Layout(response.text)
    assert found.cards == 0
    assert found.problems == []
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_an_empty_page_still_puts_every_h2_in_a_card(client: TestClient) -> None:
    upgrade_to_head()
    response = client.get("/")
    assert response.status_code == 200
    found = Layout(response.text)
    assert found.problems == []
    assert found.cards >= 1


def test_ahead_detail_with_nothing_expected_is_a_card(client: TestClient) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        quiet = create_account(session, "Test Quiet", "Test Bank", "checking")
        add_balance_snapshot(session, quiet.id, date(2026, 5, 20), 500, DataSource.STATEMENT)
    engine.dispose()
    response = client.get("/ahead?account=Test+Quiet")
    assert response.status_code == 200
    found = Layout(response.text)
    assert found.problems == []
    assert found.cards == 1
    assert "Nothing expected." in response.text
