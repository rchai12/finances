from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.account_page import account_page
from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    create_rule,
    list_balance_snapshots,
    set_account_active,
    set_account_owner,
)
from finances.domain.models import DataSource
from finances.domain.spending import month_bounds
from finances.web.app import create_app
from tests.support import WEB_PORT, Page


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        yield opened


def test_list_balance_snapshots_puts_the_higher_id_first_on_the_same_day(session: Session) -> None:
    account = create_account(session, "Test Card", "Test Bank", "credit_card")
    first = add_balance_snapshot(
        session, account.id, date(2026, 5, 20), -10000, DataSource.STATEMENT
    )
    second = add_balance_snapshot(
        session, account.id, date(2026, 5, 20), -20000, DataSource.AGGREGATOR
    )
    found = list_balance_snapshots(session, account.id)
    assert [item.id for item in found] == [second.id, first.id]
    assert found[0].source is DataSource.AGGREGATOR


def test_closed_joint_and_no_cards_on_the_page(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("finances.web.app._today", lambda: date(2026, 5, 25))
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        closed = create_account(session, "Old Card", "Test Bank", "credit_card")
        joint = create_account(session, "Joint Card", "Test Bank", "credit_card")
        plain = create_account(session, "Plain Card", "Test Bank", "credit_card")
        set_account_active(session, closed.id, False)
        set_account_owner(session, joint.id, None)
        session.add(
            TransactionRow(
                account_id=plain.id,
                posted_date=date(2026, 5, 1),
                amount_cents=-100,
                description="ACME COFFEE",
                source="statement",
                fingerprint="p".ljust(64, "0"),
            )
        )
    engine.dispose()
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    closed_page = Page(client.get("/account?name=Old%20Card").text)
    assert ["Status", "closed"] in closed_page.rows
    joint_page = Page(client.get("/account?name=Joint%20Card").text)
    assert ["Owner", "Joint"] in joint_page.rows
    plain_html = client.get("/account?name=Plain%20Card").text
    assert 'class="cards"' not in plain_html
    assert not any(kind == "cards" for kind, _ in Page(plain_html).paragraphs)


def test_a_month_with_income(session: Session) -> None:
    account = create_account(session, "Test Checking", "Test Bank", "checking")
    create_rule(session, "PAYCHECK", "Paycheck")
    session.add(
        TransactionRow(
            account_id=account.id,
            posted_date=date(2026, 5, 10),
            amount_cents=300000,
            description="PAYCHECK EXAMPLE CORP",
            source="statement",
            fingerprint="i".ljust(64, "0"),
        )
    )
    session.add(
        TransactionRow(
            account_id=account.id,
            posted_date=date(2026, 5, 12),
            amount_cents=500,
            description="FOOBAR GROCERY REFUND",
            source="statement",
            fingerprint="r".ljust(64, "0"),
        )
    )
    session.flush()
    categorize(session)
    start, end = month_bounds(date(2026, 5, 1))
    found = account_page(session, account, "", start, end, date(2026, 5, 25))
    may = next(month for month in found.months if month.start == date(2026, 5, 1))
    assert may.income_cents == 300000
    assert may.spent_cents == 0


def test_a_month_later_than_today_still_loads_its_flows(session: Session) -> None:
    account = create_account(session, "Test Card", "Test Bank", "credit_card")
    create_rule(session, "ACME", "Dining")
    session.add(
        TransactionRow(
            account_id=account.id,
            posted_date=date(2026, 6, 5),
            amount_cents=-900,
            description="ACME COFFEE",
            source="statement",
            fingerprint="j".ljust(64, "0"),
        )
    )
    session.flush()
    categorize(session)
    start, end = month_bounds(date(2026, 6, 1))
    found = account_page(session, account, "", start, end, date(2026, 5, 25))
    assert [(line.label, line.spent_cents, line.count) for line in found.spending] == [
        ("Food", 900, 1)
    ]
