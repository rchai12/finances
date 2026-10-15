from datetime import date
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from finances.web.app import create_app

PORT = 8765
NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"
POSTS = ["/transfers/find", "/transfers/confirm", "/transfers/reject", "/transfers/unpair"]
REVIEW = ["Out", "Out date", "From", "In", "In date", "To", "Amount", ""]
PAIRS = ["Pair", "Date", "From", "To", "Amount", "Out", "In", "How", ""]
HINT = (
    "Money that leaves one of your accounts and arrives in another, the same amount within 5 days,"
    " is a transfer. When there is only one match it is paired by itself; the rest wait here for"
    " you."
)


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


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """1 and 2: a clear card payment. 3 with 4 or 5: unclear. 6: not a transfer. Nothing paired."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        savings = create_account(session, "Test Savings", "Test Bank", "savings")
        for number, (account, day, cents, description) in enumerate(
            (
                (checking, 3, -50000, "PAYMENT TO TEST CARD"),
                (card, 4, 50000, "PAYMENT THANK YOU"),
                (checking, 5, -2000, "TRANSFER TO SAVINGS"),
                (savings, 5, 2000, "TRANSFER FROM CHECKING"),
                (savings, 6, 2000, "TRANSFER FROM CHECKING"),
                (card, 6, -1250, "SQ *ACME COFFEE"),
            ),
            start=1,
        ):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number}".ljust(64, "0"),
                )
            )
    engine.dispose()
    client.get("/transfers")
    return client


@pytest.fixture
def found(home: TestClient) -> TestClient:
    """As home, after Find transfers: pair 1 is transactions 1 and 2."""
    assert post(home, "/transfers/find").status_code == 303
    return home


def post(client: TestClient, path: str, **fields: str):
    return client.post(
        path, data={"csrf": client.cookies["fin_csrf"], **fields}, follow_redirects=False
    )


def page(client: TestClient, path: str) -> Page:
    return Page(client.get(path).text)


def redirected(response, location: str) -> bool:
    return (response.status_code, response.headers.get("location")) == (303, location)


# The menu and the page


def test_the_menu_has_transfers(home: TestClient) -> None:
    html = home.get("/transfers").text
    assert 'href="/transfers" aria-current="page">Transfers</a>' in html
    assert html.count('aria-current="page"') == 1
    assert 'href="/transfers">Transfers</a>' in home.get("/categories").text
    assert "<script" not in html


def test_a_database_that_is_not_migrated(client: TestClient) -> None:
    response = client.get("/transfers")
    assert response.status_code == 503
    assert ("error", NOT_MIGRATED) in Page(response.text).paragraphs


def test_the_page_before_finding(home: TestClient) -> None:
    found = page(home, "/transfers")
    assert ("hint", HINT) in found.paragraphs
    assert found.rows == [
        REVIEW,
        [
            "3",
            "2026-05-05",
            "Test Checking",
            "4",
            "2026-05-05",
            "Test Savings",
            "$20.00",
            "Transfer Not a transfer",
        ],
        [
            "3",
            "2026-05-05",
            "Test Checking",
            "5",
            "2026-05-06",
            "Test Savings",
            "$20.00",
            "Transfer Not a transfer",
        ],
    ]
    assert ("empty", "No transfers.") in found.paragraphs
    assert [form["inputs"]["in"] for form in found.all("/transfers/confirm")] == [
        ("hidden", "4"),
        ("hidden", "5"),
    ]
    assert [form["inputs"]["out"] for form in found.all("/transfers/reject")] == [
        ("hidden", "3"),
        ("hidden", "3"),
    ]
    assert found.links.count("/transactions/3") == 2
    assert "/transactions/4" in found.links and "/transactions/5" in found.links


def test_every_form_carries_the_token(found: TestClient) -> None:
    for path in ("/transfers", "/transactions/2"):
        forms = [form for form in page(found, path).forms if form["method"] == "post"]
        assert forms
        assert all(
            form["inputs"]["csrf"] == ("hidden", found.cookies["fin_csrf"]) for form in forms
        )


@pytest.mark.parametrize("path", POSTS)
def test_a_form_without_the_token_is_refused(home: TestClient, path: str) -> None:
    response = home.post(path, data={}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")
    assert home.get(path).status_code == 405


# The forms


def test_find_transfers(home: TestClient) -> None:
    response = post(home, "/transfers/find")
    assert redirected(response, "/transfers?notice=transfers-found")
    found = page(home, response.headers["location"])
    assert ("notice", "Clear transfers were paired; the rest wait for review.") in found.paragraphs
    assert found.rows[3:] == [
        PAIRS,
        ["1", "2026-05-03", "Test Checking", "Test Card", "$500.00", "1", "2", "auto", "Unpair"],
    ]
    assert found.find("/transfers/unpair")["inputs"]["pair"] == ("hidden", "1")


def test_confirm_a_transfer(found: TestClient) -> None:
    response = post(found, "/transfers/confirm", out="3", **{"in": "5"})
    assert redirected(response, "/transfers?notice=transfer-confirmed")
    shown = page(found, response.headers["location"])
    assert ("notice", "Transfer saved.") in shown.paragraphs
    assert ("empty", "No transfers wait for review.") in shown.paragraphs
    assert shown.rows == [
        PAIRS,
        [
            "2",
            "2026-05-05",
            "Test Checking",
            "Test Savings",
            "$20.00",
            "3",
            "5",
            "confirmed",
            "Unpair",
        ],
        ["1", "2026-05-03", "Test Checking", "Test Card", "$500.00", "1", "2", "auto", "Unpair"],
    ]


def test_reject_a_choice(home: TestClient) -> None:
    response = post(home, "/transfers/reject", out="3", **{"in": "4"})
    assert redirected(response, "/transfers?notice=transfer-rejected")
    shown = page(home, response.headers["location"])
    assert ("notice", "Those two will not be paired.") in shown.paragraphs
    assert ("empty", "No transfers wait for review.") in shown.paragraphs
    post(home, "/transfers/find")
    assert [row[0] for row in page(home, "/transfers").rows] == ["Pair", "2", "1"]


def test_unpair_on_the_transfers_page(found: TestClient) -> None:
    response = post(found, "/transfers/unpair", pair="1")
    assert redirected(response, "/transfers?notice=transfer-removed")
    shown = page(found, response.headers["location"])
    assert (
        "notice",
        "Transfer removed; those two will not be paired again.",
    ) in shown.paragraphs
    assert ("empty", "No transfers.") in shown.paragraphs
    post(found, "/transfers/find")
    assert ("empty", "No transfers.") in page(found, "/transfers").paragraphs


# A transaction's page


def test_a_paired_transaction_shows_its_transfer(found: TestClient) -> None:
    for transaction_id in ("1", "2"):
        shown = page(found, f"/transactions/{transaction_id}")
        assert (
            "",
            "Pair 1 (auto): $500.00 from Test Checking (transaction 1)"
            " to Test Card (transaction 2).",
        ) in shown.paragraphs
        assert shown.find("/transfers/unpair")["inputs"]["back"] == ("hidden", transaction_id)
    shown = page(found, "/transactions/3")
    assert shown.all("/transfers/unpair") == []
    assert not any(text.startswith("Pair ") for _, text in shown.paragraphs)


def test_unpair_on_a_transaction_page_returns_to_it(found: TestClient) -> None:
    response = post(found, "/transfers/unpair", pair="1", back="2")
    assert redirected(response, "/transactions/2?notice=transfer-removed")
    assert page(found, "/transactions/2").all("/transfers/unpair") == []


# Refusals


@pytest.mark.parametrize(
    ("path", "fields", "message"),
    [
        ("/transfers/confirm", {"out": "abc", "in": "2"}, "transaction not found"),
        ("/transfers/confirm", {"out": "99", "in": "2"}, "transaction not found"),
        (
            "/transfers/confirm",
            {"out": "1", "in": "3"},
            "a transfer goes from one account to another",
        ),
        (
            "/transfers/confirm",
            {"out": "6", "in": "4"},
            "a transfer pairs money out with the same amount in",
        ),
        ("/transfers/confirm", {"out": "1", "in": "2"}, "transaction 1 is already in a transfer"),
        (
            "/transfers/reject",
            {"out": "2", "in": "1"},
            "a transfer pairs money out with the same amount in",
        ),
        ("/transfers/reject", {"in": "1"}, "transaction not found"),
        ("/transfers/unpair", {"pair": "x"}, "transfer not found"),
        ("/transfers/unpair", {"pair": "9", "back": "2"}, "transfer not found"),
    ],
)
def test_a_refused_form(found: TestClient, path: str, fields: dict, message: str) -> None:
    response = post(found, path, **fields)
    assert response.status_code == 400
    shown = Page(response.text)
    assert ("error", message) in shown.paragraphs
    assert "<h1>Transfers</h1>" in response.text
    assert [
        "1",
        "2026-05-03",
        "Test Checking",
        "Test Card",
        "$500.00",
        "1",
        "2",
        "auto",
        "Unpair",
    ] in shown.rows
