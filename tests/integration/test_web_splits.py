from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule, set_split
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts

PART_HEADINGS = ["Part", "Amount", "Category"]


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def home(client: TestClient) -> TestClient:
    """Card: 1 FOOBAR GROCERY -$20.00 with no category, 2 ACME COFFEE -$5.00 put in Coffee &
    Dessert by a rule, 3 BAZ CAFE -$10.00 split into Dining -$6.00 and Groceries -$4.00."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-2000, "FOOBAR GROCERY"), (-500, "ACME COFFEE"), (-1000, "BAZ CAFE")), start=1
        ):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, number),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        create_rule(session, "ACME", "Coffee & Dessert")
        categorize(session)
        set_split(session, 3, [(-600, "Dining"), (-400, "Groceries")])
    engine.dispose()
    client.get("/transactions")
    return client


def parts_of(found: Page) -> list[list[str]]:
    start = found.rows.index(PART_HEADINGS)
    return [row for row in found.rows[start + 1 :] if len(row) == 3]


def test_a_split_transactions_page(home: TestClient) -> None:
    found = page(home, "/transactions/3")
    assert parts_of(found) == [["1", "-$6.00", "Dining"], ["2", "-$4.00", "Groceries"]]
    assert sorted(found.find("/transactions/3/split/clear")["inputs"]) == ["csrf"]
    assert (found.all("/transactions/3/split"), found.all("/transactions/3/category")) == ([], [])


def test_a_page_that_is_not_split(home: TestClient) -> None:
    found = page(home, "/transactions/1")
    assert PART_HEADINGS not in found.rows
    assert sorted(found.find("/transactions/1/split")["inputs"]) == ["csrf"]
    assert len(found.all("/transactions/1/category")) == 1


def test_splitting_on_the_page(home: TestClient) -> None:
    response = post(home, "/transactions/1/split", parts="12.00 groceries\n$8 Home & Garden")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/transactions/1?notice=split-saved",
    )
    found = page(home, "/transactions/1?notice=split-saved")
    assert texts(found, "notice") == ["Split saved."]
    assert parts_of(found) == [["1", "-$12.00", "Groceries"], ["2", "-$8.00", "Home & Garden"]]


def test_a_refused_split_keeps_what_was_typed(home: TestClient) -> None:
    response = post(home, "/transactions/1/split", parts="12.00 Groceries\n9.00 Dining")
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["the parts must add up to the transaction"]
    assert ">12.00 Groceries\n9.00 Dining</textarea>" in response.text


def test_removing_the_split(home: TestClient) -> None:
    response = post(home, "/transactions/3/split/clear")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/transactions/3?notice=split-removed",
    )
    found = page(home, "/transactions/3?notice=split-removed")
    assert texts(found, "notice") == ["Split removed, and the rules were run again."]
    assert len(found.all("/transactions/3/split")) == 1


@pytest.mark.parametrize(
    ("path", "fields", "status", "message"),
    [
        ("/transactions/1/split/clear", {}, 400, "the transaction is not split"),
        (
            "/transactions/99/split",
            {"parts": "1.00 Dining\n1.00 Dining"},
            404,
            "transaction not found",
        ),
    ],
)
def test_a_refused_form(
    home: TestClient, path: str, fields: dict, status: int, message: str
) -> None:
    response = post(home, path, **fields)
    assert response.status_code == status
    assert texts(Page(response.text), "error") == [message]


def test_parts_on_the_transactions_page(home: TestClient) -> None:
    found = page(home, "/transactions")
    assert [(row[2], row[3], row[4]) for row in found.rows[1:]] == [
        ("BAZ CAFE", "Dining part 1", "-$6.00"),
        ("BAZ CAFE", "Groceries part 2", "-$4.00"),
        ("ACME COFFEE", "Coffee & Dessert", "-$5.00"),
        ("FOOBAR GROCERY", "", "-$20.00"),
    ]
