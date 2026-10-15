import shutil
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

import finances.db
from finances.config import Settings, get_settings
from finances.db import backup
from finances.db.backup import check_backup, list_backups, make_backup, restore_backup
from finances.db.migrate import upgrade_to_head
from tests.support import failed_cleanly, run

MOMENT = datetime(2026, 10, 15, 14, 30, 5, tzinfo=UTC)
NAME = "finances-20261015-143005.db"
SET_ASIDE = "finances-20261015-143005-before-restore.db"


@pytest.fixture
def live(db_url: str) -> str:
    upgrade_to_head(db_url)
    return db_url


def filled(path: Path) -> Path:
    """A plain SQLite file large enough that damage in its middle hits a table and an index."""
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE things (id INTEGER PRIMARY KEY, label TEXT)")
        connection.execute("CREATE INDEX things_label ON things (label)")
        rows = [(f"thing {number:05d}",) for number in range(3000)]
        connection.executemany("INSERT INTO things (label) VALUES (?)", rows)
        connection.commit()
    return path


def damaged(path: Path, at: int) -> Path:
    data = bytearray(path.read_bytes())
    data[at : at + 512] = b"\xff" * 512
    path.write_bytes(bytes(data))
    return path


def test_the_backup_folder_defaults_to_the_data_folder(tmp_settings: Settings) -> None:
    assert tmp_settings.effective_backup_dir == tmp_settings.data_dir / "backups"
    assert tmp_settings.backup_keep == 14


def test_the_backup_settings_come_from_the_environment(
    tmp_settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIN_BACKUP_DIR", str(tmp_path / "elsewhere"))
    monkeypatch.setenv("FIN_BACKUP_KEEP", "3")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.effective_backup_dir == tmp_path / "elsewhere"
    assert settings.backup_keep == 3


def test_a_missing_folder_has_no_backups(tmp_path: Path) -> None:
    assert list_backups(tmp_path / "missing") == []


def test_damage_found_by_the_integrity_check(tmp_path: Path) -> None:
    path = filled(tmp_path / "broken.db")
    damaged(path, path.stat().st_size // 2)
    with pytest.raises(ValueError, match="^broken.db is not a readable finances backup$"):
        check_backup(path)


def test_damage_that_stops_sqlite_reading(tmp_path: Path) -> None:
    path = filled(tmp_path / "broken.db")
    damaged(path, 4096)
    with pytest.raises(ValueError, match="^broken.db is not a readable finances backup$"):
        check_backup(path)


def test_an_empty_alembic_version(tmp_path: Path) -> None:
    path = tmp_path / "empty.db"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.commit()
    with pytest.raises(ValueError, match="^empty.db is not a readable finances backup$"):
        check_backup(path)


def test_a_check_leaves_nothing_beside_the_backup(live: str, tmp_path: Path) -> None:
    folder = tmp_path / "backups"
    made = make_backup(live, folder, 3, MOMENT)
    check_backup(made.path)
    assert sorted(path.name for path in folder.iterdir()) == [NAME]


def test_a_check_changes_none_of_the_files_it_reads(live: str, tmp_path: Path) -> None:
    made = make_backup(live, tmp_path / "backups", 3, MOMENT)
    writer = sqlite3.connect(made.path)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute("CREATE TABLE notes (id INTEGER)")
    writer.commit()
    copy = tmp_path / "copy"
    copy.mkdir()
    for suffix in ("", "-wal", "-shm"):
        shutil.copy(f"{made.path}{suffix}", copy / f"{NAME}{suffix}")
    writer.close()
    kept = (NAME, f"{NAME}-wal")
    before = {name: (copy / name).read_bytes() for name in kept}
    assert check_backup(copy / NAME) == made.check
    assert sorted(path.name for path in copy.iterdir()) == [NAME, f"{NAME}-shm", f"{NAME}-wal"]
    assert {name: (copy / name).read_bytes() for name in kept} == before


def test_a_set_aside_name_that_already_exists(live: str, tmp_path: Path) -> None:
    folder = tmp_path / "backups"
    made = make_backup(live, folder, 3, MOMENT)
    (folder / SET_ASIDE).write_text("x", encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        restore_backup(live, made.path, folder, MOMENT)
    assert str(caught.value) == f"a backup named {SET_ASIDE} already exists; try again in a second"
    assert (folder / SET_ASIDE).read_text(encoding="utf-8") == "x"


@pytest.mark.parametrize("url", ["sqlite://", "postgresql://user@localhost/finances"])
def test_a_restore_needs_a_database_file(live: str, tmp_path: Path, url: str) -> None:
    made = make_backup(live, tmp_path / "backups", 3, MOMENT)
    with pytest.raises(ValueError, match="^backups need a database file$"):
        restore_backup(url, made.path, tmp_path / "backups", MOMENT)
    assert [path.name for path in (tmp_path / "backups").iterdir()] == [NAME]


def test_a_new_copy_that_fails_its_check(
    live: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(path: Path) -> None:
        raise ValueError(f"{path.name} is not a readable finances backup")

    monkeypatch.setattr(backup, "check_backup", refuse)
    folder = tmp_path / "backups"
    with pytest.raises(ValueError) as caught:
        make_backup(live, folder, 3, MOMENT)
    assert str(caught.value) == (
        f"the new backup failed its check: {NAME}.partial is not a readable finances backup"
    )
    assert list(folder.iterdir()) == []


def test_restoring_an_older_backup_asks_for_an_upgrade(
    tmp_settings: Settings, tmp_path: Path
) -> None:
    old = tmp_path / "old.db"
    config = Config()
    config.set_main_option("script_location", str(Path(finances.db.__file__).parent / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{old.as_posix()}")
    command.upgrade(config, "0008")
    result = run("backup", "restore", old, "--yes")
    assert result.exit_code == 0
    assert result.stdout.splitlines() == [
        "Restored old.db.",
        "Run fin db upgrade to bring it up to date.",
    ]


def test_the_command_refuses_a_keep_below_one(
    tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run("db", "upgrade").exit_code == 0
    monkeypatch.setenv("FIN_BACKUP_KEEP", "0")
    get_settings.cache_clear()
    assert failed_cleanly(run("backup", "run"), "keep must be at least 1")


def test_the_command_refuses_a_restore_without_a_database_file(
    tmp_settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run("db", "upgrade").exit_code == 0
    made = make_backup(get_settings().effective_database_url, tmp_path / "made", 3, MOMENT)
    monkeypatch.setenv("FIN_DATABASE_URL", "sqlite://")
    get_settings.cache_clear()
    assert failed_cleanly(
        run("backup", "restore", made.path, "--yes"), "backups need a database file"
    )
