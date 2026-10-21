from datetime import date

import pytest
from sqlalchemy import select

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, create_transfer_pair
from finances.domain.models import CONFIRMED
from tests.support import run, table_rows

AS_OF = ("--as-of", "2026-05-25")


def store(rows: list[tuple[str, date, int, str]]) -> None:
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        accounts = {}
        for name, day, cents, description in rows:
            if name not in accounts:
                if "Checking" in name:
                    kind = "checking"
                elif "Savings" in name:
                    kind = "savings"
                else:
                    kind = "credit_card"
                accounts[name] = create_account(session, name, "Test Bank", kind)
            session.add(
                TransactionRow(
                    account_id=accounts[name].id,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"{name}-{day}-{cents}-{description}".ljust(64, "0")[:64],
                )
            )
    engine.dispose()


def test_a_quarterly_bill_in_the_window(tmp_settings: Settings) -> None:
    store(
        [
            ("Test Card", date(2025, 9, 15), -4500, "QUUX TAX PREP"),
            ("Test Card", date(2025, 12, 15), -4500, "QUUX TAX PREP"),
            ("Test Card", date(2026, 3, 15), -4500, "QUUX TAX PREP"),
        ]
    )
    merchants = [row[2] for row in table_rows(run("upcoming", *AS_OF).stdout)[1:]]
    assert merchants == ["QUUX TAX PREP"]
    assert table_rows(run("upcoming", *AS_OF).stdout)[1] == [
        "2026-06-15",
        "bill",
        "QUUX TAX PREP",
        "quarter",
        "-$45.00",
    ]


def test_a_paired_transfer_is_not_income(tmp_settings: Settings) -> None:
    store(
        [
            ("Test Checking", date(2026, 3, 1), -2000, "TRANSFER TO SAVINGS"),
            ("Test Savings", date(2026, 3, 1), 2000, "TRANSFER FROM CHECKING"),
            ("Test Checking", date(2026, 4, 1), -2000, "TRANSFER TO SAVINGS"),
            ("Test Savings", date(2026, 4, 1), 2000, "TRANSFER FROM CHECKING"),
            ("Test Checking", date(2026, 5, 1), -2000, "TRANSFER TO SAVINGS"),
            ("Test Savings", date(2026, 5, 1), 2000, "TRANSFER FROM CHECKING"),
        ]
    )
    engine = get_engine()
    with session_scope(engine) as session:
        rows = list(session.scalars(select(TransactionRow)))
        outs = sorted(row.id for row in rows if row.amount_cents < 0)
        ins = sorted(row.id for row in rows if row.amount_cents > 0)
        for out_id, in_id in zip(outs, ins, strict=True):
            create_transfer_pair(session, out_id, in_id, CONFIRMED)
    engine.dispose()
    assert "TRANSFER" not in run("recurring", "--income", *AS_OF).stdout
    assert "TRANSFER" not in run("upcoming", *AS_OF).stdout


def test_uncategorized_income_is_counted(tmp_settings: Settings) -> None:
    store(
        [
            ("Test Checking", day, 180000, "ACME PAYROLL")
            for day in (date(2026, 2, 15), date(2026, 3, 15), date(2026, 4, 15), date(2026, 5, 15))
        ]
    )
    rows = table_rows(run("recurring", "--income", *AS_OF).stdout)
    assert rows[1][0] == "ACME PAYROLL"
    assert rows[1][1] == "month"
    merchants = [row[2] for row in table_rows(run("upcoming", *AS_OF).stdout)[1:]]
    assert "ACME PAYROLL" in merchants


def test_upcoming_without_as_of_uses_today(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 5, 25))
    store([])
    assert run("upcoming").stdout.splitlines()[0] == "Expected from 2026-05-25 to 2026-06-23."


def test_stopped_income_is_listed_only_with_all(tmp_settings: Settings) -> None:
    store(
        [
            ("Test Checking", date(2025, 1, 15), 250000, "OLD PAYCHECK"),
            ("Test Checking", date(2025, 2, 15), 250000, "OLD PAYCHECK"),
            ("Test Checking", date(2025, 3, 15), 250000, "OLD PAYCHECK"),
        ]
    )
    assert run("rules", "add", "--pattern", "OLD PAYCHECK", "--category", "Paycheck").exit_code == 0
    without = run("recurring", "--income", *AS_OF)
    assert without.stdout.startswith("No recurring income.")
    with_all = table_rows(run("recurring", "--income", "--all", *AS_OF).stdout)
    assert with_all[1][0] == "OLD PAYCHECK"
    assert with_all[1][-1] == "no"
