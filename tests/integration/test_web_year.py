from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, set_category_by_hand, set_split
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts

HEADINGS = ["Spent", "Refunds", "Net", "Count"]
ROWS = [
    ["Group", *HEADINGS],
    ["Health", "$130.00", "$20.00", "$110.00", "3"],
    ["Personal", "$51.00", "$0.00", "$51.00", "2"],
    ["Food", "$20.00", "$0.00", "$20.00", "1"],
    ["Category", *HEADINGS],
    ["Medical", "$130.00", "$20.00", "$110.00", "3"],
    ["Gifts & Donations", "$51.00", "$0.00", "$51.00", "2"],
    ["Groceries", "$20.00", "$0.00", "$20.00", "1"],
    ["Category", *HEADINGS],
    ["Gifts & Donations", "$51.00", "$0.00", "$51.00", "2"],
    ["Medical", "$130.00", "$20.00", "$110.00", "3"],
    ["Taxes", "$0.00", "$0.00", "$0.00", "0"],
]
SUMMARY = [
    "Year 2026, from 2026-01-01 to 2026-12-31.",
    "Spent: $201.00. Refunds: $20.00. Net: $181.00. Income: $3,000.00.",
    "Transfers left out: 0.",
]


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    monkeypatch.setattr("finances.web.app._today", lambda: date(2024, 8, 1))
    return found


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """The year of tests/e2e/test_cli_year.py: Medical, a refund, a split, Gifts & Donations
    on both edges' sides, and a paycheck."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [
            (date(2026, 2, 10), -12000, "ACME CLINIC", "Medical"),
            (date(2026, 3, 5), -5000, "BAZ CHARITY", "Gifts & Donations"),
            (date(2026, 4, 1), -3000, "FOOBAR GROCERY", None),
            (date(2026, 5, 1), 2000, "ACME CLINIC", "Medical"),
            (date(2026, 6, 1), 300000, "PAYCHECK EXAMPLE CORP", "Paycheck"),
            (date(2025, 12, 31), -9999, "ACME CLINIC", "Medical"),
            (date(2026, 12, 31), -100, "BAZ CHARITY", "Gifts & Donations"),
        ]
        for number, (day, cents, description, _) in enumerate(rows, start=1):
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
        for number, (_, _, _, category) in enumerate(rows, start=1):
            if category is not None:
                set_category_by_hand(session, number, category)
        set_split(session, 3, [(-2000, "Groceries"), (-1000, "Medical")])
    engine.dispose()
    client.get("/categories")
    return client


def test_the_year_page(home: TestClient) -> None:
    response = home.get("/year?year=2026")
    assert response.status_code == 200
    found = Page(response.text)
    assert texts(found, "summary") == SUMMARY
    assert found.rows == ROWS
    assert texts(found, "years") == ["2025 · 2027"]
    assert "/transactions?from=2026-01-01&to=2026-12-31&group=Health&kind=spending&limit=1000" in (
        found.links
    )
    assert (
        "/transactions?from=2026-01-01&to=2026-12-31&category=Gifts%20%26%20Donations"
        "&kind=spending&limit=1000"
    ) in found.links


def test_this_year_by_default(home: TestClient) -> None:
    found = page(home, "/year")
    assert texts(found, "summary")[0] == "Year 2024, from 2024-01-01 to 2024-12-31."
    assert found.find("/year")["inputs"]["year"] == ("text", "2024")
    assert texts(found, "empty") == ["No spending.", "No spending."]


@pytest.mark.parametrize(("year", "years"), [("1", "2"), ("9999", "9998")])
def test_the_first_and_last_years(home: TestClient, year: str, years: str) -> None:
    assert texts(page(home, f"/year?year={year}"), "years") == [years]


@pytest.mark.parametrize("year", ["abc", "0", "10000", "２０２６"])
def test_a_year_that_is_refused(home: TestClient, year: str) -> None:
    response = home.get(f"/year?year={year}")
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == ["year must be from 1 to 9999"]
    assert (found.rows, texts(found, "summary")) == ([], [])


def test_a_line_drills_down_to_its_transactions(home: TestClient) -> None:
    link = next(href for href in page(home, "/year?year=2026").links if "category=Medical" in href)
    rows = page(home, link).rows
    assert [row[4] for row in rows[1:]] == ["$20.00", "-$10.00", "-$120.00"]


def test_reports_links_to_the_year(home: TestClient) -> None:
    assert "/year" in page(home, "/reports").links


def tax_forms(found: Page) -> list[str]:
    return [
        form["inputs"]["category"][1]
        for form in found.all("/categories/tax")
        if form["inputs"]["tax"] == ("hidden", "off")
    ]


def test_the_tax_card(home: TestClient) -> None:
    assert tax_forms(page(home, "/categories")) == ["Gifts & Donations", "Medical", "Taxes"]


def test_marking_on_the_page(home: TestClient) -> None:
    on = post(home, "/categories/tax", category="groceries", tax="on")
    assert (on.status_code, on.headers["location"]) == (303, "/categories?notice=tax-set")
    found = page(home, "/categories?notice=tax-set")
    assert texts(found, "notice") == ["Marked tax-relevant."]
    assert tax_forms(found) == ["Gifts & Donations", "Groceries", "Medical", "Taxes"]
    off = post(home, "/categories/tax", category="Medical", tax="off")
    assert (off.status_code, off.headers["location"]) == (303, "/categories?notice=tax-cleared")
    found = page(home, "/categories?notice=tax-cleared")
    assert texts(found, "notice") == ["No longer tax-relevant."]
    assert tax_forms(found) == ["Gifts & Donations", "Groceries", "Taxes"]


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        (
            {"category": "Health", "tax": "on"},
            "a group cannot be tax-relevant; mark its categories",
        ),
        ({"category": "Medical", "tax": "maybe"}, "tax must be on or off"),
    ],
)
def test_marking_refused(home: TestClient, fields: dict, message: str) -> None:
    response = post(home, "/categories/tax", **fields)
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == [message]
