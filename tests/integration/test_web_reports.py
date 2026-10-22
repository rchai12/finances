from datetime import UTC, date, datetime
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import FeedPullRow, TransactionRow
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    create_rule,
    create_statement,
    set_balance_snapshot,
)
from finances.domain.models import DataSource
from finances.web.app import create_app

PORT = 8765
NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"
BALANCES = ["Account", "Type", "Balance", "As of", "From"]
MONTHS = ["Month", "Spent", "Income", "Change", "Covered"]
BY = ["category", "group", "merchant", "person", "account", "bank", "card"]


class Page(HTMLParser):
    """The parts of a page the tests read: table rows, paragraphs, and forms."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.paragraphs: list[tuple[str, str]] = []
        self.forms: list[dict] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.paragraph: str | None = None
        self.text: list[str] = []
        self.form: dict | None = None
        self.select: str | None = None
        self.links: list[str] = []
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag == "a":
            self.links.append(values.get("href", ""))
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag == "p":
            self.paragraph = values.get("class", "")
            self.text = []
        elif tag == "form":
            self.form = {
                "action": values.get("action", ""),
                "method": values.get("method", "get"),
                "inputs": {},
                "selects": {},
            }
            self.forms.append(self.form)
        elif tag == "input" and self.form is not None:
            self.form["inputs"][values.get("name", "")] = (
                values.get("type", "text"),
                values.get("value", ""),
            )
        elif tag == "select" and self.form is not None:
            self.select = values.get("name", "")
            self.form["selects"][self.select] = []
        elif tag == "option" and self.form is not None and self.select is not None:
            self.form["selects"][self.select].append(
                (values.get("value", ""), "selected" in values)
            )

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "p" and self.paragraph is not None:
            self.paragraphs.append((self.paragraph, "".join(self.text).strip()))
            self.paragraph = None
        elif tag == "form":
            self.form = None
        elif tag == "select":
            self.select = None

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)
        if self.paragraph is not None:
            self.text.append(data)

    def all(self, action: str) -> list[dict]:
        return [form for form in self.forms if form["action"] == action]

    def find(self, action: str) -> dict:
        found = [form for form in self.forms if form["action"] == action]
        assert len(found) == 1, action
        return found[0]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")


def statement(session, account, number: int, start: date, end: date, closing: int) -> None:
    create_statement(
        session,
        account_id=account.id,
        source_filename=f"statement-{number}.pdf",
        file_sha256=f"s{number:02d}".ljust(64, "0"),
        parser_name="test",
        period_start=start,
        period_end=end,
        opening_balance_cents=0,
        closing_balance_cents=closing,
        lines_parsed=0,
        rows_inserted=0,
        rows_duplicate=0,
    )
    add_balance_snapshot(session, account.id, end, closing, DataSource.STATEMENT)


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """The data of tests/e2e/test_cli_balances_months.py: checking statements for March and
    April; a card statement from 5 March to 4 April, then a SimpleFIN pull on 20 May; a
    quarterly savings statement, March to May."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Example Card Co", "credit_card")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        statement(session, checking, 1, date(2026, 3, 1), date(2026, 3, 31), 250000)
        statement(session, checking, 2, date(2026, 4, 1), date(2026, 4, 30), 310000)
        statement(session, card, 3, date(2026, 3, 5), date(2026, 4, 4), -45000)
        statement(session, savings, 4, date(2026, 3, 1), date(2026, 5, 31), 1000000)
        set_balance_snapshot(session, card.id, date(2026, 5, 20), -61234, DataSource.AGGREGATOR)
        session.add(
            FeedPullRow(
                account_id=card.id,
                inserted=1,
                updated=0,
                removed=0,
                unchanged=0,
                feed_total_cents=-1500,
                balance_cents=-61234,
                balance_date=date(2026, 5, 20),
                drift_cents=None,
                pulled_at=datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
            )
        )
        for number, (account, day, cents, description) in enumerate(
            (
                (card, date(2026, 3, 10), -2000, "FOOBAR GROCERY"),
                (card, date(2026, 4, 12), -3000, "FOOBAR GROCERY"),
                (card, date(2026, 5, 3), -1500, "BAZ BOOKS"),
                (checking, date(2026, 3, 15), 300000, "PAYCHECK EXAMPLE CORP"),
                (checking, date(2026, 4, 15), 300000, "PAYCHECK EXAMPLE CORP"),
                (checking, date(2026, 4, 25), -12000, "ACME UTILITY"),
            ),
            start=1,
        ):
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
        create_rule(session, "PAYCHECK", "Paycheck")
        categorize(session)
    engine.dispose()
    return client


def page(client: TestClient, path: str) -> Page:
    return Page(client.get(path).text)


def section(rows: list[list[str]], heading: list[str]) -> list[list[str]]:
    """The rows of the table that starts with this heading row."""
    start = rows.index(heading)
    end = start + 1
    while (
        end < len(rows) and len(rows[end]) == len(heading) and rows[end] not in (BALANCES, MONTHS)
    ):
        end += 1
    return rows[start:end]


def texts(found: Page, kind: str) -> list[str]:
    return [text for name, text in found.paragraphs if name == kind]


# The menu and the page


def test_the_menu_has_reports(home: TestClient) -> None:
    html = home.get("/reports?month=2026-05").text
    assert 'href="/reports" aria-current="page">Reports</a>' in html
    assert html.count('aria-current="page"') == 1
    assert 'href="/reports">Reports</a>' in home.get("/transfers").text


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get("/reports")
    assert response.status_code == 503
    assert ("error", NOT_MIGRATED) in Page(response.text).paragraphs


