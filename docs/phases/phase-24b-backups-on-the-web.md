# Phase 24b: backups on the web

## Goal

The household manages its backups from the browser. After this phase the menu has **Backups**: one page with **Back up now**, the backups and the copies set aside by restores (when each was taken and its size), and for each a **Restore** and a **Delete** link.

- **Delete** opens a page naming the file; a button deletes it.
- **Restore** opens a page saying what the backup holds; the owner types the backup's name and presses Restore. The current database is always set aside first and listed, so a restore can be undone by restoring that copy. While a restore runs, the site holds new requests, so the server need not be stopped.
- Only files in the backup folder with a backup's or a set-aside's name can be restored or deleted; no path, no upload, no download.

Everything goes through Phase 24's `db/backup.py`. Limiting restore and delete to the Mac itself comes with remote access (Phase 20).

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `docs/phases/phase-24-backups.md` and `src/finances/db/backup.py` (a critical module), `src/finances/cli/backup.py`
- `src/finances/web/app.py`: `_engine`, `_reading`, `refused`, `_not_migrated`, how a refused form is shown again
- `tests/support.py`

## Starting state

N is `2611` when Phase 24 is the last phase built.

## Scope

| Path | What changes |
|---|---|
| `src/finances/db/backup.py` | new: `list_set_asides`, `find_backup`, `delete_backup`, `taken_at` (R1 to R3) |
| `src/finances/views/format.py` | new: `size_text` (R4) |
| `src/finances/views/backups.py` | new (R4) |
| `src/finances/web/app.py` | `_now`, the restore gate, four notices, the routes of Part 2 |
| `src/finances/web/templates/layout.html` | replaced: given |
| `src/finances/web/templates/backups.html`, `backup_confirm.html` | new: given |
| `docs/backups.md` | replaced: given |
| `tests/integration/test_web_backups.py` | new: given |
| `tests/integration/test_backups_page_more.py` | new: yours ("Tests to write") |
| `docs/progress.md` | one new entry |

## Out of scope

- Downloading or uploading a backup; restoring from a path; changing the folder or `keep` from the web.
- Running `fin db upgrade` from the web.
- Limiting delete and restore to the Mac itself, or asking for a password again (Phase 20).

## Dependencies

None new. No migration.

## Design

```python
# src/finances/db/backup.py
def list_set_asides(folder: Path) -> list[Path]: ...       # newest first; nothing when no folder
def find_backup(folder: Path, name: str) -> Path: ...       # a backup or set-aside file by its name
def delete_backup(folder: Path, name: str) -> Path: ...     # find_backup, then delete it
def taken_at(path: Path) -> datetime: ...                    # from the name, in UTC

# src/finances/views/format.py
def size_text(size: int) -> str: ...

# src/finances/views/backups.py
@dataclass(frozen=True)
class BackupRow:
    file: str
    taken: str   # "YYYY-MM-DD HH:MM:SS"
    size: str    # size_text


def backup_rows(paths: list[Path]) -> list[BackupRow]: ...
def taken_text(path: Path) -> str: ...
```

`size_text`: below 1024 bytes `N B`; below 1024 × 1024 `N KB` (whole kilobytes, rounded down); otherwise `N.N MB` (megabytes rounded half up to one decimal, exactly, without floats).

Notices added to `NOTICES`, in full:

| Key | Text |
|---|---|
| `backed-up` | `Backup written.` |
| `deleted` | `Backup deleted.` |
| `restored` | `Backup restored. The database it replaced is listed under Set aside before a restore.` |
| `restored-old` | `Backup restored. It comes from an older version of the app: run fin db upgrade in the terminal before using the other pages.` |

