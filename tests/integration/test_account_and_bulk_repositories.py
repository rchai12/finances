from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    rename_account,
    set_account_active,
    set_categories_by_hand,
)
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, run, table_rows


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        create_account(opened, "Test Checking", "Test Bank", "checking")
        yield opened


def add_transaction(session: Session, account_id: int, day: int, description: str) -> int:
    row = TransactionRow(
        account_id=account_id,
        posted_date=date(2026, 5, day),
        amount_cents=-100,
        description=description,
        source="statement",
        fingerprint=f"{account_id}-{day}-{description}".ljust(64, "0")[:64],
    )
    session.add(row)
    session.flush()
    return row.id


def test_renaming_keeps_a_change_of_its_own_case(session: Session) -> None:
    renamed = rename_account(session, 1, "test card")
    assert renamed.name == "test card"


def test_rename_account_refuses_a_missing_id(session: Session) -> None:
    with pytest.raises(ValueError, match="^account not found$"):
        rename_account(session, 99, "Other")


def test_set_account_active_refuses_a_missing_id(session: Session) -> None:
    with pytest.raises(ValueError, match="^account not found$"):
        set_account_active(session, 99, False)


def test_set_categories_refuses_more_than_a_thousand(session: Session) -> None:
    with pytest.raises(ValueError, match="^at most 1000 transactions at once$"):
        set_categories_by_hand(session, range(1, 1002), "Dining")


def test_set_categories_counts_repeated_ids_once(session: Session) -> None:
    first = add_transaction(session, 1, 1, "ACME COFFEE")
    second = add_transaction(session, 1, 2, "FOOBAR GROCERY")
    count, chosen = set_categories_by_hand(session, [first, second, first], "Dining")
    assert (count, chosen.name) == (2, "Dining")


def test_the_web_refuses_more_than_a_thousand_ids(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from starlette.requests import Request

    original = Request.form

    async def form_with_room(self, *args, max_files=1000, max_fields=1000, **kwargs):
        return await original(self, *args, max_files=max_files, max_fields=2000, **kwargs)

    monkeypatch.setattr(Request, "form", form_with_room)
    upgrade_to_head()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    client.get("/transactions")
    response = client.post(
        "/transactions/bulk",
        data={
            "csrf": client.cookies["fin_csrf"],
            "id": [str(number) for number in range(1, 1002)],
            "category": "Dining",
            "action": "set",
            "back": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert ("error", "at most 1000 transactions at once") in Page(response.text).paragraphs


def test_a_closed_account_leaves_balances_and_still_counts_in_spending(
    tmp_settings: Settings,
) -> None:
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        add_transaction(session, card.id, 1, "ACME COFFEE")
        add_transaction(session, checking.id, 2, "FOOBAR GROCERY")
        set_account_active(session, card.id, False)
    engine.dispose()
    assert run("rules", "add", "--pattern", "ACME", "--category", "Dining").exit_code == 0
    balances = table_rows(run("balances").stdout)
    assert [row[0] for row in balances[1:]] == ["Test Checking"]
    spending = table_rows(run("spending", "--month", "2026-05", "--by", "account").stdout)
    assert ["Test Card", "$1.00", "1"] in spending
    assert ["Test Checking", "$1.00", "1"] in spending
