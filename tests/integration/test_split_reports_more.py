from collections.abc import Iterator
from datetime import date

import anyio
import pytest
from fastapi.testclient import TestClient
from mcp.client import Client
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.account_page import account_page
from finances.analysis.budgets import budget_report
from finances.analysis.insights import insights_report
from finances.analysis.months import month_report
from finances.analysis.recurring import recurring_charges
from finances.analysis.search import TransactionQuery, search_transactions
from finances.analysis.spending import load_flows
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    set_budget,
    set_category_by_hand,
    set_split,
    split_by_sizes,
)
from finances.domain.spending import TRANSFER, SpendingLine
from finances.mcp_server.server import build_server
from finances.web.app import create_app
from tests.support import WEB_PORT, page

FIRST, LAST = date(2026, 5, 1), date(2026, 5, 31)


def _row(
    session: Session,
    account_id: int,
    day: date,
    cents: int,
    description: str,
    number: int,
    *,
    pending: bool = False,
) -> None:
    session.add(
        TransactionRow(
            account_id=account_id,
            posted_date=day,
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


def test_month_report_counts_spent_without_the_transfer_part(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    _row(session, 1, date(2026, 5, 3), -2000, "FOOBAR GROCERY", 1)
    session.flush()
    set_split(session, 1, [(-1200, "Groceries"), (-800, "Transfer")])
    parts = load_flows(session, FIRST, LAST, parts=True)
    assert [(flow.amount_cents, flow.category, flow.kind) for flow in parts] == [
        (-1200, "Groceries", "spending"),
        (-800, "Transfer", TRANSFER),
    ]
    assert month_report(session, LAST, 1)[0].spent_cents == 1200


def test_a_groceries_budget_counts_the_part(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    _row(session, 1, date(2026, 5, 3), -2000, "FOOBAR GROCERY", 1)
    session.flush()
    set_split(session, 1, [(-1200, "Groceries"), (-800, "Home & Garden")])
    set_budget(session, "Groceries", 5000)
    found = {line.name: line.spent_cents for line in budget_report(session, FIRST, LAST)}
    assert found["Groceries"] == 1200


def test_the_account_page_spending_shows_the_parts(session: Session) -> None:
    account = create_account(session, "Test Card", "Test Bank", "credit_card")
    _row(session, account.id, date(2026, 5, 3), -2000, "FOOBAR GROCERY", 1)
    session.flush()
    set_split(session, 1, [(-1200, "Groceries"), (-800, "Home & Garden")])
    found = account_page(session, account, "", FIRST, LAST, date(2026, 5, 25))
    assert found.spending == [SpendingLine("Food", 1200, 1, 0), SpendingLine("Home", 800, 1, 0)]


def test_spikes_see_a_groceries_part(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    for number, month in enumerate((2, 3, 4), start=1):
        _row(session, 1, date(2026, month, 5), -10000, "FOOBAR GROCERY", number)
    _row(session, 1, date(2026, 5, 5), -20000, "FOOBAR GROCERY", 4)
    session.flush()
    for number in (1, 2, 3):
        set_category_by_hand(session, number, "Groceries")
    set_split(session, 4, [(-15000, "Groceries"), (-5000, "Home & Garden")])
    report = insights_report(session, FIRST)
    spikes = [item for item in report.findings if item.type == "spike"]
    assert [(item.subject, item.savings_cents) for item in spikes] == [("Groceries", 5000)]


def test_merchant_stats_count_a_split_purchase_once(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    _row(session, 1, date(2026, 5, 3), -2000, "FOOBAR GROCERY", 1)
    session.flush()
    set_split(session, 1, [(-1200, "Groceries"), (-800, "Home & Garden")])
    stats = {item.merchant: item.visits for item in insights_report(session, FIRST).merchants}
    assert stats["FOOBAR GROCERY"] == 1


def test_recurring_charges_keep_the_whole_streamflix_amount(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    for number, month in enumerate((2, 3, 4, 5), start=1):
        _row(session, 1, date(2026, month, 5), -1500, "STREAMFLIX", number)
    session.flush()
    set_split(session, 4, [(-1000, "Subscriptions & Digital"), (-500, "Entertainment & Events")])
    found = recurring_charges(session, LAST)
    assert [(item.merchant, item.amount_cents, item.count) for item in found] == [
        ("STREAMFLIX", 1500, 4)
    ]


def test_search_matches_a_part_kind_and_limit_counts_parts(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    _row(session, 1, date(2026, 5, 3), -2000, "FOOBAR GROCERY", 1)
    session.flush()
    set_split(session, 1, [(-1200, "Groceries"), (-500, "Transfer"), (-300, "Dining")])
    found = search_transactions(session, TransactionQuery(kind="transfer"))
    assert [(item.transaction.id, item.flow.amount_cents, item.flow.kind) for item in found] == [
        (1, -500, TRANSFER)
    ]
    limited = search_transactions(session, TransactionQuery(limit=2))
    assert [(item.flow.amount_cents, item.flow.category) for item in limited] == [
        (-1200, "Groceries"),
        (-500, "Transfer"),
    ]


def test_split_by_sizes_refuses_not_found_before_a_size(session: Session) -> None:
    with pytest.raises(ValueError) as raised:
        split_by_sizes(session, 9, [(0, "Dining"), (100, "Groceries")])
    assert str(raised.value) == "transaction not found"


def test_split_by_sizes_refuses_pending_before_the_sum(session: Session) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    _row(session, 1, date(2026, 5, 3), -2000, "FOOBAR GROCERY", 1, pending=True)
    session.flush()
    with pytest.raises(ValueError) as raised:
        split_by_sizes(session, 1, [(1200, "Dining"), (100, "Groceries")])
    assert str(raised.value) == "a pending transaction cannot be split"


@pytest.fixture
def split_card(tmp_settings: Settings) -> Settings:
    """-$20.00 at FOOBAR GROCERY (1) split into Groceries -$12.00 and Home & Garden -$8.00."""
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        _row(session, 1, date(2026, 5, 3), -2000, "FOOBAR GROCERY", 1)
        session.flush()
        set_split(session, 1, [(-1200, "Groceries"), (-800, "Home & Garden")])
    engine.dispose()
    return tmp_settings


def test_list_transactions_gives_each_part_amount(split_card: Settings) -> None:
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool("list_transactions")

    result = anyio.run(go)
    found = result.structured_content["transactions"]
    assert [(item["id"], item["amount_cents"]) for item in found] == [(1, -1200), (1, -800)]


def test_the_transactions_page_shows_the_parts_amounts(split_card: Settings) -> None:
    client = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    amounts = [row[4] for row in page(client, "/transactions").rows[1:]]
    assert amounts == ["-$12.00", "-$8.00"]
