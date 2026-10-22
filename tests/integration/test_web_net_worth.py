import html
import json
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import add_balance_snapshot, create_account, set_account_active
from finances.domain.models import DataSource
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, texts

TODAY = date(2026, 5, 25)
HEADING = ["Date", "Net worth", "Accounts"]
SCRIPTS = [
    '<script src="/static/vendor/chart.umd.js" defer></script>',
    '<script src="/static/charts.js" defer></script>',
]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return found


@pytest.fixture
def money(client: TestClient) -> TestClient:
    """Checking from March, the card from April, savings from May; a closed account; and a
    checking balance dated after today."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        closed = create_account(session, "Test Old", "Test Bank", "checking")
        for account, day, cents in (
            (checking, date(2026, 3, 15), 200000),
            (checking, date(2026, 4, 30), 250000),
            (checking, date(2026, 5, 20), 300000),
            (checking, date(2026, 6, 1), 999900),
            (card, date(2026, 4, 30), -30000),
            (card, date(2026, 5, 24), -45000),
            (savings, date(2026, 5, 1), 100000),
            (closed, date(2026, 1, 31), 500000),
        ):
            add_balance_snapshot(session, account.id, day, cents, DataSource.STATEMENT)
        set_account_active(session, closed.id, False)
    engine.dispose()
    return client


def section(rows: list[list[str]]) -> list[list[str]]:
    start = rows.index(HEADING)
    end = start + 1
    while end < len(rows) and len(rows[end]) == len(HEADING):
        end += 1
    return rows[start:end]


def charts(text: str) -> list[dict]:
    return [json.loads(html.unescape(found)) for found in re.findall(r'data-chart="([^"]*)"', text)]


def test_net_worth_over_time(money: TestClient) -> None:
    response = money.get("/reports")
    assert response.status_code == 200
    assert section(Page(response.text).rows) == [
        HEADING,
        ["2026-03-31", "$2,000.00", "1"],
        ["2026-04-30", "$2,200.00", "2"],
        ["2026-05-25", "$3,550.00", "3"],
    ]
    assert charts(response.text) == [
        {
            "kind": "line",
            "labels": ["2026-03-31", "2026-04-30", "2026-05-25"],
            "series": [{"name": "Net worth", "cents": [200000, 220000, 355000]}],
        }
    ]
    assert re.findall(r"<script[^>]*>[^<]*</script>", response.text) == SCRIPTS
    assert response.text.count('<div class="chart">') == 1


def test_the_months_follow_today_not_the_month_shown(money: TestClient) -> None:
    rows = section(Page(money.get("/reports?month=2026-03").text).rows)
    assert rows[-1] == ["2026-05-25", "$3,550.00", "3"]


def test_no_balances_yet(client: TestClient) -> None:
    upgrade_to_head()
    response = client.get("/reports")
    assert texts(Page(response.text), "empty")[:2] == ["No accounts.", "No balances yet."]
    assert "<script" not in response.text
    assert "data-chart" not in response.text


@pytest.mark.parametrize("days", ["٣", "²"])
def test_days_take_only_the_digits_0_to_9(money: TestClient, days: str) -> None:
    response = money.get("/ahead", params={"days": days})
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["days must be a whole number from 1 to 90"]