New messages, in full (each a `ValueError`; every other message is Phase 24's):

| When | Message |
|---|---|
| `find_backup` with a name that is not wholly a backup or set-aside name, or no such file in the folder | `NAME is not a backup in the folder` (NAME as sent) |
| the typed name differs from the backup's name in any way | `type the backup's name to confirm` |

## Requirements

### Part 1: the module and views

- **R1.** `list_set_asides` is `list_backups` for set-aside names. `taken_at` reads the time from a backup or set-aside name, in UTC.
- **R2.** `find_backup` checks the name against both patterns (the whole name, as sent) before touching the file system, then that `folder / name` is a file; `delete_backup` deletes it and returns its path. Nothing else is ever deleted.
- **R3.** `db/backup.py` stays fully covered (it is a critical module).
- **R4.** `size_text` as above. `backup_rows` gives each path's name, `taken_text`, and `size_text` of its size.

### Part 2: the pages

Every `POST` checks the origin and the form token as today. Only `POST /backups/run` also needs a current database (`503` otherwise, as other forms); the other routes of this phase work on any database, including one just restored from an older version.

- **R5.** `GET /backups` renders `backups.html` with `folder` (the resolved backup folder, as text), `keep` (`backup_keep`), `backups` (`backup_rows(list_backups)`), `set_asides` (`backup_rows(list_set_asides)`), and `error`.
- **R6.** `POST /backups/run`: `make_backup` with the configured URL, folder, `keep`, and `_now()`. Done: `/backups?notice=backed-up`. Refused (its `ValueError`): the Backups page with status `400`.
- **R7.** `GET /backups/delete?name=NAME` renders `backup_confirm.html` with `action` `delete`, `name`, and `taken` (`taken_text`). `POST /backups/delete` (`name`): `delete_backup`. Done: `/backups?notice=deleted`. A name `find_backup` refuses, on either route: the Backups page with status `400` and the message.
- **R8.** `GET /backups/restore?name=NAME`: `find_backup`, then `check_backup`; renders `backup_confirm.html` with `action` `restore`, `name`, `taken`, and `check`. `POST /backups/restore` (`name`, `confirm`): `find_backup`, then `check_backup`; then `confirm` must equal the name exactly, else the confirmation page again with status `400` and `type the backup's name to confirm`; then `restore_backup` with `_now()` while holding the restore gate. Done: `/backups?notice=restored`, or `notice=restored-old` when `needs_upgrade`. Any other refusal (`find_backup`, `check_backup`, `restore_backup`): the Backups page with status `400` and the message.
- **R9.** `_now()` is a module-level function in `web/app.py` returning the current UTC time; every route of this phase reads the time through it (the given tests replace it).
- **R10.** The **restore gate** is a module-level `threading.Lock` in `web/app.py`. `POST /backups/restore` holds it while `restore_backup` runs; `_engine()` waits for it (acquires and releases it) before opening an engine, so requests that arrive during a restore wait for it to end. Requests already running finish first: SQLite's backup retries while the database is busy.

## Given templates and docs

`src/finances/web/templates/layout.html`

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}Finances{% endblock %}</title>
<link rel="stylesheet" href="/static/app.css">
</head>
<body>
<nav>
  <span class="brand">Finances</span>
  <a href="/accounts"{% if section == "accounts" %} aria-current="page"{% endif %}>Accounts</a>
  <a href="/people"{% if section == "people" %} aria-current="page"{% endif %}>People</a>
  <a href="/transactions"{% if section == "transactions" %} aria-current="page"{% endif %}>Transactions</a>
  <a href="/categories"{% if section == "categories" %} aria-current="page"{% endif %}>Categories</a>
  <a href="/transfers"{% if section == "transfers" %} aria-current="page"{% endif %}>Transfers</a>
  <a href="/reports"{% if section == "reports" %} aria-current="page"{% endif %}>Reports</a>
  <a href="/insights"{% if section == "insights" %} aria-current="page"{% endif %}>Insights</a>
  <a href="/sync"{% if section == "sync" %} aria-current="page"{% endif %}>SimpleFIN</a>
  <a href="/backups"{% if section == "backups" %} aria-current="page"{% endif %}>Backups</a>
