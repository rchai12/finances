from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.categorize.transfers import pair_transfers
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import add_balance_snapshot, create_account, create_rule
from finances.domain.models import DataSource
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts

TODAY = date(2026, 5, 25)
PROBLEMS = ["Kind", "Account", "Problem", "What to do"]
MONTHS = ["Month", "Spent", "Income", "Change", "Covered"]
FINDINGS = ["Severity", "Type", "About", "Saves a month", "Detail"]
NO_BACKUP = [
    "backup",
    "",
    "No backup yet.",
    "Run fin backup run, or press Back up now on the Backups page.",
]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("finances.web.app._today", lambda: TODAY)
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """April and May 2026 on a card, checking, and savings: a card payment that pairs, a move
    to savings with two possible matches, coffee eight times, a grocery jump, interest, a fee."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        add_balance_snapshot(session, card.id, date(2026, 5, 20), -61234, DataSource.STATEMENT)
        add_balance_snapshot(session, checking.id, date(2026, 4, 30), 310000, DataSource.STATEMENT)
        rows = [
            (card, date(2026, 4, 12), -3000, "FOOBAR GROCERY"),
            (checking, date(2026, 4, 15), 300000, "PAYCHECK EXAMPLE CORP"),
            (card, date(2026, 5, 3), -1500, "BAZ BOOKS"),
            (checking, date(2026, 5, 5), -2000, "TRANSFER TO SAVINGS"),
            (savings, date(2026, 5, 5), 2000, "TRANSFER FROM CHECKING"),
            (savings, date(2026, 5, 6), 2000, "TRANSFER FROM CHECKING"),
            (checking, date(2026, 5, 10), -50000, "PAYMENT TO TEST CARD"),
            (card, date(2026, 5, 11), 50000, "PAYMENT THANK YOU"),
            (card, date(2026, 5, 10), -20000, "FOOBAR GROCERY"),
            (card, date(2026, 5, 20), -3500, "LATE FEE"),
            (card, date(2026, 5, 28), -2345, "PURCHASE INTEREST CHARGE"),
        ] + [(card, date(2026, 5, day), -500, "ACME COFFEE") for day in (1, 2, 4, 6, 8, 11, 13, 15)]
        for number, (account, day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for pattern, category in (
            ("FOOBAR", "Groceries"),
            ("PAYCHECK", "Paycheck"),
            ("ACME COFFEE", "Coffee & Dessert"),
        ):
            create_rule(session, pattern, category)
        categorize(session)
        pair_transfers(session)
    engine.dispose()
    return client


def test_home_is_the_dashboard(home: TestClient) -> None:
    response = home.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert 'href="/" aria-current="page">Home</a>' in response.text
    assert response.text.count('aria-current="page"') == 1
    assert 'href="/">Home</a>' in home.get("/accounts").text
    assert "<script" not in response.text


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_the_dashboard(home: TestClient) -> None:
    found = page(home, "/")
    assert found.rows == [
        PROBLEMS,
        NO_BACKUP,
        MONTHS,
        ["2026-04", "$30.00", "$3,000.00", "", "partly"],
        ["2026-05", "$333.45", "$0.00", "+$303.45", "partly"],
        FINDINGS,
        ["high", "interest", "", "$23.45", "Interest charged: $23.45."],
        [
            "medium",
            "spike",
            "Groceries",
            "$190.00",
            "Groceries: $200.00 this month, against $10.00 a month before.",
        ],
        ["medium", "fees", "", "$35.00", "Fees charged: $35.00."],
    ]
    assert texts(found, "attention") == [
        "6 transactions without a category.",
        "2 transfers waiting for review.",
    ]
    assert texts(found, "summary") == [
        "Today is 2026-05-25.",
        "Cash: $3,100.00. Cards: -$612.34. Other: $0.00.",
        "Net worth: $2,487.66.",
        "No balance yet: Test Savings.",
        "Findings: 4. Could save up to $268.45 a month.",
    ]


def test_every_part_links_to_its_page(home: TestClient) -> None:
    links = page(home, "/").links
    for link in (
        "/categories",
        "/transfers",
        "/backups",
        "/reports",
        "/reports?month=2026-04",
        "/reports?month=2026-05",
        "/insights?month=2026-05",
    ):
        assert link in links, link


def test_a_fresh_backup_and_an_empty_database(client: TestClient, tmp_settings: Settings) -> None:
    upgrade_to_head()
    folder = tmp_settings.effective_backup_dir
    folder.mkdir(parents=True)
    (folder / "finances-20260525-020000.db").write_bytes(b"")
    found = page(client, "/")
    assert texts(found, "empty") == [
        "Every transaction has a category.",
        "No transfers wait for review.",
        "No data problems found.",
        "No accounts.",
        "No findings this month.",
    ]
    assert found.rows == [
        MONTHS,
        ["2026-04", "$0.00", "$0.00", "", "yes"],
        ["2026-05", "$0.00", "$0.00", "$0.00", "yes"],
    ]
