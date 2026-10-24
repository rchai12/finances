from collections.abc import Iterator
from datetime import date

import pytest
import typer
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.yearend import year_report
from finances.cli.reports import year_command
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_category,
    create_transfer_pair,
    list_categories,
    list_changes,
    rename_category,
    set_tax_relevant,
)
from finances.domain.models import CONFIRMED
from finances.domain.spending import SpendingLine
from tests.support import plain_lines, run


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    """A migrated database with one card (id 1) and no transactions."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        yield opened


def add(session: Session, account: int, posted: date, cents: int, description: str) -> int:
    row = TransactionRow(
        account_id=account,
        posted_date=posted,
        amount_cents=cents,
        description=description,
        source="statement",
        fingerprint=f"{account}-{posted}-{cents}-{description}".ljust(64, "0")[:64],
    )
    session.add(row)
    session.flush()
    return row.id


def test_a_new_category_is_not_tax_relevant(session: Session) -> None:
    made = create_category(session, "Probe Care", "Health")
    assert made.is_tax is False
    flagged = {item.name for item in list_categories(session) if item.is_tax}
    assert flagged == {"Gifts & Donations", "Medical", "Taxes"}


def test_setting_the_flag_records_once(session: Session) -> None:
    found = set_tax_relevant(session, "Groceries", True)
    logged = list_changes(session, action="category_tax_set")
    assert [(item.kind, item.record_id, item.before, item.after) for item in logged] == [
        ("category", found.id, "not tax", "tax")
    ]
    set_tax_relevant(session, "Groceries", True)
    assert len(list_changes(session, action="category_tax_set")) == 1


def test_a_renamed_tax_category_keeps_its_flag(session: Session) -> None:
    set_tax_relevant(session, "Groceries", True)
    _, renamed = rename_category(session, "Groceries", "Food shop")
    assert renamed.is_tax is True
    found = {item.name: item.is_tax for item in list_categories(session)}
    assert found["Food shop"] is True
    assert "Groceries" not in found


@pytest.mark.parametrize("year", [0, 10000])
def test_year_report_refuses_a_year_outside_the_range(session: Session, year: int) -> None:
    with pytest.raises(ValueError) as caught:
        year_report(session, year)
    assert str(caught.value) == "year must be from 1 to 9999"


def test_a_transfer_is_not_in_any_line(session: Session) -> None:
    create_account(session, "Test Checking", "Test Bank", "checking")
    out_id = add(session, 2, date(2026, 6, 1), -5000, "TRANSFER TO CARD")
    in_id = add(session, 1, date(2026, 6, 1), 5000, "PAYMENT THANK YOU")
    create_transfer_pair(session, out_id, in_id, CONFIRMED)
    report = year_report(session, 2026)
    assert report.groups == []
    assert report.categories == []
    assert report.tax == [
        SpendingLine("Gifts & Donations", 0, 0, 0),
        SpendingLine("Medical", 0, 0, 0),
        SpendingLine("Taxes", 0, 0, 0),
    ]


def test_fin_year_with_no_tax_relevant_category(tmp_settings: Settings) -> None:
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        for name in ("Medical", "Gifts & Donations", "Taxes"):
            set_tax_relevant(session, name, False)
    engine.dispose()
    result = run("year", "--year", "2026")
    assert result.exit_code == 0
    assert "No tax-relevant categories." in plain_lines(result.stdout)


def test_the_year_command_refuses_an_out_of_range_year(
    tmp_settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("db", "upgrade").exit_code == 0
    with pytest.raises(typer.Exit) as caught:
        year_command(year=0)
    assert caught.value.exit_code == 1
    assert capsys.readouterr().err == "Error: year must be from 1 to 9999\n"
