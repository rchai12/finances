import sqlite3
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select

import finances.db
from finances.db.backup import (
    BackupCheck,
    backup_name,
    check_backup,
    list_backups,
    make_backup,
    restore_backup,
)
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import head_revision, upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account

MOMENT = datetime(2026, 10, 15, 14, 30, 5, tzinfo=UTC)
NAME = "finances-20261015-143005.db"


def add_transactions(url: str, account_id: int, count: int, start: int) -> None:
    engine = get_engine(url)
    with session_scope(engine) as session:
        for number in range(start, start + count):
            session.add(
                TransactionRow(
                    account_id=account_id,
                    posted_date=date(2026, 5, 1),
                    amount_cents=-100,
                    description="ACME COFFEE",
                    source="statement",
                    fingerprint=f"b{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()


def transactions_in(path: Path) -> int:
    engine = get_engine(f"sqlite:///{path.as_posix()}")
    with session_scope(engine) as session:
        found = session.scalar(select(func.count()).select_from(TransactionRow))
    engine.dispose()
    return found


@pytest.fixture
def live(db_url: str) -> str:
    """A migrated database with two accounts and three transactions."""
    upgrade_to_head(db_url)
    engine = get_engine(db_url)
    with session_scope(engine) as session:
        card = create_account(session, "Test Card", "Test Bank", "credit_card")
        create_account(session, "Test Checking", "Test Bank", "checking")
        card_id = card.id
    engine.dispose()
    add_transactions(db_url, card_id, 3, 1)
    return db_url


def live_path(url: str) -> Path:
    return Path(url.removeprefix("sqlite:///"))


def test_backup_names_use_utc() -> None:
    assert backup_name(MOMENT) == NAME
    eastern = MOMENT.astimezone(timezone(timedelta(hours=-4)))
    assert backup_name(eastern) == NAME


def test_a_backup_is_a_checked_copy(live: str, tmp_path: Path) -> None:
    folder = tmp_path / "backups"
    result = make_backup(live, folder, 3, MOMENT)
    assert result.path == folder / NAME
    assert result.check == BackupCheck(revision=head_revision(), accounts=2, transactions=3)
    assert (result.kept, result.removed) == (1, [])
    assert sorted(path.name for path in folder.iterdir()) == [NAME]
    assert transactions_in(result.path) == 3
    assert check_backup(result.path) == result.check


def test_only_the_newest_are_kept(live: str, tmp_path: Path) -> None:
    folder = tmp_path / "backups"
    folder.mkdir()
    (folder / "notes.txt").write_text("keep me", encoding="utf-8")
    (folder / "finances-20200101-000000-before-restore.db").write_text("x", encoding="utf-8")
    moments = [MOMENT + timedelta(hours=hour) for hour in range(4)]
    results = [make_backup(live, folder, 3, moment) for moment in moments]
    assert results[-1].kept == 3
    assert [path.name for path in results[-1].removed] == [NAME]
    assert [path.name for path in list_backups(folder)] == [
        "finances-20261015-173005.db",
        "finances-20261015-163005.db",
        "finances-20261015-153005.db",
    ]
    assert (folder / "notes.txt").exists()
    assert (folder / "finances-20200101-000000-before-restore.db").exists()


def test_two_backups_in_one_second(live: str, tmp_path: Path) -> None:
    folder = tmp_path / "backups"
    make_backup(live, folder, 3, MOMENT)
    with pytest.raises(ValueError) as caught:
        make_backup(live, folder, 3, MOMENT)
    assert str(caught.value) == f"a backup named {NAME} already exists; try again in a second"
    assert sorted(path.name for path in folder.iterdir()) == [NAME]


@pytest.mark.parametrize(
    ("url", "keep", "message"),
    [
        ("sqlite://", 3, "backups need a database file"),
        ("sqlite:///:memory:", 3, "backups need a database file"),
        (None, 0, "keep must be at least 1"),
    ],
)
def test_refused_backups(
    live: str, tmp_path: Path, url: str | None, keep: int, message: str
) -> None:
    with pytest.raises(ValueError) as caught:
        make_backup(url or live, tmp_path / "backups", keep, MOMENT)
    assert str(caught.value) == message
    assert not (tmp_path / "backups").exists() or list((tmp_path / "backups").iterdir()) == []


def test_a_file_that_is_not_a_backup(tmp_path: Path) -> None:
    text = tmp_path / "notes.txt"
    text.write_text("not a database", encoding="utf-8")
    plain = tmp_path / "plain.db"
    with sqlite3.connect(plain) as connection:
        connection.execute("CREATE TABLE things (id INTEGER)")
    connection.close()
    newer = tmp_path / "newer.db"
    with sqlite3.connect(newer) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('ffff')")
    connection.close()
    for path, message in (
        (text, "notes.txt is not a readable finances backup"),
        (plain, "plain.db is not a readable finances backup"),
        (tmp_path / "missing.db", "missing.db is not a readable finances backup"),
        (newer, "newer.db comes from a newer version of the app (revision ffff)"),
    ):
        with pytest.raises(ValueError) as caught:
            check_backup(path)
        assert str(caught.value) == message
    assert not (tmp_path / "missing.db").exists()


def test_restore_puts_the_backup_back_and_keeps_what_it_replaced(live: str, tmp_path: Path) -> None:
    folder = tmp_path / "backups"
    made = make_backup(live, folder, 3, MOMENT)
    add_transactions(live, 1, 1, 50)
    later = MOMENT + timedelta(minutes=30)
    result = restore_backup(live, made.path, folder, later)
    assert result.check == made.check
    assert result.replaced == folder / "finances-20261015-150005-before-restore.db"
    assert result.needs_upgrade is False
    assert transactions_in(live_path(live)) == 3
    assert transactions_in(result.replaced) == 4
    assert [path.name for path in list_backups(folder)] == [NAME]


def test_restore_onto_a_new_machine_and_an_older_backup(tmp_path: Path) -> None:
    old = tmp_path / "old.db"
    config = Config()
    config.set_main_option("script_location", str(Path(finances.db.__file__).parent / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{old.as_posix()}")
    command.upgrade(config, "0008")
    target = f"sqlite:///{(tmp_path / 'new' / 'finances.db').as_posix()}"
    result = restore_backup(target, old, tmp_path / "backups", MOMENT)
    assert result.replaced is None
    assert result.needs_upgrade is True
    assert result.check == BackupCheck(revision="0008", accounts=0, transactions=0)
    assert (tmp_path / "new" / "finances.db").exists()


def test_a_refused_restore_changes_nothing(live: str, tmp_path: Path) -> None:
    text = tmp_path / "notes.txt"
    text.write_text("not a database", encoding="utf-8")
    with pytest.raises(ValueError):
        restore_backup(live, text, tmp_path / "backups", MOMENT)
    assert transactions_in(live_path(live)) == 3
    assert not (tmp_path / "backups").exists()
