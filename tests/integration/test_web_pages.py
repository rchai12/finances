from datetime import date
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import AccountRow, TransactionRow
from finances.db.repositories import (
    create_account,
    create_feed_pull,
    create_person,
    map_feed_account,
    set_account_owner,
    set_cardholder_alias,
)
from finances.web.app import create_app

PORT = 8765
NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"


class Page(HTMLParser):
    """The parts of a page the tests read: table rows, select options, and paragraphs."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.options: dict[str, list[tuple[str, str, bool]]] = {}
        self.paragraphs: list[tuple[str, str]] = []
        self.links: list[str] = []
        self.current: list[str] | None = None
        self.cell: list[str] | None = None
        self.select: str | None = None
        self.option: tuple[str, bool] | None = None
        self.text: list[str] = []
        self.paragraph: str | None = None
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "tr":
            self.current = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag == "select":
            self.select = values.get("name") or ""
            self.options[self.select] = []
        elif tag == "option":
            self.option = (values.get("value") or "", "selected" in values)
            self.text = []
        elif tag == "p":
            self.paragraph = values.get("class") or ""
            self.text = []
        elif tag == "a":
            self.links.append(values.get("href") or "")

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)
        self.text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self.current is not None and self.cell is not None:
            self.current.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.current is not None:
            self.rows.append(self.current)
            self.current = None
        elif tag == "option" and self.select is not None and self.option is not None:
            value, selected = self.option
            self.options[self.select].append((value, "".join(self.text).strip(), selected))
            self.option = None
        elif tag == "select":
            self.select = None
        elif tag == "p" and self.paragraph is not None:
            self.paragraphs.append((self.paragraph, "".join(self.text).strip()))
            self.paragraph = None


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(PORT), base_url=f"http://127.0.0.1:{PORT}")


@pytest.fixture
def household(tmp_settings: Settings, client: TestClient) -> TestClient:
    """Alex owns the card; checking is joint; savings is closed; Sam owns a closed old card."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test <Card>", "Test Bank", "credit_card", last4="1111")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        savings = create_account(session, "Test Savings", "Test Bank", "savings", last4="3333")
        alex = create_person(session, "Alex")
        sam = create_person(session, "Sam")
        set_account_owner(session, card.id, alex.id)
        set_account_owner(session, checking.id, None)
        set_cardholder_alias(session, "SAM DOE", sam.id)
        session.get(AccountRow, savings.id).is_active = False
        old = create_account(session, "Test Old Card", "Test Bank", "credit_card")
        set_account_owner(session, old.id, sam.id)
        session.get(AccountRow, old.id).is_active = False
        for account_id, day, cents, cardholder, card_last4 in (
            (card.id, 8, -800, "SAM DOE", "2222"),
            (checking.id, 7, -700, None, None),
            (card.id, 6, -600, None, None),
            (savings.id, 5, 1000, None, None),
        ):
            session.add(
                TransactionRow(
                    account_id=account_id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=f"ACME <i>{day}</i>",
                    section="purchases" if cents < 0 else None,
                    card_last4=card_last4,
                    cardholder=cardholder,
                    source="statement",
                    fingerprint=f"{day}".ljust(64, "x"),
                )
            )
    engine.dispose()
    return client


