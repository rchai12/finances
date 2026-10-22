from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule, set_budget
from finances.web.app import create_app
from tests.support import WEB_PORT, page, texts

SPENDING = ["Category", "Spent", "Refunds", "Net", "Count"]
GROUPS = ["Group", "Spent", "Refunds", "Net", "Count"]
BACK = '<td class="amount pos">$5.99 back</td>'


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: date(2026, 6, 20))
    return found


@pytest.fixture
def refunded(client: TestClient) -> TestClient:
    """Groceries bought in May and partly refunded in June; a box bought in May."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [
            (date(2026, 5, 10), -2599, "FOOBAR GROCERY"),
            (date(2026, 5, 14), -1200, "BAZ BOX"),
            (date(2026, 6, 12), 599, "FOOBAR GROCERY"),
        ]
        for number, (day, cents, description) in enumerate(rows, start=1):
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
        categorize(session)
        set_budget(session, "Groceries", 10000)
    engine.dispose()
    return client


def test_the_reports_page(refunded: TestClient) -> None:
    html = refunded.get("/reports?month=2026-06").text
    found = page(refunded, "/reports?month=2026-06")
    start = found.rows.index(SPENDING)
    assert found.rows[start : start + 2] == [
        SPENDING,
        ["Groceries", "$0.00", "$5.99", "$5.99 back", "1"],
    ]
    assert ["2026-06", "$5.99 back", "$0.00", "-$43.98", "partly"] in found.rows
    assert "Spent: $0.00. Refunds: $5.99. Net: $5.99 back. Income: $0.00." in texts(
        found, "summary"
    )
    assert html.count(BACK) == 2


def test_the_account_page(refunded: TestClient) -> None:
    path = "/account?name=Test%20Card&month=2026-06"
    found = page(refunded, path)
    start = found.rows.index(GROUPS)
    assert found.rows[start : start + 2] == [GROUPS, ["Food", "$0.00", "$5.99", "$5.99 back", "1"]]
    assert ["2026-06", "$5.99 back", "$0.00"] in found.rows
    assert refunded.get(path).text.count(BACK) == 2


def test_the_budgets_page(refunded: TestClient) -> None:
    found = page(refunded, "/budgets?month=2026-06")
    row = next(row for row in found.rows if row and row[0] == "Groceries")
    assert row[:6] == ["Groceries", "category", "$100.00", "$5.99 back", "$105.99", "0%"]