</nav>
<main>
{% block content %}{% endblock %}
</main>
</body>
</html>
```

`src/finances/web/templates/backups.html`

```html
{% extends "layout.html" %}
{% block title %}Backups · Finances{% endblock %}
{% block content %}
<h1>Backups</h1>
{% include "messages.html" %}
<p class="hint">Kept in {{ folder }}: the newest {{ keep }} backups. Copies set aside by a restore are never deleted for you. Backups are not downloaded through the browser; see docs/backups.md.</p>
<form method="post" action="/backups/run" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <button type="submit">Back up now</button>
</form>
<h2>Backups</h2>
{% if backups %}
<table>
<thead><tr><th>File</th><th>Taken (UTC)</th><th class="amount">Size</th><th></th></tr></thead>
<tbody>
{% for row in backups %}<tr><td>{{ row.file }}</td><td>{{ row.taken }}</td><td class="amount">{{ row.size }}</td><td><a href="/backups/restore?name={{ row.file|urlencode }}">Restore</a> <a href="/backups/delete?name={{ row.file|urlencode }}">Delete</a></td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No backups.</p>
{% endif %}
<h2>Set aside before a restore</h2>
{% if set_asides %}
<table>
<thead><tr><th>File</th><th>Taken (UTC)</th><th class="amount">Size</th><th></th></tr></thead>
<tbody>
{% for row in set_asides %}<tr><td>{{ row.file }}</td><td>{{ row.taken }}</td><td class="amount">{{ row.size }}</td><td><a href="/backups/restore?name={{ row.file|urlencode }}">Restore</a> <a href="/backups/delete?name={{ row.file|urlencode }}">Delete</a></td></tr>
{% endfor %}</tbody>
</table>
{% else %}
<p class="empty">No set-aside copies.</p>
{% endif %}
{% endblock %}
```

`src/finances/web/templates/backup_confirm.html`

```html
{% extends "layout.html" %}
{% block title %}{{ "Restore" if action == "restore" else "Delete" }} a backup · Finances{% endblock %}
{% block content %}
<h1>{{ "Restore" if action == "restore" else "Delete" }} a backup</h1>
{% include "messages.html" %}
{% if action == "restore" %}
<p class="summary">Restore {{ name }}: {{ check.accounts }} accounts and {{ check.transactions }} transactions, taken {{ taken }} UTC.</p>
<p class="hint">The current database is set aside first and appears in the list, so restoring it undoes this. Type the backup's name to confirm.</p>
<form method="post" action="/backups/restore" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <input type="hidden" name="name" value="{{ name }}">
  <label>Name <input name="confirm" value="" autocomplete="off" required></label>
  <button type="submit">Restore</button>
</form>
{% else %}
<p class="summary">Delete {{ name }}, taken {{ taken }} UTC? This cannot be undone.</p>
<form method="post" action="/backups/delete" class="fields">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <input type="hidden" name="name" value="{{ name }}">
  <button type="submit">Delete</button>
</form>
{% endif %}
<p><a href="/backups">Cancel</a></p>
{% endblock %}
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

## On the web

The **Backups** page (`fin web serve`, then Backups in the menu) does the same: **Back up now**, the list with each file's size, **Delete** (after a confirmation page), and **Restore** (after typing the backup's name). The web restore pauses the site's other requests while it works, so the server need not be stopped. Backups are not downloaded through the browser: a full copy in the downloads folder, often synced to the cloud, would break the rule below.

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

From the terminal, stop `fin web serve` first. Then:

```
.venv/bin/fin backup restore data/backups/finances-20261015-020000.db
```

It checks the backup, asks before replacing anything, keeps the database it replaces as `finances-YYYYMMDD-HHMMSS-before-restore.db` in the backup folder (these are never deleted for you), and copies the backup in. A backup from an older version of the app is restored as it is; run `.venv/bin/fin db upgrade` afterwards, as the command says.

On a new Mac, restoring a backup is another way to bring the data over (see `docs/sync-setup.md`, "Moving to another Mac"): install the project, restore, then `fin db upgrade`. SimpleFIN links are not in the database and must be made again.
```

## Given tests

`tests/integration/test_web_backups.py` (35 tests). It replaces `finances.web.app._now` with fixed moments, so every file name it expects is literal.

```python
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import finances.db
from finances.config import Settings
from finances.db.backup import make_backup
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account
from finances.views.format import size_text
from finances.web.app import create_app
from tests.support import WEB_NOT_MIGRATED, WEB_PORT, Page, page, post, texts

FIRST = "finances-20261015-143005.db"
SECOND = "finances-20261016-020000.db"
SET_ASIDE = "finances-20261015-150005-before-restore.db"
HEADINGS = ["File", "Taken (UTC)", "Size", ""]
NOT_A_BACKUP = "{} is not a backup in the folder"
NOW = datetime(2026, 10, 17, 9, 0, 0, tzinfo=UTC)
REPLACED = "finances-20261017-090000-before-restore.db"


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


