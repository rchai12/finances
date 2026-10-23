"""Backup files as data, before any view formats them."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from finances.db.backup import taken_at


@dataclass(frozen=True)
class BackupFile:
    name: str
    taken: datetime
    size: int


def backup_file(path: Path) -> BackupFile:
    return BackupFile(path.name, taken_at(path), path.stat().st_size)


def backup_files(paths: list[Path]) -> list[BackupFile]:
    return [backup_file(path) for path in paths]
