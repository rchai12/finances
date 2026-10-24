from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.search import TransactionQuery, search_transactions
from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_rule, set_category_by_hand, set_split
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, page, post, texts

PATHS = ("/transactions/1/split", "/transactions/1/split/clear")
PART_HEADINGS = ["Part", "Amount", "Category"]


def _row(
    session: Session, cents: int, description: str, number: int, *, pending: bool = False
) -> None:
    session.add(
        TransactionRow(
            account_id=1,
            posted_date=date(2026, 5, number),
            amount_cents=cents,
            description=description,
            source="statement",
            is_pending=pending,
            fingerprint=f"t{number:02d}".ljust(64, "0"),
        )
    )


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        yield opened


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
            _row(session, cents, description, number)
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


@pytest.mark.parametrize("path", PATHS)
def test_get_on_the_new_paths_is_405(home: TestClient, path: str) -> None:
    assert home.get(path).status_code == 405


def test_a_refused_split_on_a_split_transaction_keeps_the_parts(home: TestClient) -> None:
    response = post(home, "/transactions/3/split", parts="1.00 Dining\n1.00 Groceries")
    found = Page(response.text)
    assert response.status_code == 400
    assert texts(found, "error") == ["the parts must add up to the transaction"]
    assert parts_of(found) == [["1", "-$6.00", "Dining"], ["2", "-$4.00", "Groceries"]]


def test_splitting_a_pending_transaction_is_refused(client: TestClient) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        _row(session, -500, "ACME PENDING", 1, pending=True)
    engine.dispose()
    client.get("/transactions")
    response = post(client, "/transactions/1/split", parts="3.00 Dining\n2.00 Groceries")
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["a pending transaction cannot be split"]


def test_a_part_of_size_zero_is_refused(home: TestClient) -> None:
    response = post(home, "/transactions/1/split", parts="0 Groceries\n20.00 Dining")
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == ["each part's size must be more than zero"]


def test_removing_a_split_puts_the_rule_category_back(home: TestClient) -> None:
    post(home, "/transactions/2/split", parts="3.00 Dining\n2.00 Groceries")
    post(home, "/transactions/2/split/clear")
    found = page(home, "/transactions/2")
    assert ["Category", "Coffee & Dessert"] in found.rows


def test_search_gives_part_numbers_on_a_split(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    _row(session, -450, "ACME COFFEE", 1)
    _row(session, -2000, "FOOBAR GROCERY", 2)
    session.flush()
    set_category_by_hand(session, 1, "Dining")
    set_split(session, 2, [(-1200, "Groceries"), (-800, "Home & Garden")])
    found = search_transactions(session, TransactionQuery())
    assert [(item.transaction.id, item.part) for item in found] == [(2, 1), (2, 2), (1, None)]


def test_a_form_without_a_valid_token_is_refused(home: TestClient) -> None:
    response = home.post(
        "/transactions/1/split",
        data={"parts": "12.00 Groceries\n8.00 Dining"},
        follow_redirects=False,
    )
    assert (response.status_code, response.text) == (403, "Bad form token")
