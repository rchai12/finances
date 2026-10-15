"""The backups and set-aside copies as the Backups page shows them."""

from dataclasses import dataclass
from pathlib import Path

from finances.db.backup import taken_at
from finances.views.format import size_text


@dataclass(frozen=True)
class BackupRow:
    file: str
    taken: str
    size: str


def taken_text(path: Path) -> str:
    return taken_at(path).strftime("%Y-%m-%d %H:%M:%S")


def backup_rows(paths: list[Path]) -> list[BackupRow]:
    return [
        BackupRow(path.name, taken_text(path), size_text(path.stat().st_size)) for path in paths
    ]
