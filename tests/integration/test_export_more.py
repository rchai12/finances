from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.export import transactions_for_export
from finances.config import Settings
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import add_tags, create_account
from finances.export.files import write_csv
from tests.support import failed_cleanly, run


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        yield opened


def _add(session: Session, number: int, posted: date, cents: int, *, pending: bool = False) -> int:
    row = TransactionRow(
        account_id=1,
        posted_date=posted,
        amount_cents=cents,
        description="ACME COFFEE",
        is_pending=pending,
        source="statement",
        fingerprint=f"{number:064d}",
    )
    session.add(row)
    session.flush()
    return row.id


def test_every_transaction_in_the_range_and_tags_past_500(session: Session) -> None:
    for number in range(1, 1202):
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=date(2026, 5, 1),
                amount_cents=-100,
                description="ACME COFFEE",
                source="statement",
                fingerprint=f"{number:064d}",
            )
        )
    session.flush()
    for number in range(1, 601):
        add_tags(session, [number], f"tag{number:04d}")
    lines = transactions_for_export(session, date(2026, 1, 1), date(2026, 12, 31))
    assert len(lines) == 1201
    tagged = {line.found.transaction.id: line.tags for line in lines if line.tags}
    assert tagged == {number: [f"tag{number:04d}"] for number in range(1, 601)}


def test_a_pending_transaction_is_written_as_pending(session: Session) -> None:
    _add(session, 1, date(2026, 5, 1), -500, pending=True)
    lines = transactions_for_export(session, date(2026, 5, 1), date(2026, 5, 1))
    assert [line.found.flow.kind for line in lines] == ["pending"]


def test_write_csv_makes_a_missing_folder_two_levels_deep(tmp_path: Path) -> None:
    folder = tmp_path / "taxes" / "2026"
    path = write_csv(folder, "out.csv", "ID\r\n", force=False)
    assert path == folder / "out.csv"
    assert path.read_bytes() == b"ID\r\n"


def test_transactions_with_no_dates_writes_this_year(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run("db", "upgrade").exit_code == 0
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 6, 15))
    result = run("export", "transactions")
    written = tmp_settings.data_dir / "exports" / "transactions-2026-01-01-to-2026-12-31.csv"
    assert (result.exit_code, result.stdout) == (0, f"Wrote 0 rows to {written}.\n")
    assert written.is_file()


def test_spending_with_no_options_writes_this_month_by_category(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run("db", "upgrade").exit_code == 0
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 5, 15))
    result = run("export", "spending")
    written = (
        tmp_settings.data_dir / "exports" / "spending-by-category-2026-05-01-to-2026-05-31.csv"
    )
    assert (result.exit_code, result.stdout) == (0, f"Wrote 0 rows to {written}.\n")
    assert written.is_file()


def test_year_with_no_year_writes_this_year(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run("db", "upgrade").exit_code == 0
    monkeypatch.setattr("finances.clock.today", lambda: date(2026, 8, 1))
    result = run("export", "year")
    written = tmp_settings.data_dir / "exports" / "year-2026.csv"
    assert (result.exit_code, result.stdout) == (0, f"Wrote 3 rows to {written}.\n")
    assert written.is_file()


def test_a_database_that_is_not_migrated(tmp_settings: Settings) -> None:
    assert failed_cleanly(run("export", "year"), "database is not up to date (run: fin db upgrade)")
