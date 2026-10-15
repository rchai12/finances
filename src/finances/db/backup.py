"""Checked copies of the SQLite database, kept in a folder, and restoring one of them.

This is the only module that uses `sqlite3` directly: SQLite's online backup copies a database
safely while the app has it open.
"""

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

from finances.db.migrate import MIGRATIONS, head_revision

_BACKUP_NAME = re.compile(r"finances-[0-9]{8}-[0-9]{6}\.db")
_STAMP = "%Y%m%d-%H%M%S"


@dataclass(frozen=True)
class BackupCheck:
    revision: str
    accounts: int
    transactions: int


@dataclass(frozen=True)
class BackupResult:
    path: Path
    check: BackupCheck
    kept: int
    removed: list[Path]


@dataclass(frozen=True)
class RestoreResult:
    check: BackupCheck
    replaced: Path | None
    needs_upgrade: bool


def backup_name(moment: datetime) -> str:
    return f"finances-{moment.astimezone(UTC).strftime(_STAMP)}.db"


def _set_aside_name(moment: datetime) -> str:
    return f"finances-{moment.astimezone(UTC).strftime(_STAMP)}-before-restore.db"


def list_backups(folder: Path) -> list[Path]:
    """The folder's backups, newest first; nothing when the folder does not exist."""
    if not folder.is_dir():
        return []
    found = [path for path in folder.iterdir() if _BACKUP_NAME.fullmatch(path.name)]
    return sorted(found, key=lambda path: path.name, reverse=True)


def _read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def _known_revisions() -> set[str]:
    return {script.revision for script in ScriptDirectory(str(MIGRATIONS)).walk_revisions()}


def check_backup(path: Path) -> BackupCheck:
    """Open the file read-only and check that it is a whole finances database this app knows."""
    unreadable = ValueError(f"{path.name} is not a readable finances backup")
    if not path.is_file():
        raise unreadable
    try:
        with closing(_read_only(path)) as connection:
            if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise unreadable
            versions = connection.execute("SELECT version_num FROM alembic_version").fetchall()
            if len(versions) != 1:
                raise unreadable
            revision = versions[0][0]
            if revision not in _known_revisions():
                raise ValueError(
                    f"{path.name} comes from a newer version of the app (revision {revision})"
                )
            accounts = connection.execute("SELECT count(*) FROM accounts").fetchone()[0]
            transactions = connection.execute("SELECT count(*) FROM transactions").fetchone()[0]
    except sqlite3.Error:
        raise unreadable from None
    return BackupCheck(revision=revision, accounts=accounts, transactions=transactions)


def _database_file(url: str) -> Path:
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite" or parsed.database in (None, "", ":memory:"):
        raise ValueError("backups need a database file")
    return Path(parsed.database)


def _refuse_existing(path: Path) -> None:
    if path.exists():
        raise ValueError(f"a backup named {path.name} already exists; try again in a second")


def _copy(source: Path, target: Path) -> None:
    with closing(_read_only(source)) as reading, closing(sqlite3.connect(target)) as writing:
        reading.backup(writing)


def make_backup(url: str, folder: Path, keep: int, moment: datetime) -> BackupResult:
    """Copy the database into the folder, check the copy, then keep only the newest `keep`."""
    live = _database_file(url)
    if keep < 1:
        raise ValueError("keep must be at least 1")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / backup_name(moment)
    _refuse_existing(path)
    partial = path.with_name(f"{path.name}.partial")
    _copy(live, partial)
    try:
        check = check_backup(partial)
    except ValueError as failed:
        partial.unlink()
        raise ValueError(f"the new backup failed its check: {failed}") from None
    partial.rename(path)
    backups = list_backups(folder)
    removed = list(reversed(backups[keep:]))
    for old in removed:
        old.unlink()
    return BackupResult(path=path, check=check, kept=len(backups) - len(removed), removed=removed)


def restore_backup(url: str, path: Path, folder: Path, moment: datetime) -> RestoreResult:
    """Put the backup in place of the database, first keeping the database it replaces."""
    check = check_backup(path)
    live = _database_file(url)
    replaced = None
    if live.exists():
        replaced = folder / _set_aside_name(moment)
        _refuse_existing(replaced)
        folder.mkdir(parents=True, exist_ok=True)
        _copy(live, replaced)
    live.parent.mkdir(parents=True, exist_ok=True)
    _copy(path, live)
    return RestoreResult(
        check=check, replaced=replaced, needs_upgrade=check.revision != head_revision()
    )