@pytest.mark.parametrize("path", ["/accounts", "/people", "/transactions", "/sync"])
def test_every_page_needs_a_migrated_database(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 503
    assert ("error", NOT_MIGRATED) in Page(response.text).paragraphs


@pytest.mark.parametrize(
    ("path", "label"),
    [
        ("/accounts", "Accounts"),
        ("/people", "People"),
        ("/transactions", "Transactions"),
        ("/sync", "SimpleFIN"),
    ],
)
def test_every_page_has_the_menu_and_marks_its_own_entry(
    household: TestClient, path: str, label: str
) -> None:
    html = household.get(path).text
    for href in ("/accounts", "/people", "/transactions", "/sync"):
        assert f'href="{href}"' in html
    assert f'aria-current="page">{label}</a>' in html
    assert html.count('aria-current="page"') == 1
    assert "<script" not in html


def test_accounts(household: TestClient) -> None:
    page = Page(household.get("/accounts").text)
    assert page.rows == [
        ["Name", "Institution", "Type", "Last 4", "Active", "Owner"],
        ["Test <Card>", "Test Bank", "credit_card", "••1111", "yes", "Alex"],
        ["Test Checking", "Test Bank", "checking", "", "yes", "Joint"],
    ]
    assert "/accounts?closed=true" in page.links


def test_accounts_with_closed_ones(household: TestClient) -> None:
    page = Page(household.get("/accounts?closed=true").text)
    assert page.rows[3:] == [
        ["Test Old Card", "Test Bank", "credit_card", "", "no", "Sam"],
        ["Test Savings", "Test Bank", "savings", "••3333", "no", ""],
    ]
    assert "/accounts" in page.links


def test_text_from_the_database_is_escaped(household: TestClient) -> None:
    assert "Test &lt;Card&gt;" in household.get("/accounts").text
    assert "<i>" not in household.get("/transactions").text


def test_accounts_with_none(tmp_settings: Settings, client: TestClient) -> None:
    upgrade_to_head()
    assert ("empty", "No accounts.") in Page(client.get("/accounts").text).paragraphs


def test_people(household: TestClient) -> None:
    assert Page(household.get("/people").text).rows == [
        ["Name", "Owns", "Cardholder names"],
        ["Alex", "Test <Card>", ""],
        ["Sam", "Test Old Card", "SAM DOE"],
    ]


def test_people_with_none(tmp_settings: Settings, client: TestClient) -> None:
    upgrade_to_head()
    assert ("empty", "No people.") in Page(client.get("/people").text).paragraphs


TRANSACTION_HEADINGS = [
    "Date",
    "Account",
    "Description",
    "Category",
    "Amount",
    "Card",
    "Section",
    "Person",
]


def test_transactions(household: TestClient) -> None:
    page = Page(household.get("/transactions").text)
    assert page.rows == [
        TRANSACTION_HEADINGS,
        ["2026-05-08", "Test <Card>", "ACME <i>8</i>", "", "-$8.00", "••2222", "purchases", "Sam"],
        ["2026-05-07", "Test Checking", "ACME <i>7</i>", "", "-$7.00", "", "purchases", "Joint"],
        ["2026-05-06", "Test <Card>", "ACME <i>6</i>", "", "-$6.00", "", "purchases", "Alex"],
        ["2026-05-05", "Test Savings", "ACME <i>5</i>", "", "$10.00", "", "", ""],
    ]
    assert page.options["account"] == [
        ("", "All accounts", True),
        ("Test <Card>", "Test <Card>", False),
        ("Test Checking", "Test Checking", False),
        ("Test Old Card", "Test Old Card", False),
        ("Test Savings", "Test Savings", False),
    ]
    assert page.options["person"] == [
        ("", "Everyone", True),
        ("Alex", "Alex", False),
        ("Sam", "Sam", False),
        ("joint", "Joint", False),
        ("unassigned", "Unassigned", False),
    ]


@pytest.mark.parametrize(
    ("query", "days"),
    [
        ("person=Alex", ["2026-05-06"]),
        ("person=joint", ["2026-05-07"]),
        ("person=unassigned", ["2026-05-05"]),
        ("account=Test+Checking", ["2026-05-07"]),
        ("from=2026-05-06&to=2026-05-07", ["2026-05-07", "2026-05-06"]),
        ("limit=2", ["2026-05-08", "2026-05-07"]),
        ("person=sam&account=test+%3Ccard%3E", ["2026-05-08"]),
        ("account=&person=&from=&to=", ["2026-05-08", "2026-05-07", "2026-05-06", "2026-05-05"]),
    ],
)
def test_transaction_filters(household: TestClient, query: str, days: list[str]) -> None:
    page = Page(household.get(f"/transactions?{query}").text)
    assert [row[0] for row in page.rows[1:]] == days


def test_the_chosen_filters_stay_chosen(household: TestClient) -> None:
    html = household.get("/transactions?person=joint&from=2026-05-01&limit=7").text
    page = Page(html)
    assert ("joint", "Joint", True) in page.options["person"]
    assert 'name="from" value="2026-05-01"' in html
    assert 'name="limit" min="1" max="1000" value="7"' in html


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("person=Nobody", "person not found"),
        ("account=Nope", "account not found"),
        ("from=2026-13-01", "from must be a date as YYYY-MM-DD"),
        ("to=yesterday", "to must be a date as YYYY-MM-DD"),
        ("limit=0", "limit must be a whole number from 1 to 1000"),
        ("limit=1001", "limit must be a whole number from 1 to 1000"),
        ("limit=ten", "limit must be a whole number from 1 to 1000"),
    ],
)
def test_bad_filters(household: TestClient, query: str, message: str) -> None:
    response = household.get(f"/transactions?{query}")
    assert response.status_code == 400
    page = Page(response.text)
    assert ("error", message) in page.paragraphs
    assert page.rows == []


