from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, texts

FINDINGS = ["Severity", "Type", "About", "Saves a month", "Detail"]
RECURRING = ["Merchant", "Every", "Amount", "Monthly", "Count", "Last", "Next"]
MERCHANTS = ["Merchant", "Visits", "Spent", "Average", "Baseline", "Change", "Weekend"]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """The data of tests/e2e/test_cli_insights.py, plus a yearly cloud plan last charged in
    January 2026, before the four months a May report reads."""
    rows = [
        (date(2026, 2, 3), -6000, "ACME DINER"),
        (date(2026, 3, 17), -6000, "ACME DINER"),
        (date(2026, 4, 9), -6000, "ACME DINER"),
        (date(2026, 5, 22), -20000, "ACME DINER"),
        (date(2026, 2, 5), -1599, "QUUX STREAMING"),
        (date(2026, 3, 5), -1599, "QUUX STREAMING"),
        (date(2026, 4, 5), -1599, "QUUX STREAMING"),
        (date(2026, 5, 5), -1799, "QUUX STREAMING"),
        (date(2026, 3, 12), -999, "BAZ VIDEO"),
        (date(2026, 4, 12), -999, "BAZ VIDEO"),
        (date(2026, 5, 12), -999, "BAZ VIDEO"),
        (date(2026, 5, 28), -2345, "PURCHASE INTEREST CHARGE"),
        (date(2025, 1, 8), -9900, "QUUX CLOUD"),
        (date(2026, 1, 8), -9900, "QUUX CLOUD"),
    ] + [(date(2026, 5, day), -500, "ACME COFFEE") for day in (2, 3, 6, 9, 10, 13, 16, 17)]
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
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for pattern, category in (
            ("ACME DINER", "Dining"),
            ("QUUX STREAMING", "Subscriptions & Digital"),
            ("BAZ VIDEO", "Subscriptions & Digital"),
            ("QUUX CLOUD", "Subscriptions & Digital"),
            ("ACME COFFEE", "Coffee & Dessert"),
        ):
            create_rule(session, pattern, category)
        categorize(session)
    engine.dispose()
    return client


def table(found: Page, heading: list[str]) -> list[list[str]]:
    """The rows of the table that starts with this heading row."""
    start = found.rows.index(heading)
    end = start + 1
    while end < len(found.rows) and len(found.rows[end]) == len(heading):
        if found.rows[end] in (FINDINGS, RECURRING, MERCHANTS):
            break
        end += 1
    return found.rows[start:end]


def test_the_menu_has_insights(home: TestClient) -> None:
    html = home.get("/insights?month=2026-05").text
    assert 'href="/insights" aria-current="page">Insights</a>' in html
    assert html.count('aria-current="page"') == 1
    assert 'href="/insights">Insights</a>' in home.get("/reports?month=2026-05").text
    assert "<script" not in html


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get("/insights")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_a_month(home: TestClient) -> None:
    response = home.get("/insights?month=2026-05")
    assert response.status_code == 200
    found = Page(response.text)
    assert table(found, FINDINGS) == [
        FINDINGS,
        ["high", "interest", "", "$23.45", "Interest charged: $23.45."],
        [
            "medium",
            "spike",
            "Dining",
            "$140.00",
            "Dining: $200.00 this month, against $60.00 a month before.",
        ],
        [
            "medium",
            "price_increase",
            "QUUX STREAMING",
            "$2.00",
            "QUUX STREAMING went from $15.99 to $17.99.",
        ],
        [
            "low",
            "frequent_small",
            "ACME COFFEE",
            "$20.00",
            "ACME COFFEE: 8 visits averaging $5.00.",
        ],
        [
            "low",
            "subscription_overlap",
            "Subscriptions & Digital",
            "$8.25",
            "Subscriptions & Digital: QUUX STREAMING ($17.99), BAZ VIDEO ($9.99),"
            " QUUX CLOUD ($8.25).",
        ],
    ]
    assert table(found, RECURRING) == [
        RECURRING,
        ["QUUX STREAMING", "month", "$17.99", "$17.99", "4", "2026-05-05", "2026-06-05"],
        ["BAZ VIDEO", "month", "$9.99", "$9.99", "3", "2026-05-12", "2026-06-12"],
        ["QUUX CLOUD", "year", "$99.00", "$8.25", "2", "2026-01-08", "2027-01-08"],
    ]
    assert table(found, MERCHANTS) == [
        MERCHANTS,
        ["ACME DINER", "1", "$200.00", "$200.00", "$60.00", "+$140.00", "0"],
        ["ACME COFFEE", "8", "$40.00", "$5.00", "$0.00", "+$40.00", "6"],
        ["PURCHASE INTEREST CHARGE", "1", "$23.45", "$23.45", "$0.00", "+$23.45", "0"],
        ["QUUX STREAMING", "1", "$17.99", "$17.99", "$15.99", "+$2.00", "0"],
        ["BAZ VIDEO", "1", "$9.99", "$9.99", "$6.66", "+$3.33", "0"],
    ]
    assert texts(found, "summary") == [
        "Insights for 2026-05.",
        "Findings: 5. Could save up to $193.70 a month.",
        "Recurring: 3 active, $36.23 a month.",
    ]
    assert found.find("/insights")["inputs"]["month"] == ("month", "2026-05")


def test_a_yearly_plan_charged_before_the_window_still_overlaps(home: TestClient) -> None:
    found = page(home, "/insights?month=2026-04")
    assert table(found, FINDINGS)[1:] == [
        [
            "low",
            "subscription_overlap",
            "Subscriptions & Digital",
            "$8.25",
            "Subscriptions & Digital: QUUX STREAMING ($15.99), QUUX CLOUD ($8.25).",
        ]
    ]


def test_a_month_with_nothing(home: TestClient) -> None:
    found = page(home, "/insights?month=2024-05")
    assert texts(found, "empty") == ["No findings.", "No recurring charges.", "No spending."]
    assert texts(found, "summary") == [
        "Insights for 2024-05.",
        "Recurring: 0 active, $0.00 a month.",
    ]


def test_no_month_means_this_month(home: TestClient) -> None:
    response = home.get("/insights")
    assert response.status_code == 200
    assert texts(Page(response.text), "summary")[0].startswith("Insights for ")


@pytest.mark.parametrize("month", ["2026-13", "May", "2026-5"])
def test_a_month_that_is_not_one(home: TestClient, month: str) -> None:
    response = home.get(f"/insights?month={month}")
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", "month must be a year and month, like 2026-05") in found.paragraphs
    assert texts(found, "summary") == []
    assert found.find("/insights")["inputs"]["month"] == ("month", month)
