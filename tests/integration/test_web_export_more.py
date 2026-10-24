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
    set_category_by_hand,
    set_note,
    set_split,
)
from finances.web.app import create_app
from tests.e2e.test_cli_export import TRANSACTIONS, folder
from tests.integration.test_web_export import HEADER, download
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, run, texts


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [
            (date(2026, 5, 1), -1234, "ACME COFFEE"),
            (date(2026, 5, 3), -2000, "FOOBAR GROCERY"),
            (date(2026, 5, 5), 500, "ACME COFFEE"),
            (date(2025, 12, 31), -999, "ACME COFFEE"),
        ]
        for number, (day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for number in (1, 3, 4):
            set_category_by_hand(session, number, "Coffee & Dessert")
        set_split(session, 2, [(-1200, "Groceries"), (-800, "Home & Garden")])
        add_tags(session, [1], "work")
        set_note(session, 1, "client lunch")
    engine.dispose()
    return client


def test_a_blank_year_exports_today(home: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("finances.web.app._today", lambda: date(2024, 8, 1))
    status, _, name, _body = download(home, "/export/year")
    assert (status, name) == (200, 'attachment; filename="year-2024.csv"')


def test_spending_with_no_options_exports_this_month(
    home: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("finances.web.app._today", lambda: date(2026, 5, 15))
    status, _, name, _body = download(home, "/export/spending")
    assert (status, name) == (
        200,
        'attachment; filename="spending-by-category-2026-05-01-to-2026-05-31.csv"',
    )


def test_transactions_by_tag_and_a_named_date_range(home: TestClient) -> None:
    status, _, name, body = download(home, "/export/transactions?tag=work")
    assert (status, name) == (200, 'attachment; filename="transactions.csv"')
    assert body == (
        HEADER + "1,2026-05-01,2026-05-01,Test Card,ACME COFFEE,ACME COFFEE,Coffee & Dessert,"
        "Food,spending,-12.34,,,,work,client lunch\r\n"
    )
    _, _, named, _body = download(
        home, "/export/transactions?from=2026-05-02&to=2026-05-31&kind=spending"
    )
    assert named == 'attachment; filename="transactions-2026-05-02-to-2026-05-31.csv"'
    _, _, only_from, _body = download(home, "/export/transactions?from=2026-05-02")
    assert only_from == 'attachment; filename="transactions.csv"'


def test_a_bad_limit_is_refused_as_the_page_refuses_it(home: TestClient) -> None:
    response = home.get("/export/transactions?limit=x")
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["limit must be a whole number from 1 to 1000"]


@pytest.mark.parametrize("path", ["/export/transactions", "/export/year", "/export/spending"])
def test_downloads_need_a_migrated_database(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 503
    assert texts(Page(response.text), "error") == [WEB_NOT_MIGRATED]


def test_fin_export_transactions_writes_the_same_bytes(
    home: TestClient, tmp_settings: Settings
) -> None:
    result = run("export", "transactions", "--from", "2026-01-01", "--to", "2026-12-31")
    written = folder(tmp_settings) / "transactions-2026-01-01-to-2026-12-31.csv"
    assert result.exit_code == 0
    assert written.read_bytes().decode("utf-8") == TRANSACTIONS
