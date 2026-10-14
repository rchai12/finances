import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from finances.categorize.service import CategorizeResult, categorize
from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_rule,
    delete_rule,
    get_category_by_name,
    list_category_assignments,
    map_feed_account,
    set_category_by_hand,
)
from finances.domain.models import BY_RULE, MANUAL, CategoryAssignment
from finances.ingest.service import ImportStatus, import_statement
from finances.sync import transport
from finances.sync.feed import AccountFeed, FeedTransaction
from finances.sync.service import apply_feed


@pytest.fixture
def session(db_engine: Engine, fake_bank) -> Iterator[Session]:
    """A migrated database with the fake bank's card (id 1) and no transactions."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Fake Bank", "credit_card", last4="1111")
        yield opened


def add_transaction(session: Session, day: int, description: str) -> int:
    row = TransactionRow(
        account_id=1,
        posted_date=date(2026, 5, day),
        amount_cents=-100,
        description=description,
        source="statement",
        fingerprint=f"{description}{day}".ljust(64, "0")[:64],
    )
    session.add(row)
    session.flush()
    return row.id


def category_id(session: Session, name: str) -> int:
    found = get_category_by_name(session, name)
    assert found is not None
    return found.id


def categories(session: Session) -> dict[int, int]:
    return {key: item.category_id for key, item in list_category_assignments(session).items()}


def test_an_empty_ledger(session: Session) -> None:
    assert categorize(session) == CategorizeResult(0, 0, 0)


def test_the_counts(session: Session) -> None:
    coffee = add_transaction(session, 1, "SQ *ACME COFFEE")
    grocery = add_transaction(session, 2, "FOOBAR GROCERY #77 DECATUR GA")
    stranger = add_transaction(session, 3, "STRANGER")
    by_hand = add_transaction(session, 4, "TEA HOUSE")
    set_category_by_hand(session, by_hand, "Coffee & Dessert")
    first = create_rule(session, "ACME", "Dining")
    assert categorize(session) == CategorizeResult(4, 1, 2)
    closer = create_rule(session, "ACME COFFEE", "Dining", "equals", priority=5)
    create_rule(session, "FOOBAR GROCERY", "Groceries")
    assert categorize(session) == CategorizeResult(4, 1, 1)
    assignments = list_category_assignments(session)
    assert assignments[coffee] == CategoryAssignment(coffee, first.category_id, BY_RULE, closer.id)
    assert assignments[grocery].category_id == category_id(session, "Groceries")
    assert stranger not in assignments


def test_a_category_set_by_hand_is_never_overwritten(session: Session) -> None:
    item = add_transaction(session, 1, "ACME COFFEE")
    chosen = set_category_by_hand(session, item, "Groceries")
    create_rule(session, "ACME COFFEE", "Dining", priority=99)
    assert categorize(session) == CategorizeResult(1, 0, 0)
    assert list_category_assignments(session) == {
        item: CategoryAssignment(item, chosen.id, MANUAL, None)
    }


def test_a_deleted_rule_hands_over_to_the_next_rule_or_to_none(session: Session) -> None:
    coffee = add_transaction(session, 1, "ACME COFFEE")
    tea = add_transaction(session, 2, "ACME TEA")
    broad = create_rule(session, "ACME", "Dining", priority=5)
    create_rule(session, "COFFEE", "Coffee & Dessert")
    assert categorize(session) == CategorizeResult(2, 2, 0)
    delete_rule(session, broad.id)
    assert categorize(session) == CategorizeResult(2, 1, 1)
    assert categories(session) == {coffee: category_id(session, "Coffee & Dessert")}
    assert tea not in categories(session)


def test_a_rule_that_no_longer_matches_lets_go(session: Session) -> None:
    item = add_transaction(session, 1, "ACME COFFEE")
    create_rule(session, "ACME", "Dining")
    categorize(session)
    session.get(TransactionRow, item).description = "FOOBAR DINER"
    assert categorize(session) == CategorizeResult(1, 1, 1)
    assert categories(session) == {}


def test_running_twice_changes_nothing(session: Session) -> None:
    for day, text in ((1, "ACME COFFEE"), (2, "FOOBAR GROCERY"), (3, "STRANGER")):
        add_transaction(session, day, text)
    create_rule(session, "ACME", "Dining")
    create_rule(session, "FOOBAR", "Groceries")
    first = categorize(session)
    before = list_category_assignments(session)
    assert categorize(session) == CategorizeResult(first.total, 0, first.uncategorized)
    assert list_category_assignments(session) == before


def may(day: int) -> date:
    return date(2026, 5, day)


def test_categorized_feed_rows_survive_a_statement(session: Session, fake_statement_pdf) -> None:
    apply_feed(
        session,
        1,
        AccountFeed(
            [
                FeedTransaction("f-coffee", may(3), -450, "ACME COFFEE"),
                FeedTransaction("f-wrong-amount", may(8), -2600, "FOOBAR GROCERY"),
                FeedTransaction("f-unknown", may(15), -999, "NOT ON THE STATEMENT"),
            ],
            [],
        ),
    )
    create_rule(session, "ACME", "Coffee & Dessert")
    create_rule(session, "FOOBAR", "Groceries")
    create_rule(session, "NOT ON", "Dining")
    assert categorize(session) == CategorizeResult(3, 3, 0)
    content = fake_statement_pdf(
        start="2026-05-01",
        end="2026-05-31",
        opening="-100.00",
        closing="-80.49",
        rows=(
            "2026-05-03|-|purchases|-4.50|-|-|ACME COFFEE #12",
            "2026-05-08|-|purchases|-25.99|-|-|FOOBAR GROCERY",
            "2026-05-20|-|payments_credits|50.00|-|-|PAYMENT THANK YOU",
        ),
    )
    result = import_statement(session, filename="may.pdf", content=content)
    assert result.status is ImportStatus.IMPORTED
    assert (result.inserted, result.upgraded, result.dropped) == (2, 1, 2)
    assert categories(session) == {1: category_id(session, "Coffee & Dessert")}
    assert categorize(session) == CategorizeResult(3, 1, 1)


def test_a_sync_categorizes_quietly(
    tmp_settings: Settings, keychain, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = CliRunner(env={"COLUMNS": "200"})
    assert runner.invoke(app, ["db", "upgrade"]).exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        map_feed_account(session, card.id, "ACT-1", "alex")
        create_rule(session, "ACME", "Dining")
    keychain.passwords[("finances-simplefin", "alex")] = (
        "https://probe-user:probe-pass@bridge.simplefin.org/simplefin"
    )
    yesterday = int((datetime.now(UTC) - timedelta(days=1)).timestamp())
    body = {
        "errlist": [],
        "connections": [{"conn_id": "C-1", "name": "Probe Bank", "org_id": "O", "sfin_url": "x"}],
        "accounts": [
            {
                "id": "ACT-1",
                "name": "Probe Card",
                "conn_id": "C-1",
                "currency": "USD",
                "balance": "-4.50",
                "balance-date": yesterday,
                "transactions": [
                    {"id": "T-1", "posted": yesterday, "amount": "-4.50", "description": "SQ *ACME"}
                ],
            }
        ],
    }
    monkeypatch.setattr(
        transport, "urllib_transport", lambda method, url, headers: (200, json.dumps(body).encode())
    )
    result = runner.invoke(app, ["sync", "run"])
    assert result.exit_code == 0
    assert all(line[0] in "┏┃┡│└" for line in result.stdout.splitlines())
    with session_scope(engine) as session:
        assert list(categories(session).values()) == [category_id(session, "Dining")]
    engine.dispose()
