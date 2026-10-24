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
from tests.support import WEB_PORT, Page, page, texts

HEADER = (
    "ID,Posted,Date,Account,Description,Merchant,Category,Group,Kind,Amount,Card,Person,Part,"
    "Tags,Note\r\n"
)
TRANSACTIONS = (
    HEADER
    + "1,2026-05-01,2026-05-01,Test Card,ACME COFFEE,ACME COFFEE,Coffee & Dessert,Food,spending,"
    "-12.34,,,,work,client lunch\r\n"
    "2,2026-05-03,2026-05-03,Test Card,FOOBAR GROCERY,FOOBAR GROCERY,Groceries,Food,spending,"
    "-12.00,,,1,,\r\n"
    "2,2026-05-03,2026-05-03,Test Card,FOOBAR GROCERY,FOOBAR GROCERY,Home & Garden,Home,"
    "spending,-8.00,,,2,,\r\n"
    "3,2026-05-05,2026-05-05,Test Card,ACME COFFEE,ACME COFFEE,Coffee & Dessert,Food,spending,"
    "5.00,,,,,\r\n"
)
YEAR = (
    "Section,Label,Spent,Refunds,Net,Count\r\n"
    "group,Food,24.34,5.00,19.34,3\r\n"
    "group,Home,8.00,0.00,8.00,1\r\n"
    "category,Groceries,12.00,0.00,12.00,1\r\n"
    "category,Home & Garden,8.00,0.00,8.00,1\r\n"
    "category,Coffee & Dessert,12.34,5.00,7.34,2\r\n"
    "tax,Gifts & Donations,0.00,0.00,0.00,0\r\n"
    "tax,Medical,0.00,0.00,0.00,0\r\n"
    "tax,Taxes,0.00,0.00,0.00,0\r\n"
)
SPENDING = (
    "Category,Spent,Refunds,Net,Count\r\n"
    "Groceries,12.00,0.00,12.00,1\r\n"
    "Home & Garden,8.00,0.00,8.00,1\r\n"
    "Coffee & Dessert,12.34,5.00,7.34,2\r\n"
)


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """The card of tests/e2e/test_cli_export.py: ACME COFFEE -$12.34 (1) tagged work with a
    note; FOOBAR GROCERY -$20.00 (2) split into Groceries -$12.00 and Home & Garden -$8.00; a
    refund of $5.00 (3); and -$9.99 on 2025-12-31 (4)."""
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


def download(client: TestClient, path: str) -> tuple[int, str, str, str]:
    response = client.get(path)
    return (
        response.status_code,
        response.headers.get("content-type", ""),
        response.headers.get("content-disposition", ""),
        response.content.decode("utf-8"),
    )


def test_the_year(home: TestClient) -> None:
    assert download(home, "/export/year?year=2026") == (
        200,
        "text/csv; charset=utf-8",
        'attachment; filename="year-2026.csv"',
        YEAR,
    )


def test_spending(home: TestClient) -> None:
    assert download(home, "/export/spending?month=2026-05") == (
        200,
        "text/csv; charset=utf-8",
        'attachment; filename="spending-by-category-2026-05-01-to-2026-05-31.csv"',
        SPENDING,
    )


def test_transactions_by_dates(home: TestClient) -> None:
    assert download(home, "/export/transactions?from=2026-01-01&to=2026-12-31") == (
        200,
        "text/csv; charset=utf-8",
        'attachment; filename="transactions-2026-01-01-to-2026-12-31.csv"',
        TRANSACTIONS,
    )


def test_transactions_as_the_filters_choose(home: TestClient) -> None:
    status, _, name, body = download(home, "/export/transactions?category=Groceries")
    assert (status, name) == (200, 'attachment; filename="transactions.csv"')
    assert body == (
        HEADER + "2,2026-05-03,2026-05-03,Test Card,FOOBAR GROCERY,FOOBAR GROCERY,Groceries,"
        "Food,spending,-12.00,,,1,,\r\n"
    )
    _, _, _, every = download(home, "/export/transactions?limit=1")
    assert every.count("\r\n") == 6
    assert every.splitlines()[1].startswith("4,2025-12-31,")


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("/export/year?year=abc", "year must be from 1 to 9999"),
        ("/export/year?year=0", "year must be from 1 to 9999"),
        (
            "/export/spending?month=2026-05&by=colour",
            "by must be one of: category, group, merchant, person, account, bank, card",
        ),
        ("/export/transactions?account=Nope", "account not found"),
    ],
)
def test_a_download_that_is_refused(home: TestClient, path: str, message: str) -> None:
    response = home.get(path)
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == [message]


def test_each_page_links_to_its_download(home: TestClient) -> None:
    assert "/export/year?year=2026" in page(home, "/year?year=2026").links
    assert "/export/spending?from=2026-05-01&to=2026-05-31&by=category" in (
        page(home, "/reports?month=2026-05").links
    )
    assert "/export/transactions?category=Groceries" in (
        page(home, "/transactions?category=Groceries").links
    )
    assert "/export/transactions" in page(home, "/transactions").links


def test_a_download_writes_nothing(home: TestClient, tmp_settings: Settings) -> None:
    home.get("/export/year?year=2026")
    assert not (tmp_settings.data_dir / "exports").exists()
    assert home.post("/export/year").status_code == 405
