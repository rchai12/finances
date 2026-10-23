from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.categorize.service import categorize, preview_rule
from finances.config import Settings
from finances.db.engine import session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_alias,
    check_rule,
    create_account,
    create_rule,
    get_category_by_name,
    list_category_assignments,
    list_changes,
    list_rules,
    set_category_by_hand,
)
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, post, texts


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        yield opened


def add_card(session: Session, rows: tuple[tuple[date, int, str], ...]) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    for number, (day, cents, description) in enumerate(rows, start=1):
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=day,
                amount_cents=cents,
                description=description,
                source="statement",
                fingerprint=f"p{number:02d}".ljust(64, "0"),
            )
        )
    session.flush()


def test_check_rule_returns_the_normalized_pair(session: Session) -> None:
    pattern, category = check_rule(session, "  acme  coffee ", "dining")
    dining = get_category_by_name(session, "Dining")
    assert dining is not None
    assert (pattern, category) == ("ACME COFFEE", dining)


@pytest.mark.parametrize(
    ("pattern", "category", "match", "message"),
    [
        ("", "Dining", "contains", "a rule pattern must be 1 to 100 characters"),
        ("ACME", "Dining", "like", "match must be one of: contains, starts_with, equals"),
        ("ACME", "Food", "contains", "rules and transactions take a category, not a group"),
    ],
)
def test_check_rule_refuses(
    session: Session, pattern: str, category: str, match: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        check_rule(session, pattern, category, match)


def test_check_rule_refuses_an_existing_rule(session: Session) -> None:
    create_rule(session, "ACME COFFEE", "Dining")
    with pytest.raises(ValueError, match="a rule with this pattern and match already exists"):
        check_rule(session, "acme coffee", "Coffee & Dessert")


def test_a_hand_set_transaction_the_rule_matches_is_not_counted(session: Session) -> None:
    add_card(session, ((date(2026, 5, 1), -450, "ACME CAFE"),))
    set_category_by_hand(session, 1, "Groceries")
    found = preview_rule(session, "ACME", "Dining")
    assert found.changes == 0
    assert found.examples == []


def test_a_winning_rule_that_changes_nothing_is_not_counted(session: Session) -> None:
    add_card(session, ((date(2026, 5, 1), -500, "ACME COFFEE"),))
    create_rule(session, "ACME COFFEE", "Dining")
    categorize(session)
    found = preview_rule(session, "ACME", "Dining", priority=5)
    assert found.changes == 0


def test_an_older_rule_wins_a_tie_and_a_higher_priority_wins(session: Session) -> None:
    add_card(session, ((date(2026, 5, 1), -500, "ACME COFFEE"),))
    create_rule(session, "ACME COFFEE", "Coffee & Dessert")
    categorize(session)
    tied = preview_rule(session, "ACME", "Dining", priority=0)
    assert tied.changes == 0
    wins = preview_rule(session, "ACME", "Dining", priority=1)
    assert wins.changes == 1
    assert wins.examples[0].transaction.id == 1


def test_an_alias_lets_equals_see_the_merged_name(session: Session) -> None:
    add_card(session, ((date(2026, 5, 1), -450, "ACME CAFE"),))
    add_alias(session, "ACME CAFE", "ACME COFFEE")
    found = preview_rule(session, "ACME COFFEE", "Dining", match="equals")
    assert found.changes == 1
    assert found.examples[0].merchant == "ACME COFFEE"


def test_same_day_examples_come_newest_id_first(session: Session) -> None:
    add_card(
        session,
        (
            (date(2026, 5, 1), -450, "ACME CAFE"),
            (date(2026, 5, 1), -500, "ACME CAFE"),
        ),
    )
    found = preview_rule(session, "ACME", "Dining")
    assert [item.transaction.id for item in found.examples] == [2, 1]


def test_a_preview_writes_nothing_and_matches_categorize(session: Session) -> None:
    add_card(session, ((date(2026, 5, 1), -450, "ACME CAFE"),))
    before_rules = list_rules(session)
    before_audit = [
        (item.action, item.kind, item.record_id, item.before, item.after)
        for item in list_changes(session)
    ]
    before_held = list_category_assignments(session)
    found = preview_rule(session, "ACME", "Dining")
    assert found.changes == 1
    assert list_rules(session) == before_rules
    assert [
        (item.action, item.kind, item.record_id, item.before, item.after)
        for item in list_changes(session)
    ] == before_audit
    assert list_category_assignments(session) == before_held
    create_rule(session, "ACME", "Dining")
    result = categorize(session)
    assert result.changed == found.changes


def test_a_preview_with_a_bad_priority_is_refused(tmp_settings: Settings) -> None:
    upgrade_to_head()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/categories")
    response = post(
        client,
        "/categories/rules/preview",
        pattern="acme",
        match="contains",
        priority="x",
        category="Dining",
    )
    assert response.status_code == 400
    found = Page(response.text)
    assert texts(found, "error") == ["priority must be a whole number"]
    assert texts(found, "preview") == []


@pytest.mark.parametrize(
    "path",
    ["/categories/aliases/add", "/categories/aliases/delete", "/categories/rules/preview"],
)
def test_a_new_form_without_the_token_is_refused(tmp_settings: Settings, path: str) -> None:
    upgrade_to_head()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/categories")
    response = client.post(path, data={}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")
