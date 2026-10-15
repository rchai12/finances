from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from finances.analysis.recurring import recurring_charges
from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_transfer_pair, set_category_by_hand
from finances.domain.models import CONFIRMED
from finances.domain.recurring import Charge, find_recurring

CHECKING, CARD = 1, 2
AS_OF = date(2026, 4, 1)
MONTHS = (date(2026, 1, 5), date(2026, 2, 5), date(2026, 3, 5))


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Checking", "Test Bank", "checking")
        create_account(opened, "Test Card", "Example Card Co", "credit_card")
        yield opened


def add(
    session: Session,
    account: int,
    day: date,
    cents: int,
    description: str,
    *,
    pending: bool = False,
) -> int:
    row = TransactionRow(
        account_id=account,
        posted_date=day,
        amount_cents=cents,
        description=description,
        is_pending=pending,
        source="statement",
        fingerprint=f"r{account}-{day}-{cents}-{description}"[:64].ljust(64, "0"),
    )
    session.add(row)
    session.flush()
    return row.id


def monthly(session: Session, account: int, cents: int, description: str) -> list[int]:
    return [add(session, account, day, cents, description) for day in MONTHS]


def found(session: Session, as_of: date = AS_OF) -> list[tuple[str, int, int]]:
    return [
        (item.merchant, item.amount_cents, item.count) for item in recurring_charges(session, as_of)
    ]


def test_a_monthly_charge_is_found(session: Session) -> None:
    monthly(session, CARD, -1599, "QUUX STREAMING")
    assert found(session) == [("QUUX STREAMING", 1599, 3)]


def test_a_pending_charge_is_left_out(session: Session) -> None:
    monthly(session, CARD, -1599, "QUUX STREAMING")
    add(session, CARD, date(2026, 3, 28), -1599, "QUUX STREAMING", pending=True)
    assert found(session) == [("QUUX STREAMING", 1599, 3)]


def test_a_paired_transfer_is_left_out(session: Session) -> None:
    outs = monthly(session, CHECKING, -50000, "PAYMENT TO TEST CARD")
    for out, day in zip(outs, MONTHS, strict=True):
        into = add(session, CARD, day + timedelta(days=1), 50000, "PAYMENT THANK YOU")
        create_transfer_pair(session, out, into, CONFIRMED)
    assert found(session) == []


def test_a_charge_with_an_income_category_is_left_out(session: Session) -> None:
    for item in monthly(session, CHECKING, -1000, "EXAMPLE CORP ADJUSTMENT"):
        set_category_by_hand(session, item, "Other Income")
    assert found(session) == []


def test_a_refund_is_left_out(session: Session) -> None:
    for item in monthly(session, CARD, 500, "FOOBAR GROCERY"):
        set_category_by_hand(session, item, "Groceries")
    assert found(session) == []


def test_charges_after_the_day_are_ignored(session: Session) -> None:
    monthly(session, CARD, -1599, "QUUX STREAMING")
    add(session, CARD, date(2026, 4, 5), -1599, "QUUX STREAMING")
    assert found(session) == [("QUUX STREAMING", 1599, 3)]
    assert found(session, date(2026, 4, 5)) == [("QUUX STREAMING", 1599, 4)]


def test_a_charge_at_zero_or_above_does_not_break_a_series() -> None:
    charges = [Charge("ACME GYM", day, -3000) for day in MONTHS] + [
        Charge("ACME GYM", date(2026, 1, 20), 3000),
        Charge("ACME GYM", date(2026, 2, 20), 0),
    ]
    assert [(item.merchant, item.count) for item in find_recurring(charges, AS_OF)] == [
        ("ACME GYM", 3)
    ]


def test_fin_recurring_without_as_of_uses_today(tmp_settings: Settings) -> None:
    runner = CliRunner(env={"COLUMNS": "200"})
    assert runner.invoke(app, ["db", "upgrade"]).exit_code == 0
    today = date.today()
    engine = get_engine()
    with session_scope(engine) as opened:
        create_account(opened, "Test Card", "Example Card Co", "credit_card")
        for days in (70, 40, 10):
            add(opened, 1, today - timedelta(days=days), -1599, "QUUX STREAMING")
        add(opened, 1, today + timedelta(days=5), -1599, "QUUX STREAMING")
    engine.dispose()
    result = runner.invoke(app, ["recurring"])
    assert result.exit_code == 0
    (row,) = [line for line in result.stdout.splitlines() if line.startswith("│ QUUX")]
    cells = [cell.strip() for cell in row.split("│")[1:-1]]
    assert (cells[4], cells[5], cells[7]) == ("3", (today - timedelta(days=10)).isoformat(), "yes")
    assert result.stdout.splitlines()[-1] == "Recurring: 1 active, $15.99 a month."
