from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from finances.web.app import create_app
from tests.support import WEB_PORT, page, texts

RECURRING = ["Merchant", "Every", "Amount", "Monthly", "Count", "Last", "Next"]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    """A card with a streaming plan still charged in May and a gym that stopped in February."""
    rows = [(date(2026, month, 5), -1599, "QUUX STREAMING") for month in (3, 4, 5)] + [
        (date(2026, month, 10), -3000, "OLD GYM") for month in (1, 2, 3)
    ]
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Example Card Co", "credit_card")
        for number, (day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"m{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


def test_only_active_recurring_charges_are_listed(client: TestClient) -> None:
    found = page(client, "/insights?month=2026-05")
    start = found.rows.index(RECURRING)
    assert found.rows[start : start + 2] == [
        RECURRING,
        ["QUUX STREAMING", "month", "$15.99", "$15.99", "3", "2026-05-05", "2026-06-05"],
    ]
    assert all(row[0] != "OLD GYM" for row in found.rows[start:] if len(row) == len(RECURRING))
    assert texts(found, "summary")[-1] == "Recurring: 1 active, $15.99 a month."
