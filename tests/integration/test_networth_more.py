from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.analysis.networth import net_worth_over_time
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import add_balance_snapshot, create_account
from finances.domain.models import DataSource
from finances.domain.networth import NetWorthPoint, point_days
from finances.web.app import create_app
from tests.support import WEB_PORT, page, texts

TODAY = date(2026, 5, 25)


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return found


def test_twelve_months_from_january_start_in_the_year_before() -> None:
    days = point_days(date(2026, 1, 15), 12)
    assert days[0] == date(2025, 2, 28)
    assert days[-1] == date(2026, 1, 15)
    assert len(days) == 12


def test_only_a_card_is_a_negative_net_worth(tmp_settings: Settings) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        add_balance_snapshot(session, card.id, date(2026, 5, 24), -45000, DataSource.STATEMENT)
        points = net_worth_over_time(session, TODAY, 1)
    engine.dispose()
    assert points == [NetWorthPoint(TODAY, -45000, 1)]


def test_a_balance_after_today_is_not_counted(tmp_settings: Settings) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        add_balance_snapshot(session, checking.id, date(2026, 6, 1), 999900, DataSource.STATEMENT)
        points = net_worth_over_time(session, TODAY, 12)
    engine.dispose()
    assert points == []


def test_two_snapshots_on_one_date_take_the_later_added(tmp_settings: Settings) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        add_balance_snapshot(session, checking.id, date(2026, 5, 20), 100000, DataSource.STATEMENT)
        add_balance_snapshot(session, checking.id, date(2026, 5, 20), 200000, DataSource.AGGREGATOR)
        points = net_worth_over_time(session, TODAY, 1)
    engine.dispose()
    assert points == [NetWorthPoint(TODAY, 200000, 1)]


def test_leading_zero_days_is_still_seven(client: TestClient) -> None:
    upgrade_to_head()
    found = page(client, "/ahead?days=07")
    assert texts(found, "summary")[0] == "Forecast from 2026-05-25 to 2026-05-31."
    assert found.forms[0]["inputs"]["days"] == ("number", "7")
