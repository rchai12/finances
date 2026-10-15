# Phase 24: backups

## Goal

Years of the household's categorizing live in one SQLite file. After this phase:

- `fin backup run` copies the database safely (SQLite's own backup, safe while the app is running), checks the copy, names it by the time in UTC, and keeps only the newest N;
- `fin backup list` shows the backups, newest first;
- `fin backup restore FILE` checks a backup, asks first, keeps the database it replaces, and puts the backup in;
- a script schedules a daily backup with `launchd`, as the sync script does;
- `docs/backups.md` tells the owner where backups go and why not to put them in a cloud folder.

The backup folder is `FIN_BACKUP_DIR` (default `data/backups`) and N is `FIN_BACKUP_KEEP` (default 14). The app copies nothing off the machine.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `src/finances/config.py`, `src/finances/db/engine.py`, `src/finances/db/migrate.py`, `src/finances/cli/common.py`
- `scripts/install-sync-schedule.sh`, `docs/sync-setup.md`
- `tests/support.py` and `docs/testing.md` rule 8

## Starting state

N is `2578` when Phase 16e is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/config.py` | new settings `backup_dir`, `backup_keep`, and `effective_backup_dir` (R1) |
| `src/finances/db/backup.py` | new (R2 to R6) |
| `src/finances/cli/backup.py` | new (R7 to R9) |
| `src/finances/cli/main.py` | registers `backup` |
| `scripts/critical_modules.txt` | adds `db/backup.py` |
| `scripts/install-backup-schedule.sh`, `scripts/uninstall-backup-schedule.sh` | new: given (executable) |
| `docs/backups.md` | new: given |
| `tests/integration/test_backup.py`, `tests/e2e/test_cli_backup.py` | new: given |
| `tests/conftest.py` | the two new settings are cleared for every test: given change (below) |
| `tests/integration/test_backup_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Encrypting backups, copying them anywhere (a network drive, a cloud service), or compressing them.
- A backup check in `fin doctor` or a stale-backup warning (Phase 25), a web page for backups.
- Restoring part of a database.

## Dependencies

None new: the standard library's `sqlite3` provides the backup.

## Design

```python
# src/finances/config.py: two settings and a property
    backup_dir: Path | None = None
    backup_keep: int = 14

    @property
    def effective_backup_dir(self) -> Path: ...  # backup_dir, or data_dir / "backups"
```

```python
# src/finances/db/backup.py
@dataclass(frozen=True)
class BackupCheck:
    revision: str
    accounts: int
    transactions: int


@dataclass(frozen=True)
class BackupResult:
    path: Path
    check: BackupCheck
    kept: int            # backups in the folder after pruning, this one included
    removed: list[Path]  # oldest first


@dataclass(frozen=True)
class RestoreResult:
    check: BackupCheck
    replaced: Path | None  # where the replaced database was kept, or None when there was none
    needs_upgrade: bool    # the backup's revision is not the newest


def backup_name(moment: datetime) -> str: ...
def list_backups(folder: Path) -> list[Path]: ...
def check_backup(path: Path) -> BackupCheck: ...
def make_backup(url: str, folder: Path, keep: int, moment: datetime) -> BackupResult: ...
def restore_backup(url: str, path: Path, folder: Path, moment: datetime) -> RestoreResult: ...
```

A **backup name** is `finances-YYYYMMDD-HHMMSS.db` with the moment in UTC; a **set-aside name** is `finances-YYYYMMDD-HHMMSS-before-restore.db`. Only files whose whole name is a backup name count as backups; nothing else in the folder is ever deleted.

Messages, in full. Each is a `ValueError`; the command prints `Error: <message>` and exits with code 1. NAME is the file's name only, never its folder.

| When | Message |
|---|---|
| the database URL is not a SQLite file (no file name, or `:memory:`) | `backups need a database file` |
| `keep` below 1 | `keep must be at least 1` |
| the backup's or set-aside's name is already in the folder | `a backup named NAME already exists; try again in a second` |
| a file that is missing, not SQLite, damaged, or has no `alembic_version` row | `NAME is not a readable finances backup` |
| a revision this app's migrations do not know | `NAME comes from a newer version of the app (revision R)` |
| the new copy fails its check | `the new backup failed its check: MESSAGE` (the check's message), and the partial file is deleted |

## Requirements

### Part 1: the backup module

- **R1.** `effective_backup_dir` is `backup_dir` when set, otherwise `data_dir / "backups"`. Both settings come from `FIN_BACKUP_DIR` and `FIN_BACKUP_KEEP` like the others.
- **R2.** `backup_name` converts the moment to UTC first. `list_backups` returns the folder's backups, newest first by name, or nothing when the folder does not exist.
- **R3.** `check_backup` refuses a path that is not a file without creating anything, then opens it **read-only** (`sqlite3` with `file:...?mode=ro`, `uri=True`) and runs `PRAGMA integrity_check` (must be `ok`), reads the single `alembic_version` row, checks that the revision is one this app's migrations know (the newer-version message otherwise), and counts the rows of `accounts` and `transactions`. Any `sqlite3.Error` becomes the not-readable message.
- **R4.** `make_backup` checks the URL, then `keep`, before touching the folder; creates the folder; refuses a name already there; copies the live database with `sqlite3.Connection.backup` into the folder under the name plus `.partial`; checks that file with `check_backup`; renames it to the backup name; then deletes the oldest backups beyond `keep`.
- **R5.** `restore_backup` checks the backup first (nothing changes when it is refused). When the live database file exists, it copies it with `sqlite3.Connection.backup` into the folder under the set-aside name (creating the folder). It then copies the backup into the live database with `sqlite3.Connection.backup` (creating the live file's folder when needed). `needs_upgrade` is true when the backup's revision is not `head_revision()`.
- **R6.** This module is the only place that uses `sqlite3` directly; it is SQLite-only by nature, as the app is. It logs no paths or counts at INFO or above.

### Part 2: the commands

- **R7.** `fin backup run` checks the schema as other commands do, then calls `make_backup` with the configured URL, `effective_backup_dir`, `backup_keep`, and the current UTC time, and prints `Backup written: PATH (A accounts, T transactions).` (PATH absolute and resolved), then `Backups kept: K. Removed: R.`
- **R8.** `fin backup list` prints a table with columns `File` and `Taken (UTC)` (`YYYY-MM-DD HH:MM:SS`, read from the name), newest first, or `No backups.`
- **R9.** `fin backup restore FILE [--yes]` does not need a current schema. It calls `check_backup` (refusing as above); without `--yes` it asks `Replace the database with NAME?` (default no), and on no prints `Nothing restored.` and exits with code 0. Then it calls `restore_backup` with the current UTC time and prints `Restored NAME.`, then `The database it replaced is kept as SET-ASIDE-NAME.` when there was one, then `Run fin db upgrade to bring it up to date.` when `needs_upgrade`.

### Part 3: schedule and docs

- **R10.** The given scripts and `docs/backups.md` are added exactly as shown, the scripts executable (`chmod +x`).

## Given files

`scripts/install-backup-schedule.sh`

```sh
#!/bin/bash
# Run `fin backup run` every day at a set time, as the logged-in user, with launchd.
#
#   scripts/install-backup-schedule.sh              daily at 02:00
#   scripts/install-backup-schedule.sh 3 30         daily at 03:30
#   scripts/install-backup-schedule.sh 2 0 --now    install, then run once straight away
#
# Backups go to FIN_BACKUP_DIR (data/backups unless set; see docs/backups.md). Paths are worked
# out from where this repository is, so the same command works on any Mac. Output goes to
# data/logs/backup.log (data/ is never committed). Installing again replaces the earlier job.
# Remove it with scripts/uninstall-backup-schedule.sh.
set -euo pipefail

LABEL="local.finances.backup"
HOUR="${1:-2}"
MINUTE="${2:-0}"
RUN_NOW="${3:-}"

if ! [[ "$HOUR" =~ ^[0-9]{1,2}$ ]] || ((10#$HOUR > 23)); then
    echo "Error: the hour must be 0 to 23" >&2
    exit 1
fi
if ! [[ "$MINUTE" =~ ^[0-9]{1,2}$ ]] || ((10#$MINUTE > 59)); then
    echo "Error: the minute must be 0 to 59" >&2
    exit 1
fi
if [[ -n "$RUN_NOW" && "$RUN_NOW" != "--now" ]]; then
    echo "Error: the only third argument is --now" >&2
    exit 1
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIN="$REPO/.venv/bin/fin"
LOGS="$REPO/data/logs"
AGENTS="$HOME/Library/LaunchAgents"
PLIST="$AGENTS/$LABEL.plist"
DOMAIN="gui/$(id -u)"

if [[ ! -x "$FIN" ]]; then
    echo "Error: $FIN not found; install the project first" >&2
    exit 1
fi
mkdir -p "$LOGS" "$AGENTS"

cat >"$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$FIN</string>
    <string>backup</string>
    <string>run</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$REPO</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>$((10#$HOUR))</integer>
    <key>Minute</key>
    <integer>$((10#$MINUTE))</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$LOGS/backup.log</string>
  <key>StandardErrorPath</key>
  <string>$LOGS/backup.log</string>
</dict>
</plist>
PLIST
plutil -lint "$PLIST" >/dev/null

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
printf 'Scheduled fin backup run daily at %02d:%02d (log: %s)\n' "$((10#$HOUR))" "$((10#$MINUTE))" "$LOGS/backup.log"

if [[ "$RUN_NOW" == "--now" ]]; then
    launchctl kickstart "$DOMAIN/$LABEL"
    echo "Started one run now; see the log when it finishes."
fi
```

`scripts/uninstall-backup-schedule.sh`

```sh
#!/bin/bash
# Stop the daily `fin backup run` job and remove it. The backups and the log are kept.
set -euo pipefail

LABEL="local.finances.backup"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [[ -f "$PLIST" ]]; then
    rm "$PLIST"
    echo "Removed the daily backup job."
else
    echo "No daily backup job was installed."
fi
```

`docs/backups.md`

```markdown
# Backups

Everything the household has entered or the app has worked out (accounts, transactions, categories, rules, transfers, mappings) lives in one file, `data/finances.db`. Back it up.

## Making a backup

```
.venv/bin/fin backup run
```

It copies the database with SQLite's own backup, which is safe while the app is running, checks the copy (it opens, its schema is one this app knows, and it can count the accounts and transactions), and only then gives it its name, `finances-YYYYMMDD-HHMMSS.db` (the time in UTC). It keeps the newest 14 and deletes older ones; files with other names are never touched.

`.venv/bin/fin backup list` shows the backups, newest first.

## Where backups go

`data/backups/` unless `FIN_BACKUP_DIR` says otherwise; `FIN_BACKUP_KEEP` sets how many to keep. Both can go in `.env`.

A backup on the same disk protects against mistakes, not against losing the disk. Point `FIN_BACKUP_DIR` at a drive you control (an external disk, preferably encrypted) for that. A backup holds every transaction in plain form, like the database itself, so keep it off cloud folders and email, for the same reason the database is (see `docs/architecture.md`, Privacy boundary). The app never copies anything off the machine.

## Every day

```
scripts/install-backup-schedule.sh              # daily at 02:00
scripts/install-backup-schedule.sh 3 30         # or another time
scripts/install-backup-schedule.sh 2 0 --now    # install, then run once straight away to test
```

Output goes to `data/logs/backup.log`. To stop it: `scripts/uninstall-backup-schedule.sh`. The Mac must be on and you logged in; a run missed while asleep happens when it wakes.

## Restoring

Stop `fin web serve` first. Then:

```
.venv/bin/fin backup restore data/backups/finances-20261015-020000.db
```

It checks the backup, asks before replacing anything, keeps the database it replaces as `finances-YYYYMMDD-HHMMSS-before-restore.db` in the backup folder (these are never deleted for you), and copies the backup in. A backup from an older version of the app is restored as it is; run `.venv/bin/fin db upgrade` afterwards, as the command says.

On a new Mac, restoring a backup is another way to bring the data over (see `docs/sync-setup.md`, "Moving to another Mac"): install the project, restore, then `fin db upgrade`. SimpleFIN links are not in the database and must be made again.
```

## Given tests

18 tests in two files. The end-to-end file imports from `tests/support.py`.

`tests/integration/test_backup.py`

```python
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
```

`tests/e2e/test_cli_backup.py`

```python
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
        ["File", "Taken (UTC)"],
        ["finances-20261016-020000.db", "2026-10-16 02:00:00"],
        ["finances-20261015-143005.db", "2026-10-15 14:30:05"],
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
```

The change to `tests/conftest.py`, exactly this diff, so no test reads the owner's own backup settings:

```diff
diff --git a/tests/conftest.py b/tests/conftest.py
index f7f6a64..9fbbdde 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -30,7 +30,14 @@ settings.register_profile(
 )
 settings.load_profile("finances")
 
-_ENV_KEYS = ("FIN_ENVIRONMENT", "FIN_DATA_DIR", "FIN_DATABASE_URL", "FIN_LOG_LEVEL")
+_ENV_KEYS = (
+    "FIN_ENVIRONMENT",
+    "FIN_DATA_DIR",
+    "FIN_DATABASE_URL",
+    "FIN_LOG_LEVEL",
+    "FIN_BACKUP_DIR",
+    "FIN_BACKUP_KEEP",
+)
 
 _TERMINAL_KEYS = ("FORCE_COLOR", "NO_COLOR", "TTY_COMPATIBLE", "TTY_INTERACTIVE")
 
```

## Tests to write

`tests/integration/test_backup_more.py` (`db/backup.py` becomes a critical module: cover every branch):

- the settings: the default folder, `FIN_BACKUP_DIR`, `FIN_BACKUP_KEEP`;
- `list_backups` of a missing folder;
- `check_backup` of a damaged file (a real database with bytes overwritten in its middle) and of a database whose `alembic_version` is empty;
- `check_backup` creates no file next to the backup (no `-journal` or `-wal`);
- a set-aside name that already exists;
- a new copy that fails its check (for example by replacing `check_backup` for the test): the message, and neither a `.partial` file nor a backup file left;
- `fin backup restore` of a backup from an older revision prints the upgrade line.

## Rules for this phase

- No network, no copy off the machine; the folder is whatever the owner configured.
- `PATH` appears only in the command's own output, never in logs at INFO or above.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/integration/test_backup.py tests/e2e/test_cli_backup.py`, 18 tests;
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.db.backup --cov=finances.cli.backup --cov=finances.config --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "^ *(import sqlite3|from sqlite3)" -- src` (only `src/finances/db/backup.py` may appear) and `git grep -n --untracked -E "log(ger)?\.(info|warning|error|critical)" -- src/finances/db/backup.py src/finances/cli/backup.py` (no output).

## Report

As in `docs/phase-conventions.md`, headed `## Phase 24: backups (YYYY-MM-DD)`.
