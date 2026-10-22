from datetime import date

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_balance_snapshot,
    create_account,
    set_account_active,
)
from finances.domain.models import DataSource
from tests.support import run, table_rows

AS_OF = ("--as-of", "2026-05-25")


def upgrade() -> None:
    assert run("db", "upgrade").exit_code == 0


def add_tx(
    session, account_id: int, day: date, cents: int, description: str, *, pending: bool = False
) -> None:
    session.add(
        TransactionRow(
            account_id=account_id,
            posted_date=day,
            amount_cents=cents,
            description=description,
            is_pending=pending,
            source="statement",
            fingerprint=f"{account_id}-{day}-{cents}-{description}-{pending}".ljust(64, "0")[:64],
        )
    )


def test_an_inactive_account_is_left_out_of_the_summary_but_found_by_name(
    tmp_settings: Settings,
) -> None:
    upgrade()
    engine = get_engine()
    with session_scope(engine) as session:
        closed = create_account(session, "Old Card", "Test Bank", "credit_card")
        add_balance_snapshot(session, closed.id, date(2026, 5, 20), -1000, DataSource.STATEMENT)
        set_account_active(session, closed.id, False)
        open_one = create_account(session, "Test Checking", "Test Bank", "checking")
        add_balance_snapshot(session, open_one.id, date(2026, 5, 24), 5000, DataSource.STATEMENT)
    engine.dispose()
    names = [row[0] for row in table_rows(run("forecast", *AS_OF).stdout)[1:]]
    assert names == ["Test Checking"]
    assert "Old Card" not in run("forecast", *AS_OF).stdout
    detail = run("forecast", *AS_OF, "--account", "old card")
    assert detail.exit_code == 0
    assert detail.stdout.splitlines()[0] == ("Forecast for Old Card from 2026-05-25 to 2026-06-23.")


def test_a_recurring_refund_is_not_income(tmp_settings: Settings) -> None:
    upgrade()
    engine = get_engine()
    with session_scope(engine) as session:
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        add_balance_snapshot(session, checking.id, date(2026, 5, 24), 10000, DataSource.STATEMENT)
        for month in (3, 4, 5):
            add_tx(session, checking.id, date(2026, month, 9), 599, "FOOBAR GROCERY")
    engine.dispose()
    assert run("rules", "add", "--pattern", "FOOBAR", "--category", "Groceries").exit_code == 0
    row = table_rows(run("forecast", *AS_OF).stdout)[1]
    assert row[3] == "$0.00"
    assert "FOOBAR GROCERY" not in run("forecast", *AS_OF, "--account", "Test Checking").stdout


def test_a_pending_charge_is_left_out(tmp_settings: Settings) -> None:
    upgrade()
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        add_balance_snapshot(session, card.id, date(2026, 5, 24), -2000, DataSource.STATEMENT)
        for month in (3, 4, 5):
            add_tx(session, card.id, date(2026, month, 10), -2500, "QUUX RENT", pending=True)
    engine.dispose()
    assert "QUUX RENT" not in run("forecast", *AS_OF, "--account", "Test Card").stdout
    assert run("forecast", *AS_OF, "--account", "Test Card").stdout.splitlines()[2] == (
        "Nothing expected."
    )


def test_two_accounts_without_a_balance_are_named_in_order(tmp_settings: Settings) -> None:
    upgrade()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Zeta", "Test Bank", "checking")
        funded = create_account(session, "Test Checking", "Test Bank", "checking")
        add_balance_snapshot(session, funded.id, date(2026, 5, 24), 1000, DataSource.STATEMENT)
        create_account(session, "Test Alpha", "Test Bank", "checking")
    engine.dispose()
    lines = [line for line in run("forecast", *AS_OF).stdout.splitlines() if line]
    assert lines[-1] == "No balance yet: Test Alpha, Test Zeta."


def test_forecast_without_as_of_uses_today(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 5, 25))
    upgrade()
    assert run("forecast").stdout.splitlines()[0] == "Forecast from 2026-05-25 to 2026-06-23."


def test_a_window_out_of_range(tmp_settings: Settings) -> None:
    upgrade()
    result = run("forecast", *AS_OF, "--days", "91")
    assert result.exit_code == 2
    assert "'--days'" in result.stderr
