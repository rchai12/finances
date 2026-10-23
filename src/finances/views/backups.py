"""The backups and set-aside copies as the Backups page shows them."""

from dataclasses import dataclass
from datetime import datetime

from finances.analysis.backups import BackupFile
from finances.views.format import size_text


@dataclass(frozen=True)
class BackupRow:
    file: str
    taken: str
    size: str


def taken_text(taken: datetime) -> str:
    return taken.strftime("%Y-%m-%d %H:%M:%S")


def backup_rows(files: list[BackupFile]) -> list[BackupRow]:
    return [BackupRow(item.name, taken_text(item.taken), size_text(item.size)) for item in files]