def test_no_accounts(client: TestClient) -> None:
    upgrade_to_head()
    found = page(client, "/reports?month=2026-05")
    assert ("empty", "No accounts.") in found.paragraphs
    assert ("empty", "No spending.") in found.paragraphs


def test_a_month(home: TestClient) -> None:
    response = home.get("/reports?month=2026-05")
    assert response.status_code == 200
    found = Page(response.text)
    assert section(found.rows, BALANCES) == [
        BALANCES,
        ["Test Card", "credit_card", "-$612.34", "2026-05-20", "SimpleFIN"],
        ["Test Checking", "checking", "$3,100.00", "2026-04-30", "statement"],
        ["Test Savings", "savings", "$10,000.00", "2026-05-31", "statement"],
    ]
    assert section(found.rows, MONTHS) == [
        MONTHS,
        ["2025-12", "$0.00", "$0.00", "", "partly"],
        ["2026-01", "$0.00", "$0.00", "$0.00", "partly"],
        ["2026-02", "$0.00", "$0.00", "$0.00", "partly"],
        ["2026-03", "$20.00", "$3,000.00", "+$20.00", "partly"],
        ["2026-04", "$150.00", "$3,000.00", "+$130.00", "yes"],
        ["2026-05", "$15.00", "$0.00", "-$135.00", "partly"],
    ]
    assert found.rows[-2:] == [["Category", "Spent", "Count"], ["Uncategorized", "$15.00", "1"]]
    assert texts(found, "summary") == [
        "Cash: $13,100.00. Cards: -$612.34. Other: $0.00.",
        "Net worth: $12,487.66.",
        "Spending from 2026-05-01 to 2026-05-31, by category.",
        "Spent: $15.00. Income: $0.00.",
        "Transfers left out: 0.",
    ]
    assert texts(found, "hint") == [
        "2025-12: no data for the whole month from Test Card, Test Checking, Test Savings.",
        "2026-01: no data for the whole month from Test Card, Test Checking, Test Savings.",
        "2026-02: no data for the whole month from Test Card, Test Checking, Test Savings.",
        "2026-03: no data for the whole month from Test Card.",
        "2026-05: no data for the whole month from Test Card, Test Checking.",
    ]
    assert [link for link in found.links if link.startswith("/reports?")] == [
        "/reports?month=2025-12",
        "/reports?month=2026-01",
        "/reports?month=2026-02",
        "/reports?month=2026-03",
        "/reports?month=2026-04",
        "/reports?month=2026-05",
    ]


def test_the_form_keeps_what_was_asked(home: TestClient) -> None:
    form = page(home, "/reports?month=2026-05&by=merchant").find("/reports")
    assert form["method"] == "get"
    assert form["inputs"]["month"] == ("month", "2026-05")
    assert form["inputs"]["from"] == ("date", "")
    assert form["inputs"]["to"] == ("date", "")
    assert form["selects"]["by"] == [(item, item == "merchant") for item in BY]
    assert "csrf" not in form["inputs"]


def test_a_range_by_merchant_and_months_ending_with_it(home: TestClient) -> None:
    found = page(home, "/reports?from=2026-04-01&to=2026-04-30&by=merchant")
    assert found.rows[-3:] == [
        ["Merchant", "Spent", "Count"],
        ["ACME UTILITY", "$120.00", "1"],
        ["FOOBAR GROCERY", "$30.00", "1"],
    ]
    assert texts(found, "summary")[2:] == [
        "Spending from 2026-04-01 to 2026-04-30, by merchant.",
        "Spent: $150.00. Income: $3,000.00.",
        "Transfers left out: 0.",
    ]
    assert [row[0] for row in section(found.rows, MONTHS)] == [
        "Month",
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
    ]
    form = found.find("/reports")
    assert (form["inputs"]["from"], form["inputs"]["to"]) == (
        ("date", "2026-04-01"),
        ("date", "2026-04-30"),
    )


def test_a_month_without_spending(home: TestClient) -> None:
    found = page(home, "/reports?month=2026-06")
    assert ("empty", "No spending.") in found.paragraphs
    assert texts(found, "summary")[2:] == [
        "Spending from 2026-06-01 to 2026-06-30, by category.",
        "Spent: $0.00. Income: $0.00.",
        "Transfers left out: 0.",
    ]


def test_no_month_means_this_month(home: TestClient) -> None:
    response = home.get("/reports")
    assert response.status_code == 200
    headings = [
        text for text in texts(Page(response.text), "summary") if text.startswith("Spending")
    ]
    assert len(headings) == 1
    assert headings[0].endswith(", by category.")


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("month=2026-13", "month must be a year and month, like 2026-05"),
        ("month=2026-05&from=2026-05-01", "give a month, or from and to, not both"),
        ("from=2026-05-01", "give both from and to"),
        ("to=2026-05-01", "give both from and to"),
        ("from=2026-5-1&to=2026-05-02", "from must be a date as YYYY-MM-DD"),
        ("from=2026-05-01&to=2026-05-32", "to must be a date as YYYY-MM-DD"),
        ("from=2026-05-20&to=2026-05-10", "the start date is after the end date"),
        (
            "month=2026-05&by=vendor",
            "by must be one of: category, group, merchant, person, account, bank, card",
        ),
    ],
)
def test_a_refused_report(home: TestClient, query: str, message: str) -> None:
    response = home.get(f"/reports?{query}")
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", message) in found.paragraphs
    assert not any(text.startswith("Spending from") for text in texts(found, "summary"))
    assert section(found.rows, BALANCES)[1][0] == "Test Card"
