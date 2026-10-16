from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.budgets import budget_report
from finances.categorize.service import categorize
from finances.categorize.transfers import pair_transfers
from finances.config import Settings
from finances.db.engine import session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_rule,
    delete_category,
    get_category_by_name,
    list_budgets,
    list_categories,
    set_budget,
)
from finances.domain.spending import month_bounds
from tests.support import run, table_rows


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        yield opened


def test_set_budget_replaces_and_accepts_the_amount_edges(session: Session) -> None:
    name, first = set_budget(session, "Dining", 1)
    assert name == "Dining" and first.amount_cents == 1
    _, second = set_budget(session, "dining", 100_000_000)
    assert second.id == first.id and second.amount_cents == 100_000_000
    assert [item.amount_cents for item in list_budgets(session)] == [100_000_000]


def test_deleting_a_group_with_a_budget_and_leaving_a_moved_to_budget(
    session: Session,
) -> None:
    group = get_category_by_name(session, "Subscriptions")
    assert group is not None and group.group_id is None
    for child in [item for item in list_categories(session) if item.group_id == group.id]:
        delete_category(session, child.name)
    set_budget(session, "Subscriptions", 5000)
    set_budget(session, "Dining", 25000)
    set_budget(session, "Groceries", 20000)
    delete_category(session, "Subscriptions")
    delete_category(session, "Groceries", move_to="Dining")
    kept = list_budgets(session)
    assert len(kept) == 1
    dining = get_category_by_name(session, "Dining")
    assert dining is not None
    assert kept[0].category_id == dining.id
    assert kept[0].amount_cents == 25000


def test_budget_report_leaves_out_transfers_and_income(session: Session) -> None:
    card = create_account(session, "Test Card", "Test Bank", "credit_card")
    checking = create_account(session, "Test Checking", "Test Bank", "checking")
    set_budget(session, "Dining", 100000)
    set_budget(session, "Income", 1)
    create_rule(session, "ACME DINER", "Dining")
    create_rule(session, "PAYCHECK", "Paycheck")
    rows = [
        (card, date(2026, 5, 5), -5000, "ACME DINER", "a"),
        (checking, date(2026, 5, 10), -5000, "PAYMENT TO TEST CARD", "b"),
        (card, date(2026, 5, 11), 5000, "PAYMENT THANK YOU", "c"),
        (checking, date(2026, 5, 15), 200000, "PAYCHECK EXAMPLE CORP", "d"),
    ]
    for account, day, cents, description, mark in rows:
        session.add(
            TransactionRow(
                account_id=account.id,
                posted_date=day,
                amount_cents=cents,
                description=description,
                source="statement",
                fingerprint=mark.ljust(64, "0"),
            )
        )
    session.flush()
    categorize(session)
    pair_transfers(session)
    start, _ = month_bounds(date(2026, 5, 1))
    lines = {line.name: line for line in budget_report(session, start, date(2026, 5, 25))}
    assert lines["Dining"].spent_cents == 5000
    assert lines["Income"].spent_cents == 0


def test_list_without_month_uses_the_current_month(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Today:
        @staticmethod
        def today() -> date:
            return date(2026, 5, 16)

    monkeypatch.setattr("finances.cli.budgets.date", _Today)
    upgrade_to_head()
    assert run("budgets", "set", "--name", "Dining", "--amount", "100").exit_code == 0
    result = run("budgets", "list")
    assert result.stdout.startswith("Budgets for 2026-05.\n")
    assert table_rows(result.stdout)[1][0] == "Dining"