def add_transactions(count: int, start: int) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        for number in range(start, start + count):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, 1),
                    amount_cents=-100,
                    description="ACME COFFEE",
                    source="statement",
                    fingerprint=f"b{number:02d}".ljust(64, "0"),
                )
            )
    engine.dispose()


def transactions() -> int:
    engine = get_engine()
    with session_scope(engine) as session:
        found = session.scalar(select(func.count()).select_from(TransactionRow))
    engine.dispose()
    return found


@pytest.fixture
def home(client: TestClient, tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Two accounts and three transactions; backups FIRST and SECOND; a three-byte file with a
    set-aside name; a note that is not a backup. The page's clock reads NOW. The page has been
    opened once."""
    monkeypatch.setattr("finances.web.app._now", lambda: NOW)
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        create_account(session, "Test Checking", "Test Bank", "checking")
    engine.dispose()
    add_transactions(3, 1)
    folder = tmp_settings.effective_backup_dir
    url = tmp_settings.effective_database_url
    make_backup(url, folder, 14, datetime(2026, 10, 15, 14, 30, 5, tzinfo=UTC))
    make_backup(url, folder, 14, datetime(2026, 10, 16, 2, 0, 0, tzinfo=UTC))
    (folder / SET_ASIDE).write_bytes(b"abc")
    (folder / "notes.txt").write_text("keep me", encoding="utf-8")
    client.get("/backups")
    return client


def names(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


# The page


def test_the_menu_has_backups(home: TestClient) -> None:
    html = home.get("/backups").text
    assert 'href="/backups" aria-current="page">Backups</a>' in html
    assert html.count('aria-current="page"') == 1
    assert 'href="/backups">Backups</a>' in home.get("/accounts").text
    assert "<script" not in html


def test_the_page_lists_backups_and_set_aside_copies(
    home: TestClient, tmp_settings: Settings
) -> None:
    found = page(home, "/backups")
    folder = tmp_settings.effective_backup_dir
    size = size_text((folder / SECOND).stat().st_size)
    assert found.rows == [
        HEADINGS,
        [SECOND, "2026-10-16 02:00:00", size, "Restore Delete"],
        [
            FIRST,
            "2026-10-15 14:30:05",
            size_text((folder / FIRST).stat().st_size),
            "Restore Delete",
        ],
        HEADINGS,
        [SET_ASIDE, "2026-10-15 15:00:05", "3 B", "Restore Delete"],
    ]
    assert [link for link in found.links if link.startswith("/backups/")] == [
        f"/backups/restore?name={SECOND}",
        f"/backups/delete?name={SECOND}",
        f"/backups/restore?name={FIRST}",
        f"/backups/delete?name={FIRST}",
        f"/backups/restore?name={SET_ASIDE}",
        f"/backups/delete?name={SET_ASIDE}",
    ]
    assert texts(found, "hint") == [
        f"Kept in {folder.resolve()}: the newest 14 backups. Copies set aside by a restore are"
        " never deleted for you. Backups are not downloaded through the browser; see"
        " docs/backups.md."
    ]


def test_a_new_database_has_no_backups(client: TestClient) -> None:
    found = page(client, "/backups")
    assert ("empty", "No backups.") in found.paragraphs
    assert ("empty", "No set-aside copies.") in found.paragraphs


@pytest.mark.parametrize(
    ("size", "text"),
    [
        (0, "0 B"),
        (1023, "1023 B"),
        (1024, "1 KB"),
        (1048575, "1023 KB"),
        (1048576, "1.0 MB"),
        (1572864, "1.5 MB"),
        (1625292, "1.5 MB"),
        (1625293, "1.6 MB"),
    ],
)
def test_size_text(size: int, text: str) -> None:
    assert size_text(size) == text


# Backing up and deleting


def test_back_up_now(home: TestClient, tmp_settings: Settings) -> None:
    response = post(home, "/backups/run")
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/backups?notice=backed-up",
    )
    assert ("notice", "Backup written.") in page(home, response.headers["location"]).paragraphs
    assert names(tmp_settings.effective_backup_dir) == [
        FIRST,
        SET_ASIDE,
        SECOND,
        "finances-20261017-090000.db",
        "notes.txt",
    ]


def test_back_up_now_needs_a_migrated_database(client: TestClient) -> None:
    client.get("/backups")
    response = post(client, "/backups/run")
    assert response.status_code == 503
    assert ("error", WEB_NOT_MIGRATED) in Page(response.text).paragraphs


def test_delete_after_confirming(home: TestClient, tmp_settings: Settings) -> None:
    found = page(home, f"/backups/delete?name={FIRST}")
    assert texts(found, "summary") == [
        f"Delete {FIRST}, taken 2026-10-15 14:30:05 UTC? This cannot be undone."
    ]
    assert found.find("/backups/delete")["inputs"]["name"] == ("hidden", FIRST)
    assert "/backups" in found.links
    response = post(home, "/backups/delete", name=FIRST)
    assert (response.status_code, response.headers["location"]) == (303, "/backups?notice=deleted")
    assert ("notice", "Backup deleted.") in page(home, response.headers["location"]).paragraphs
    assert names(tmp_settings.effective_backup_dir) == [SET_ASIDE, SECOND, "notes.txt"]


@pytest.mark.parametrize(
    "name", ["notes.txt", "../finances.db", "finances-20990101-000000.db", "", FIRST.upper()]
)
def test_only_backups_in_the_folder_can_be_deleted(
    home: TestClient, tmp_settings: Settings, name: str
) -> None:
    before = names(tmp_settings.effective_backup_dir)
    for response in (
        home.get(f"/backups/delete?name={name}"),
        post(home, "/backups/delete", name=name),
    ):
        assert response.status_code == 400
        assert ("error", NOT_A_BACKUP.format(name)) in Page(response.text).paragraphs
    assert names(tmp_settings.effective_backup_dir) == before
    assert (tmp_settings.data_dir / "finances.db").exists()


@pytest.mark.parametrize("path", ["/backups/run", "/backups/delete", "/backups/restore"])
def test_a_form_without_the_token_is_refused(home: TestClient, path: str) -> None:
    response = home.post(path, data={"name": FIRST, "confirm": FIRST}, follow_redirects=False)
    assert (response.status_code, response.text) == (403, "Bad form token")


# Restoring


def test_restore_after_typing_the_name(home: TestClient, tmp_settings: Settings) -> None:
    add_transactions(1, 50)
    found = page(home, f"/backups/restore?name={FIRST}")
    assert texts(found, "summary") == [
        f"Restore {FIRST}: 2 accounts and 3 transactions, taken 2026-10-15 14:30:05 UTC."
    ]
    form = found.find("/backups/restore")
    assert (form["inputs"]["name"], form["inputs"]["confirm"]) == (("hidden", FIRST), ("text", ""))
    response = post(home, "/backups/restore", name=FIRST, confirm=FIRST)
    assert (response.status_code, response.headers["location"]) == (303, "/backups?notice=restored")
    shown = page(home, response.headers["location"])
    assert (
        "notice",
        "Backup restored. The database it replaced is listed under Set aside before a restore.",
    ) in shown.paragraphs
    assert transactions() == 3
    assert [row[0] for row in shown.rows[shown.rows.index(HEADINGS, 1) + 1 :]] == [
        REPLACED,
        SET_ASIDE,
    ]


def test_a_restore_can_be_undone(home: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    add_transactions(1, 50)
    post(home, "/backups/restore", name=FIRST, confirm=FIRST)
    assert transactions() == 3
    monkeypatch.setattr(
        "finances.web.app._now", lambda: datetime(2026, 10, 17, 9, 0, 1, tzinfo=UTC)
    )
    response = post(home, "/backups/restore", name=REPLACED, confirm=REPLACED)
    assert (response.status_code, response.headers["location"]) == (303, "/backups?notice=restored")
    assert transactions() == 4


def test_two_restores_in_one_second(home: TestClient) -> None:
    post(home, "/backups/restore", name=FIRST, confirm=FIRST)
    response = post(home, "/backups/restore", name=SECOND, confirm=SECOND)
    assert response.status_code == 400
    assert (
        "error",
        f"a backup named {REPLACED} already exists; try again in a second",
    ) in Page(response.text).paragraphs


@pytest.mark.parametrize("typed", ["", "yes", FIRST.upper(), f" {FIRST}", SECOND])
def test_restore_needs_the_name_typed_exactly(
    home: TestClient, tmp_settings: Settings, typed: str
) -> None:
    before = names(tmp_settings.effective_backup_dir)
    response = post(home, "/backups/restore", name=FIRST, confirm=typed)
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", "type the backup's name to confirm") in found.paragraphs
    assert found.find("/backups/restore")["inputs"]["name"] == ("hidden", FIRST)
    assert names(tmp_settings.effective_backup_dir) == before


@pytest.mark.parametrize("name", ["notes.txt", "../finances.db", "finances-20990101-000000.db"])
def test_only_backups_in_the_folder_can_be_restored(home: TestClient, name: str) -> None:
    for response in (
        home.get(f"/backups/restore?name={name}"),
        post(home, "/backups/restore", name=name, confirm=name),
    ):
        assert response.status_code == 400
        assert ("error", NOT_A_BACKUP.format(name)) in Page(response.text).paragraphs
    assert transactions() == 3


def test_a_file_that_is_not_a_readable_backup(home: TestClient) -> None:
    response = home.get(f"/backups/restore?name={SET_ASIDE}")
    assert response.status_code == 400
    assert ("error", f"{SET_ASIDE} is not a readable finances backup") in Page(
        response.text
    ).paragraphs
    response = post(home, "/backups/restore", name=SET_ASIDE, confirm=SET_ASIDE)
    assert response.status_code == 400
    assert transactions() == 3


def test_an_older_backup_asks_for_an_upgrade(
    home: TestClient, tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = tmp_settings.data_dir / "old.db"
    config = Config()
    config.set_main_option("script_location", str(Path(finances.db.__file__).parent / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{old.as_posix()}")
    command.upgrade(config, "0008")
    name = "finances-20200101-000000.db"
    shutil.copy(old, tmp_settings.effective_backup_dir / name)
    response = post(home, "/backups/restore", name=name, confirm=name)
    assert (response.status_code, response.headers["location"]) == (
        303,
        "/backups?notice=restored-old",
    )
    assert (
        "notice",
        "Backup restored. It comes from an older version of the app: run fin db upgrade in the"
        " terminal before using the other pages.",
    ) in page(home, "/backups?notice=restored-old").paragraphs
    assert page(home, "/accounts").paragraphs[0] == ("error", WEB_NOT_MIGRATED)
    monkeypatch.setattr(
        "finances.web.app._now", lambda: datetime(2026, 10, 17, 9, 0, 1, tzinfo=UTC)
    )
    response = post(home, "/backups/restore", name=REPLACED, confirm=REPLACED)
    assert (response.status_code, response.headers["location"]) == (303, "/backups?notice=restored")
    assert transactions() == 3
```

## Tests to write

`tests/integration/test_backups_page_more.py`:

- `list_set_asides` of a missing folder; `find_backup` of a folder with that name (not a file); `taken_at` of both kinds of name;
- the restore gate: while a test holds it, a request made in another thread does not finish; after release it does (use a short timeout, never a long sleep);
- `GET /backups/restore` for a name that is a backup but unreadable shows the Backups page with the not-readable message (the given test covers the POST).

## Rules for this phase

- **No JavaScript**, no download route, no upload route.
- **Thin.** The routes call `db/backup.py`, `views`, and the existing helpers; names are checked only by `find_backup`.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the given test files: `tests/integration/test_web_backups.py`, 35 tests;
- also `.venv/bin/python -m pytest tests/integration/test_backup.py tests/e2e/test_cli_backup.py --no-cov`: all pass (Phase 24 unchanged);
- the coverage command: `.venv/bin/python -m pytest -o addopts="" --import-mode=importlib --cov=finances.db.backup --cov=finances.views --cov=finances.web --cov-branch --cov-report=term-missing --cov-fail-under=100`;
- the searches: `git grep -n --untracked -E "select\(|session\.(add|execute|delete)|\.unlink\(|before-restore|finances-\[" -- src/finances/web` and `git grep -n --untracked -E "<script|https?://" -- src/finances/web/templates src/finances/web/static`, and `git grep -n --untracked -E "FileResponse|UploadFile|Content-Disposition|attachment" -- src/finances/web` (no output).

## Report

As in `docs/phase-conventions.md`, headed `## Phase 24b: backups on the web (YYYY-MM-DD)`.
