from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.config import Settings
from finances.db.engine import session_scope
from finances.db.orm import CategoryRow, TransactionRow
from finances.db.repositories import (
    clear_categories_by_hand,
    create_account,
    create_person,
    create_rule,
    delete_category,
    edit_rule,
    list_changes,
    rename_category,
    set_account_owner,
    set_categories_by_hand,
)
from finances.domain.audit import PERSON, Change, rule_text
from finances.domain.text import AUDIT_TEXT_LIMIT, fit
from finances.views.audit import change_rows
from tests.support import failed_cleanly, run

NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
MIDNIGHT = datetime(2026, 5, 25, 0, 0, tzinfo=UTC)


@pytest.fixture
def session(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    monkeypatch.setattr("finances.db.repositories.audit._now", lambda: NOON)
    with session_scope(db_engine) as opened:
        yield opened


def add(session: Session, number: int, account: int, cents: int) -> None:
    session.add(
        TransactionRow(
            account_id=account,
            posted_date=date(2026, 5, number),
            amount_cents=cents,
            description="PROBE",
            source="statement",
            fingerprint=f"p{number:02d}".ljust(64, "0"),
        )
    )
    session.flush()


def test_set_and_clear_by_hand_record_one_row_per_transaction(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    add(session, 1, 1, -500)
    add(session, 2, 1, -700)
    set_categories_by_hand(session, [1, 2], "Dining")
    found = [item for item in list_changes(session, limit=1000) if item.action == "category_set"]
    assert [(item.record_id, item.before, item.after) for item in reversed(found)] == [
        (1, None, "Dining"),
        (2, None, "Dining"),
    ]
    count = len(list_changes(session, limit=1000))
    set_categories_by_hand(session, [1, 2], "Dining")
    assert len(list_changes(session, limit=1000)) == count
    clear_categories_by_hand(session, [1, 2])
    cleared = [
        item for item in list_changes(session, limit=1000) if item.action == "category_cleared"
    ]
    assert [(item.record_id, item.before) for item in reversed(cleared)] == [
        (1, "Dining"),
        (2, "Dining"),
    ]
    count = len(list_changes(session, limit=1000))
    clear_categories_by_hand(session, [1, 2])
    assert len(list_changes(session, limit=1000)) == count


def test_deleting_a_group_records_category_deleted(session: Session) -> None:
    row = CategoryRow(
        name="Probe Group", parent_id=None, is_transfer=False, is_income=False, is_sensitive=False
    )
    session.add(row)
    session.flush()
    group_id = row.id
    delete_category(session, "Probe Group")
    found = [
        item for item in list_changes(session, limit=1000) if item.action == "category_deleted"
    ]
    assert [(item.kind, item.record_id, item.before, item.after) for item in found] == [
        ("category", group_id, "Probe Group", None)
    ]


def test_edit_rule_that_changes_nothing_records_nothing(session: Session) -> None:
    create_rule(session, "ACME", "Dining")
    before = len(list_changes(session, limit=1000))
    edit_rule(session, 1)
    assert len(list_changes(session, limit=1000)) == before


def test_a_rule_text_longer_than_200_characters_is_cut(session: Session) -> None:
    rename_category(session, "Dining", "D" * 50)
    priority = -9223372036854775808
    create_rule(session, "A" * 100, "D" * 50, match="starts_with", priority=priority)
    found = [item for item in list_changes(session, limit=1000) if item.action == "rule_added"]
    text = rule_text("starts_with", "A" * 100, "D" * 50, priority)
    assert found[0].after == fit(text, AUDIT_TEXT_LIMIT)
    longer = text + "!"
    assert len(longer) > AUDIT_TEXT_LIMIT
    assert fit(longer, AUDIT_TEXT_LIMIT) == longer[:AUDIT_TEXT_LIMIT]


def test_audit_without_a_migrated_database(tmp_settings: Settings) -> None:
    assert failed_cleanly(run("audit"), "database is not up to date (run: fin db upgrade)")


def test_since_keeps_a_change_at_midnight_utc_that_day(
    db_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("finances.db.repositories.audit._now", lambda: MIDNIGHT)
    with session_scope(db_engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        assert [item.after for item in list_changes(session, since=date(2026, 5, 25))] == [
            "Test Card"
        ]
        assert list_changes(session, since=date(2026, 5, 26)) == []


def test_owner_set_from_joint_records_joint_as_before(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    create_person(session, "Pat Example")
    set_account_owner(session, 1, None)
    set_account_owner(session, 1, 1)
    found = [item for item in list_changes(session, limit=1000) if item.action == "owner_set"]
    assert [(item.before, item.after) for item in reversed(found)] == [
        (None, "Joint"),
        ("Joint", "Pat Example"),
    ]


def test_change_rows_without_a_record_id() -> None:
    change = Change(1, NOON, PERSON, "budget_set", "category", None, None, "$1.00")
    row = change_rows([change])[0]
    assert (row.record, row.before, row.after) == ("category", "", "$1.00")
