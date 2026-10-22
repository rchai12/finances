import html
import json
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import add_balance_snapshot, create_account, create_rule
from finances.domain.models import DataSource
from finances.web.app import SECURITY_HEADERS, create_app
from tests.support import WEB_PORT

TODAY = date(2026, 5, 25)
CARD = "/account?name=Test%20Card"
MONTHS = [
    "2025-06",
    "2025-07",
    "2025-08",
    "2025-09",
    "2025-10",
    "2025-11",
    "2025-12",
    "2026-01",
    "2026-02",
    "2026-03",
    "2026-04",
    "2026-05",
]
SCRIPTS = [
    '<script src="/static/vendor/chart.umd.js" defer></script>',
    '<script src="/static/charts.js" defer></script>',
]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Test Card: groceries in April and May, a book, and a refund that leaves Shopping below
    zero in May; two balances. Test Checking has nothing."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        create_account(session, "Test Checking", "Test Bank", "checking")
        add_balance_snapshot(session, card.id, date(2026, 4, 30), -45000, DataSource.STATEMENT)
        add_balance_snapshot(session, card.id, date(2026, 5, 20), -61234, DataSource.AGGREGATOR)
        for number, (day, cents, description) in enumerate(
            (
                (date(2026, 4, 12), -3000, "FOOBAR GROCERY"),
                (date(2026, 5, 10), -20000, "FOOBAR GROCERY"),
                (date(2026, 5, 12), -1500, "BAZ BOOKS"),
                (date(2026, 5, 14), 2000, "BAZ TECH"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        create_rule(session, "FOOBAR", "Groceries")
        create_rule(session, "BAZ TECH", "Electronics")
        categorize(session)
    engine.dispose()
    return client


def charts(text: str) -> list[dict]:
    return [json.loads(html.unescape(found)) for found in re.findall(r'data-chart="([^"]*)"', text)]


def test_the_policy_allows_only_the_sites_own_scripts(home: TestClient) -> None:
    response = home.get(CARD)
    assert (
        response.headers["content-security-policy"] == SECURITY_HEADERS["content-security-policy"]
    )
    assert "script-src 'self';" in response.headers["content-security-policy"]


def test_the_account_page_loads_two_scripts_and_no_inline_script(home: TestClient) -> None:
    text = home.get(CARD).text
    assert re.findall(r"<script[^>]*>[^<]*</script>", text) == SCRIPTS
    for path, kind in (
        ("/static/vendor/chart.umd.js", "javascript"),
        ("/static/charts.js", "javascript"),
    ):
        response = home.get(path)
        assert response.status_code == 200
        assert kind in response.headers["content-type"]


@pytest.mark.parametrize("path", ["/", "/accounts", "/transactions", "/insights"])
def test_other_pages_load_no_script(home: TestClient, path: str) -> None:
    assert "<script" not in home.get(path).text


def test_the_charts_carry_cents(home: TestClient) -> None:
    assert charts(home.get(CARD).text) == [
        {
            "kind": "pie",
            "labels": ["Food", "Uncategorized"],
            "series": [{"name": "Spent", "cents": [20000, 1500]}],
        },
        {
            "kind": "bar",
            "labels": MONTHS,
            "series": [
                {"name": "Spent", "cents": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3000, 19500]},
                {"name": "Income", "cents": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]},
            ],
        },
        {
            "kind": "line",
            "labels": ["2026-04-30", "2026-05-20"],
            "series": [{"name": "Balance", "cents": [-45000, -61234]}],
        },
    ]


def test_each_chart_keeps_its_table(home: TestClient) -> None:
    text = home.get(CARD).text
    assert text.count('<div class="chart">') == 3
    for heading in ("<th>Group</th>", "<th>Month</th>", "<th>Date</th>"):
        assert heading in text


def test_no_chart_without_something_to_draw(home: TestClient) -> None:
    text = home.get("/account?name=Test%20Checking").text
    assert [chart["kind"] for chart in charts(text)] == ["bar"]
    april = home.get(f"{CARD}&month=2026-04").text
    assert charts(april)[0] == {
        "kind": "pie",
        "labels": ["Food"],
        "series": [{"name": "Spent", "cents": [3000]}],
    }
    march = home.get(f"{CARD}&month=2026-03").text
    assert [chart["kind"] for chart in charts(march)] == ["bar", "line"]
