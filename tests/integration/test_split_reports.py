from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.search import TransactionQuery, search_transactions
from finances.analysis.spending import load_flows, spending_report
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, set_category_by_hand, set_split
from finances.domain.spending import SpendingLine

FIRST, LAST = date(2026, 5, 1), date(2026, 5, 31)


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    """-$20.00 at FOOBAR GROCERY (1) split into Groceries -$12.00 and Home & Garden -$8.00;
    -$5.00 at ACME COFFEE (2) set to Dining by hand."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        for number, (day, cents, description) in enumerate(
            ((3, -2000, "FOOBAR GROCERY"), (4, -500, "ACME COFFEE")), start=1
        ):
            opened.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, day),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        opened.flush()
        set_split(opened, 1, [(-1200, "Groceries"), (-800, "Home & Garden")])
        set_category_by_hand(opened, 2, "Dining")
        yield opened


def test_flows_whole_and_in_parts(session: Session) -> None:
    whole = load_flows(session, FIRST, LAST)
    assert [(f.amount_cents, f.category, f.group) for f in whole] == [
        (-2000, "Split", "Split"),
        (-500, "Dining", "Food"),
    ]
    parts = load_flows(session, FIRST, LAST, parts=True)
    assert [(f.amount_cents, f.category, f.group, f.merchant) for f in parts] == [
        (-1200, "Groceries", "Food", "FOOBAR GROCERY"),
        (-800, "Home & Garden", "Home", "FOOBAR GROCERY"),
        (-500, "Dining", "Food", "ACME COFFEE"),
    ]


def test_spending_counts_the_parts(session: Session) -> None:
    assert spending_report(session, FIRST, LAST).lines == [
        SpendingLine("Groceries", 1200, 1, 0),
        SpendingLine("Home & Garden", 800, 1, 0),
        SpendingLine("Dining", 500, 1, 0),
    ]
    assert spending_report(session, FIRST, LAST, "group").lines == [
        SpendingLine("Food", 1700, 2, 0),
        SpendingLine("Home", 800, 1, 0),
    ]


def test_a_drill_down_finds_the_part(session: Session) -> None:
    found = search_transactions(session, TransactionQuery(category="groceries"))
    assert [(f.transaction.id, f.flow.amount_cents, f.flow.category) for f in found] == [
        (1, -1200, "Groceries"),
    ]
    every = search_transactions(session, TransactionQuery())
    assert [(f.transaction.id, f.flow.amount_cents, f.flow.category) for f in every] == [
        (2, -500, "Dining"),
        (1, -1200, "Groceries"),
        (1, -800, "Home & Garden"),
    ]