def test_transactions_with_none(household: TestClient) -> None:
    page = Page(household.get("/transactions?account=Test+Checking&from=2027-01-01").text)
    assert ("empty", "No transactions.") in page.paragraphs


def test_sync_status(household: TestClient, keychain) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        map_feed_account(session, 1, "ACT-1", "alex")
        map_feed_account(session, 2, "ACT-2", "sam")
        create_feed_pull(
            session,
            account_id=1,
            inserted=1,
            updated=0,
            removed=0,
            unchanged=0,
            feed_total_cents=-100,
            balance_cents=-100,
            balance_date=date(2026, 5, 9),
            drift_cents=-250,
        )
    engine.dispose()
    keychain.passwords[("finances-simplefin", "alex")] = "https://u:p@bridge.simplefin.org/s"
    rows = Page(household.get("/sync").text).rows
    assert rows[0] == [
        "Link",
        "Account",
        "SimpleFIN account",
        "Keychain",
        "Last pull",
        "Balance date",
        "Drift",
    ]
    assert rows[1][:4] == ["alex", "Test <Card>", "ACT-1", "yes"]
    assert rows[1][4].endswith(" UTC") and len(rows[1][4]) == 20
    assert rows[1][5:] == ["2026-05-09", "-$2.50"]
    assert rows[2] == ["sam", "Test Checking", "ACT-2", "no", "never", "", ""]
    assert "u:p@" not in household.get("/sync").text


def test_sync_status_with_nothing_mapped(household: TestClient) -> None:
    assert ("empty", "No mapped accounts.") in Page(household.get("/sync").text).paragraphs


def test_sync_status_when_the_keychain_fails(household: TestClient) -> None:
    import keyring
    import keyring.backend
    import keyring.errors

    class Broken(keyring.backend.KeyringBackend):
        priority = 1

        def get_password(self, service: str, username: str) -> str | None:
            raise keyring.errors.KeyringLocked("locked")

        def set_password(self, service: str, username: str, password: str) -> None:
            raise keyring.errors.PasswordSetError("no")

        def delete_password(self, service: str, username: str) -> None:
            raise keyring.errors.PasswordDeleteError("no")

    engine = get_engine()
    with session_scope(engine) as session:
        map_feed_account(session, 1, "ACT-1")
    engine.dispose()
    previous = keyring.get_keyring()
    keyring.set_keyring(Broken())
    try:
        assert Page(household.get("/sync").text).rows[1][3] == "unknown"
    finally:
        keyring.set_keyring(previous)
