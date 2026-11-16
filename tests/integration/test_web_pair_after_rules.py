from datetime import date

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_alias,
    create_account,
    create_rule,
    find_transfer_pair,
    list_transfer_pairs,
    set_category_by_hand,
)
from finances.web.app import create_app
from tests.support import WEB_PORT, post


@pytest.mark.parametrize(
    ("case", "path", "fields", "location"),
    [
        (
            "add",
            "/categories/rules/add",
            {"pattern": "NEW", "match": "contains", "priority": "0", "category": "Groceries"},
            "/categories?notice=rule-added",
        ),
        (
            "edit",
            "/categories/rules/1",
            {"pattern": "NEW", "match": "contains", "priority": "0", "category": "Groceries"},
            "/categories?notice=rule-changed",
        ),
        ("delete", "/categories/rules/delete", {"rule": "1"}, "/categories?notice=rule-deleted"),
        (
            "alias_add",
            "/categories/aliases/add",
            {"source": "FIRST", "target": "SECOND"},
            "/categories?notice=merchant-merged",
        ),
        (
            "alias_delete",
            "/categories/aliases/delete",
            {"source": "FIRST"},
            "/categories?notice=merchant-unmerged",
        ),
        (
            "bulk",
            "/transactions/bulk",
            {"id": "1", "action": "clear"},
            "/transactions?notice=bulk-cleared",
        ),
        ("clear", "/transactions/1/category/clear", {}, "/transactions/1?notice=category-cleared"),
    ],
    ids=[
        "rule-add",
        "rule-edit",
        "rule-delete",
        "alias-add",
        "alias-delete",
        "bulk-clear",
        "single-clear",
    ],
)
def test_action_pairs_waiting_transfer(
    tmp_settings: Settings, case: str, path: str, fields: dict[str, str], location: str
) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        for number, (name, cents) in enumerate(
            (("Test Checking", -12345), ("Test Savings", 12345)), start=1
        ):
            account = create_account(session, name, "Test Bank", "checking")
            session.add(
                TransactionRow(
                    account_id=account.id,
                    posted_date=date(2026, 5, 10),
                    amount_cents=cents,
                    description="SYNTHETIC TRANSFER",
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        if case in ("edit", "delete"):
            create_rule(session, "OLD", "Groceries")
        if case == "alias_delete":
            add_alias(session, "FIRST", "SECOND")
        if case in ("bulk", "clear"):
            set_category_by_hand(session, 1, "Groceries")
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/categories")
    response = post(client, path, **fields)
    assert (response.status_code, response.headers.get("location")) == (303, location)
    with session_scope(engine) as session:
        assert find_transfer_pair(session, 1) is not None
        assert len(list_transfer_pairs(session)) == 1
    engine.dispose()
