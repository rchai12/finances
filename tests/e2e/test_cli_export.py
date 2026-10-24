from datetime import date
from pathlib import Path

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_tags,
    create_account,
    set_category_by_hand,
    set_note,
    set_split,
)
from tests.support import failed_cleanly, run

TRANSACTIONS = (
    "ID,Posted,Date,Account,Description,Merchant,Category,Group,Kind,Amount,Card,Person,Part,"
    "Tags,Note\r\n"
    "1,2026-05-01,2026-05-01,Test Card,ACME COFFEE,ACME COFFEE,Coffee & Dessert,Food,spending,"
    "-12.34,,,,work,client lunch\r\n"
    "2,2026-05-03,2026-05-03,Test Card,FOOBAR GROCERY,FOOBAR GROCERY,Groceries,Food,spending,"
    "-12.00,,,1,,\r\n"
    "2,2026-05-03,2026-05-03,Test Card,FOOBAR GROCERY,FOOBAR GROCERY,Home & Garden,Home,"
    "spending,-8.00,,,2,,\r\n"
    "3,2026-05-05,2026-05-05,Test Card,ACME COFFEE,ACME COFFEE,Coffee & Dessert,Food,spending,"
    "5.00,,,,,\r\n"
)
YEAR = (
    "Section,Label,Spent,Refunds,Net,Count\r\n"
    "group,Food,24.34,5.00,19.34,3\r\n"
    "group,Home,8.00,0.00,8.00,1\r\n"
    "category,Groceries,12.00,0.00,12.00,1\r\n"
    "category,Home & Garden,8.00,0.00,8.00,1\r\n"
    "category,Coffee & Dessert,12.34,5.00,7.34,2\r\n"
    "tax,Gifts & Donations,0.00,0.00,0.00,0\r\n"
    "tax,Medical,0.00,0.00,0.00,0\r\n"
    "tax,Taxes,0.00,0.00,0.00,0\r\n"
)
SPENDING = (
    "Category,Spent,Refunds,Net,Count\r\n"
    "Groceries,12.00,0.00,12.00,1\r\n"
    "Home & Garden,8.00,0.00,8.00,1\r\n"
    "Coffee & Dessert,12.34,5.00,7.34,2\r\n"
)


@pytest.fixture
def card(tmp_settings: Settings) -> Settings:
    """May 2026 on a card: ACME COFFEE -$12.34 (1) tagged work with a note; FOOBAR GROCERY
    -$20.00 (2) split into Groceries -$12.00 and Home & Garden -$8.00; a refund of $5.00 at
    ACME COFFEE (3); and -$9.99 on 2025-12-31 (4), the year before."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        rows = [
            (date(2026, 5, 1), -1234, "ACME COFFEE"),
            (date(2026, 5, 3), -2000, "FOOBAR GROCERY"),
            (date(2026, 5, 5), 500, "ACME COFFEE"),
            (date(2025, 12, 31), -999, "ACME COFFEE"),
        ]
        for number, (day, cents, description) in enumerate(rows, start=1):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=day,
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        for number in (1, 3, 4):
            set_category_by_hand(session, number, "Coffee & Dessert")
        set_split(session, 2, [(-1200, "Groceries"), (-800, "Home & Garden")])
        add_tags(session, [1], "work")
        set_note(session, 1, "client lunch")
    engine.dispose()
    return tmp_settings


def folder(settings: Settings) -> Path:
    return settings.data_dir / "exports"


def test_transactions(card: Settings) -> None:
    result = run("export", "transactions", "--from", "2026-01-01", "--to", "2026-12-31")
    written = folder(card) / "transactions-2026-01-01-to-2026-12-31.csv"
    assert (result.exit_code, result.stdout) == (0, f"Wrote 4 rows to {written}.\n")
    assert written.read_bytes().decode("utf-8") == TRANSACTIONS


def test_the_year(card: Settings) -> None:
    result = run("export", "year", "--year", "2026")
    written = folder(card) / "year-2026.csv"
    assert (result.exit_code, result.stdout) == (0, f"Wrote 8 rows to {written}.\n")
    assert written.read_bytes().decode("utf-8") == YEAR


def test_spending_for_a_month(card: Settings) -> None:
    result = run("export", "spending", "--month", "2026-05")
    written = folder(card) / "spending-by-category-2026-05-01-to-2026-05-31.csv"
    assert (result.exit_code, result.stdout) == (0, f"Wrote 3 rows to {written}.\n")
    assert written.read_bytes().decode("utf-8") == SPENDING


def test_another_folder_and_replacing(card: Settings, tmp_path: Path) -> None:
    elsewhere = tmp_path / "taxes"
    first = run("export", "year", "--year", "2026", "--folder", str(elsewhere))
    assert first.stdout == f"Wrote 8 rows to {elsewhere / 'year-2026.csv'}.\n"
    again = run("export", "year", "--year", "2026", "--folder", str(elsewhere))
    assert failed_cleanly(again, "the file is already there; add --force to replace it")
    (elsewhere / "year-2026.csv").write_text("old", encoding="utf-8")
    forced = run("export", "year", "--year", "2026", "--folder", str(elsewhere), "--force")
    assert forced.exit_code == 0
    assert (elsewhere / "year-2026.csv").read_bytes().decode("utf-8") == YEAR


def test_the_export_folder_setting(card: Settings, tmp_path: Path, monkeypatch) -> None:
    from finances.config import get_settings

    monkeypatch.setenv("FIN_EXPORT_DIR", str(tmp_path / "out"))
    get_settings.cache_clear()
    result = run("export", "year", "--year", "2026")
    assert result.stdout == f"Wrote 8 rows to {tmp_path / 'out' / 'year-2026.csv'}.\n"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ("transactions", "--from", "2026-12-31", "--to", "2026-01-01"),
            "the start date is after the end date",
        ),
        (("year", "--year", "0"), "year must be from 1 to 9999"),
        (
            ("spending", "--month", "2026-05", "--by", "colour"),
            "by must be one of: category, group, merchant, person, account, bank, card",
        ),
    ],
)
def test_refused(card: Settings, args: tuple[str, ...], message: str) -> None:
    assert failed_cleanly(run("export", *args), message)
