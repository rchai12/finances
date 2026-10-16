from datetime import UTC, date, datetime

import pytest

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import FeedPullRow
from finances.db.repositories import (
    create_account,
    create_statement,
    map_feed_account,
    set_account_active,
)
from tests.support import CLI_NOT_MIGRATED, plain_lines, run, table_rows

AS_OF = ("--as-of", "2026-05-20")
HEADINGS = ["Kind", "Account", "Problem", "What to do"]
BACKUP = [
    "backup",
    "",
    "No backup yet.",
    "Run fin backup run, or press Back up now on the Backups page.",
]
ACCOUNTS = [
    [
        "sync",
        "Test Card",
        "No SimpleFIN pull for 10 days (last on 2026-05-10).",
        "Run fin sync run; if it fails, link SimpleFIN again (docs/sync-setup.md).",
    ],
    [
        "drift",
        "Test Card",
        "The balance differs from SimpleFIN's by -$12.34 on 2026-05-10.",
        "Look for a missing or extra transaction, or import the statement for that period.",
    ],
    [
        "statements",
        "Test Checking",
        "The newest statement ends 2026-03-31 (50 days ago).",
        "Upload the newest statement on the Statements page, or run fin import statement.",
    ],
    [
        "statements",
        "Test Savings",
        "No statements yet.",
        "Upload the newest statement on the Statements page, or run fin import statement.",
    ],
    [
        "gap",
        "Test Checking",
        "No statement covers 2026-02-01 to 2026-02-28.",
        "Upload the statement for those days.",
    ],
]


def statement(session, account, number: int, start: date, end: date) -> None:
    create_statement(
        session,
        account_id=account.id,
        source_filename=f"statement-{number}.pdf",
        file_sha256=f"s{number:02d}".ljust(64, "0"),
        parser_name="test",
        period_start=start,
        period_end=end,
        opening_balance_cents=0,
        closing_balance_cents=0,
        lines_parsed=0,
        rows_inserted=0,
        rows_duplicate=0,
    )


@pytest.fixture
def household(tmp_settings: Settings) -> Settings:
    """Test Card on SimpleFIN, last pulled 10 May with drift; Test Checking with statements for
    January and March; Test Savings with nothing; Old Card closed with nothing; no backup."""
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        checking = create_account(session, "Test Checking", "Test Bank", "checking")
        create_account(session, "Test Savings", "Test Bank", "savings")
        old = create_account(session, "Old Card", "Test Bank", "credit_card")
        set_account_active(session, old.id, False)
        map_feed_account(session, card.id, "ACT-1")
        session.add(
            FeedPullRow(
                account_id=card.id,
                inserted=0,
                updated=0,
                removed=0,
                unchanged=0,
                feed_total_cents=0,
                balance_cents=-50000,
                balance_date=date(2026, 5, 10),
                drift_cents=-1234,
                pulled_at=datetime(2026, 5, 10, 12, 0, tzinfo=UTC),
            )
        )
        statement(session, checking, 1, date(2026, 1, 1), date(2026, 1, 31))
        statement(session, checking, 2, date(2026, 3, 1), date(2026, 3, 31))
    engine.dispose()
    return tmp_settings


def test_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = run("health", *AS_OF)
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


def test_every_kind_of_problem(household: Settings) -> None:
    result = run("health", *AS_OF)
    assert result.exit_code == 0
    assert table_rows(result.stdout) == [HEADINGS, BACKUP, *ACCOUNTS]
    assert plain_lines(result.stdout) == ["Problems: 6."]


def test_a_recent_backup_is_no_problem(household: Settings) -> None:
    folder = household.effective_backup_dir
    folder.mkdir(parents=True)
    (folder / "finances-20260519-020000.db").write_bytes(b"")
    assert table_rows(run("health", *AS_OF).stdout) == [HEADINGS, *ACCOUNTS]


def test_no_problems(tmp_settings: Settings) -> None:
    assert run("db", "upgrade").exit_code == 0
    folder = tmp_settings.effective_backup_dir
    folder.mkdir(parents=True)
    (folder / "finances-20260520-020000.db").write_bytes(b"")
    result = run("health", *AS_OF)
    assert (result.exit_code, result.stdout) == (0, "No problems found.\n")


def test_a_day_that_is_not_one(household: Settings) -> None:
    result = run("health", "--as-of", "2026-02-30")
    assert result.exit_code == 2
    assert "'--as-of'" in result.stderr
