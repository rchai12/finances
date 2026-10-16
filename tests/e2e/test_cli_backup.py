import re
from datetime import date
from pathlib import Path

import pytest

from finances.cli.main import app
from finances.config import Settings, get_settings
from finances.db.engine import get_engine, session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from tests.support import CLI_NOT_MIGRATED, failed_cleanly, run, runner, table_rows

WRITTEN = re.compile(
    r"Backup written: (?P<path>.+/finances-\d{8}-\d{6}\.db) \(2 accounts, 3 transactions\)\.\n"
    r"Backups kept: (?P<kept>\d+)\. Removed: (?P<removed>\d+)\.\n"
)


@pytest.fixture
def money(tmp_settings: Settings) -> Settings:
    assert run("db", "upgrade").exit_code == 0
    engine = get_engine()
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        create_account(session, "Test Checking", "Test Bank", "checking")
        for number in range(1, 4):
            session.add(
                TransactionRow(
                    account_id=card.id,
                    posted_date=date(2026, 5, number),
                    amount_cents=-100,
                    description="ACME COFFEE",
                    source="statement",
                    fingerprint=f"b{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()
    return tmp_settings


def test_needs_a_migrated_database(tmp_settings: Settings) -> None:
    result = run("backup", "run")
    assert (result.exit_code, result.stderr) == (1, CLI_NOT_MIGRATED)


def test_back_up_into_the_data_folder_by_default(money: Settings) -> None:
    result = run("backup", "run")
    assert result.exit_code == 0
    found = WRITTEN.fullmatch(result.stdout)
    assert found is not None, result.stdout
    path = Path(found["path"])
    assert path.parent == (money.data_dir / "backups").resolve()
    assert path.is_file()
    assert (found["kept"], found["removed"]) == ("1", "0")


def test_the_folder_and_how_many_to_keep_come_from_settings(
    money: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIN_BACKUP_DIR", str(tmp_path / "elsewhere"))
    monkeypatch.setenv("FIN_BACKUP_KEEP", "1")
    folder = tmp_path / "elsewhere"
    folder.mkdir()
    (folder / "finances-20200101-000000.db").write_bytes(b"")
    get_settings.cache_clear()
    found = WRITTEN.fullmatch(run("backup", "run").stdout)
    assert found is not None
    assert Path(found["path"]).parent == folder.resolve()
    assert (found["kept"], found["removed"]) == ("1", "1")
    assert [path.name for path in folder.iterdir()] == [Path(found["path"]).name]


def test_list_backups(money: Settings) -> None:
    assert run("backup", "list").stdout == "No backups.\n"
    folder = money.data_dir / "backups"
    folder.mkdir(parents=True)
    for name in ("finances-20261015-143005.db", "finances-20261016-020000.db", "notes.txt"):
        (folder / name).write_bytes(b"")
    assert table_rows(run("backup", "list").stdout) == [
        ["File", "Taken (UTC)", "Size"],
        ["finances-20261016-020000.db", "2026-10-16 02:00:00", "0 B"],
        ["finances-20261015-143005.db", "2026-10-15 14:30:05", "0 B"],
    ]


def test_restore_after_a_yes(money: Settings) -> None:
    made = Path(WRITTEN.fullmatch(run("backup", "run").stdout)["path"])
    result = run("backup", "restore", made, "--yes")
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert lines[0] == f"Restored {made.name}."
    assert re.fullmatch(
        r"The database it replaced is kept as finances-\d{8}-\d{6}-before-restore\.db\.", lines[1]
    )
    assert len(lines) == 2


def test_restore_asks_first(money: Settings) -> None:
    made = Path(WRITTEN.fullmatch(run("backup", "run").stdout)["path"])
    result = runner.invoke(app, ["backup", "restore", str(made)], input="n\n")
    assert result.exit_code == 0
    assert result.stdout.endswith("Nothing restored.\n")
    assert f"Replace the database with {made.name}?" in result.stdout


def test_restore_refuses_a_file_that_is_not_a_backup(money: Settings, tmp_path: Path) -> None:
    text = tmp_path / "notes.txt"
    text.write_text("not a database", encoding="utf-8")
    result = run("backup", "restore", text, "--yes")
    assert failed_cleanly(result, "notes.txt is not a readable finances backup")
