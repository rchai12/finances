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
        assert ("error", NOT_A_BACKUP.format(name).strip()) in Page(response.text).paragraphs
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
