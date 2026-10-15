from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.categorize.transfers import pair_transfers
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_person, create_rule, set_account_owner
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, texts

HEADINGS = ["Date", "Account", "Description", "Category", "Amount", "Card", "Section", "Person"]
MAY = "from=2026-05-01&to=2026-05-31"
SNACK_DAYS = [
    "2026-05-08",
    "2026-05-07",
    "2026-05-06",
    "2026-05-05",
    "2026-05-04",
    "2026-05-03",
    "2026-05-02",
    "2026-05-01",
]
KINDS = "kind must be one of: spending, income, transfer, unsorted_in, pending"


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """The data of tests/e2e/test_cli_spending.py (transactions 1 to 12), plus eight snacks
    from checking on 1 to 8 May (13 to 20). Rules run and transfers are paired."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        card = create_account(session, "Test Card", "Example Card Co", "credit_card")
        pat = create_person(session, "Pat Example")
        set_account_owner(session, card.id, pat.id)
        rows = [
            # account, posted, bought, cents, description, card digits, pending
            (card, date(2026, 5, 2), None, -450, "SQ *ACME COFFEE", "1111", False),
            (card, date(2026, 5, 3), None, -2599, "FOOBAR GROCERY #77", "1111", False),
            (card, date(2026, 5, 10), None, 599, "FOOBAR GROCERY #77", "1111", False),
            (card, date(2026, 6, 1), date(2026, 5, 31), -1250, "ACME COFFEE #12", None, False),
            (card, date(2026, 5, 1), date(2026, 4, 30), -800, "BAZ BOOKS", None, False),
            (checking, date(2026, 5, 20), None, -50000, "PAYMENT TO TEST CARD", None, False),
            (card, date(2026, 5, 21), None, 50000, "PAYMENT THANK YOU", None, False),
            (checking, date(2026, 5, 15), None, 300000, "PAYCHECK EXAMPLE CORP", None, False),
            (checking, date(2026, 5, 16), None, 2500, "VENMO CASHOUT", None, False),
            (card, date(2026, 5, 18), None, -999, "QUUX STREAMING", None, True),
            (checking, date(2026, 5, 25), None, -12000, "ACME UTILITY", None, False),
            (card, date(2026, 5, 12), None, -1500, "BAZ BOOKS", None, False),
        ] + [
            (checking, date(2026, 5, day), None, -300, "QUUX SNACKS", None, False)
            for day in range(1, 9)
        ]
        for number, (account, posted, bought, cents, description, last4, pending) in enumerate(
            rows, start=1
        ):
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=posted,
                    transaction_date=bought,
                    amount_cents=cents,
                    description=description,
                    card_last4=last4,
                    is_pending=pending,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for pattern, category in (
            ("ACME COFFEE", "Coffee & Dessert"),
            ("FOOBAR GROCERY", "Groceries"),
            ("PAYCHECK", "Paycheck"),
            ("ACME UTILITY", "Utilities & Internet"),
            ("QUUX SNACKS", "Groceries"),
        ):
            create_rule(session, pattern, category)
        categorize(session)
        pair_transfers(session)
    engine.dispose()
    return client


def days(client: TestClient, query: str) -> list[str]:
    return [row[0] for row in page(client, f"/transactions?{query}").rows[1:]]


def links(found: Page) -> list[str]:
    return [link for link in found.links if link.startswith("/transactions?")]


# The Transactions page


def test_the_category_column_and_the_filters(home: TestClient) -> None:
    found = page(home, "/transactions?text=acme")
    assert found.rows == [
        HEADINGS,
        [
            "2026-06-01",
            "Test Card",
            "ACME COFFEE #12",
            "Coffee & Dessert",
            "-$12.50",
            "",
            "",
            "Pat Example",
        ],
        [
            "2026-05-25",
            "Test Checking",
            "ACME UTILITY",
            "Utilities & Internet",
            "-$120.00",
            "",
            "",
            "",
        ],
        [
            "2026-05-02",
            "Test Card",
            "SQ *ACME COFFEE",
            "Coffee & Dessert",
            "-$4.50",
            "••1111",
            "",
            "Pat Example",
        ],
    ]
    form = found.find("/transactions")
    assert form["inputs"]["text"] == ("search", "acme")
    assert form["inputs"]["merchant"] == ("text", "")
    options = form["selects"]["category"]
    assert options[:2] == [("", True), ("Uncategorized", False)]
    assert ("Coffee & Dessert", False) in options and ("Food", False) not in options
    assert len(options) == 36


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("kind=transfer", ["2026-05-21", "2026-05-20"]),
        ("kind=income", ["2026-05-15"]),
        ("kind=unsorted_in", ["2026-05-16"]),
        ("kind=pending", ["2026-05-18"]),
        ("merchant=foobar+grocery", ["2026-05-10", "2026-05-03"]),
        ("merchant=acme", []),
        ("card=1111", ["2026-05-10", "2026-05-03", "2026-05-02"]),
        (
            "category=uncategorized",
            ["2026-05-21", "2026-05-20", "2026-05-18", "2026-05-16", "2026-05-12", "2026-05-01"],
        ),
        ("bank=test+bank&text=payment", ["2026-05-20"]),
        (
            "group=Food&kind=spending&from=2026-05-02&to=2026-05-12",
            [
                "2026-05-10",
                "2026-05-08",
                "2026-05-07",
                "2026-05-06",
                "2026-05-05",
                "2026-05-04",
                "2026-05-03",
                "2026-05-03",
                "2026-05-02",
                "2026-05-02",
            ],
        ),
        ("from=2026-05-31&to=2026-05-31", ["2026-06-01"]),
        ("from=2026-04-30&to=2026-04-30", ["2026-05-01"]),
        ("person=unassigned&kind=spending&limit=2", ["2026-05-25", "2026-05-08"]),
        ("text=SNACKS&account=test+checking", SNACK_DAYS),
    ],
)
def test_filters(home: TestClient, query: str, expected: list[str]) -> None:
    assert days(home, query) == expected


def test_link_filters_are_kept_and_named(home: TestClient) -> None:
    found = page(home, "/transactions?group=Food&bank=Example+Card+Co&card=&kind=spending")
    form = found.find("/transactions")
    assert form["inputs"]["group"] == ("hidden", "Food")
    assert form["inputs"]["bank"] == ("hidden", "Example Card Co")
    assert form["inputs"]["kind"] == ("hidden", "spending")
    assert "card" not in form["inputs"]
    assert texts(found, "hint") == [
        "Also filtered by: group Food, bank Example Card Co, kind spending. Clear all filters"
    ]
    assert "/transactions" in found.links
    assert texts(page(home, "/transactions"), "hint") == []


@pytest.mark.parametrize("kind", ["spend", "SPENDING ", "all"])
def test_a_kind_that_is_not_one(home: TestClient, kind: str) -> None:
    response = home.get(f"/transactions?kind={kind}")
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", KINDS) in found.paragraphs
    assert found.rows == []
    assert found.find("/transactions")["inputs"]["kind"] == ("hidden", kind)


# Drilling down


def test_a_spending_line_opens_its_transactions(home: TestClient) -> None:
    found = page(home, "/reports?month=2026-05")
    assert links(found) == [
        f"/transactions?{MAY}&category=Utilities%20%26%20Internet&kind=spending&limit=1000",
        f"/transactions?{MAY}&category=Groceries&kind=spending&limit=1000",
        f"/transactions?{MAY}&category=Coffee%20%26%20Dessert&kind=spending&limit=1000",
        f"/transactions?{MAY}&category=Uncategorized&kind=spending&limit=1000",
    ]
    shown = page(home, links(found)[2])
    assert [(row[0], row[2]) for row in shown.rows[1:]] == [
        ("2026-06-01", "ACME COFFEE #12"),
        ("2026-05-02", "SQ *ACME COFFEE"),
    ]
    assert days(home, links(found)[3].removeprefix("/transactions?")) == ["2026-05-12"]


@pytest.mark.parametrize(
    "by", ["category", "group", "merchant", "person", "account", "bank", "card"]
)
def test_every_line_opens_exactly_its_transactions(home: TestClient, by: str) -> None:
    found = page(home, f"/reports?month=2026-05&by={by}")
    spending = found.rows[found.rows.index([by.capitalize(), "Spent", "Count"]) + 1 :]
    assert len(links(found)) == len(spending) > 0
    for link, row in zip(links(found), spending, strict=True):
        assert len(page(home, link).rows) - 1 == int(row[2]), (link, row)


def test_insights_open_their_transactions(home: TestClient) -> None:
    found = page(home, "/insights?month=2026-05")
    assert f"/transactions?{MAY}&merchant=QUUX%20SNACKS&kind=spending&limit=1000" in links(found)
    assert f"/transactions?{MAY}&merchant=ACME%20COFFEE&kind=spending&limit=1000" in links(found)
    finding = Page(home.get("/insights?month=2026-05").text).rows[1]
    assert finding[:3] == ["low", "frequent_small", "QUUX SNACKS"]
    assert links(found)[0] == f"/transactions?{MAY}&merchant=QUUX%20SNACKS&kind=spending&limit=1000"
    assert days(home, links(found)[0].removeprefix("/transactions?")) == SNACK_DAYS
