from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.backup import list_backups, make_backup
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import record_seen_feed_account
from finances.sync.links import load_access_url, save_access_url
from finances.web.app import create_app
from finances.web.login import set_password
from tests.support import WEB_PORT, Page, page, texts

RIGHT = "correct horse battery"
TOKEN = "x"


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    upgrade_to_head()
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


@pytest.fixture
def backup(tmp_settings: Settings, client: TestClient) -> Path:
    make_backup(
        tmp_settings.effective_database_url,
        tmp_settings.effective_backup_dir,
        14,
        datetime(2026, 10, 24, 12, 0, tzinfo=UTC),
    )
    return list_backups(tmp_settings.effective_backup_dir)[0]


@pytest.fixture
def home(client: TestClient) -> TestClient:
    set_password(RIGHT, None)
    client.get("/login")
    client.post(
        "/login",
        data={"csrf": client.cookies["fin_csrf"], "password": RIGHT, "next": "/"},
        follow_redirects=False,
    )
    return client


def send(client: TestClient, path: str, **fields: str):
    data = {"csrf": client.cookies["fin_csrf"], **fields}
    return client.post(path, data=data, follow_redirects=False)


def test_no_password_box_without_a_password(client: TestClient, backup: Path) -> None:
    found = page(client, f"/backups/delete?name={backup.name}")
    assert "password" not in found.find("/backups/delete")["inputs"]


def test_the_boxes_with_a_password(home: TestClient, backup: Path) -> None:
    for path, action in (
        (f"/backups/delete?name={backup.name}", "/backups/delete"),
        (f"/backups/restore?name={backup.name}", "/backups/restore"),
        ("/sync", "/sync/link"),
        ("/sync/unlink?link=alex", "/sync/unlink"),
    ):
        assert page(home, path).find(action)["inputs"]["password"] == ("password", ""), path


def test_deleting_needs_the_password(home: TestClient, backup: Path) -> None:
    wrong = send(home, "/backups/delete", name=backup.name, password="not the password")
    assert wrong.status_code == 400
    assert texts(Page(wrong.text), "error") == ["wrong password"]
    assert backup.exists()
    right = send(home, "/backups/delete", name=backup.name, password=RIGHT)
    assert (right.status_code, right.headers["location"]) == (303, "/backups?notice=deleted")
    assert not backup.exists()


def test_restoring_needs_the_password_before_the_name(home: TestClient, backup: Path) -> None:
    wrong = send(
        home, "/backups/restore", name=backup.name, confirm=backup.name, password="not it at all"
    )
    assert (wrong.status_code, texts(Page(wrong.text), "error")) == (400, ["wrong password"])
    right = send(home, "/backups/restore", name=backup.name, confirm=backup.name, password=RIGHT)
    assert (right.status_code, right.headers["location"]) == (303, "/backups?notice=restored")


def test_linking_needs_the_password(home: TestClient) -> None:
    wrong = send(home, "/sync/link", link="alex", token=TOKEN, password="not the password")
    assert (wrong.status_code, texts(Page(wrong.text), "error")) == (400, ["wrong password"])
    assert f'value="{TOKEN}"' not in wrong.text
    right = send(home, "/sync/link", link="alex", token=TOKEN, password=RIGHT)
    assert (right.status_code, texts(Page(right.text), "error")) == (
        400,
        ["setup token is not valid"],
    )


def test_unlinking_has_a_page_and_needs_the_password(home: TestClient) -> None:
    save_access_url("alex", "https://user:secret@bridge.example/simplefin")
    engine = get_engine()
    with session_scope(engine) as session:
        record_seen_feed_account(
            session, "alex", "ACT-0001", "EXAMPLE CHECKING", "EXAMPLE BANK", date(2026, 10, 24)
        )
    engine.dispose()
    found = page(home, "/sync")
    assert [form["method"] for form in found.all("/sync/unlink")] == ["get"]
    confirm = page(home, "/sync/unlink?link=alex")
    assert texts(confirm, "summary") == [
        "Unlink alex? Its SimpleFIN access is removed from this Mac's Keychain; its accounts and"
        " their mappings stay."
    ]
    wrong = send(home, "/sync/unlink", link="alex", password="not the password")
    assert (wrong.status_code, texts(Page(wrong.text), "error")) == (400, ["wrong password"])
    assert load_access_url("alex") is not None
    right = send(home, "/sync/unlink", link="alex", password=RIGHT)
    assert (right.status_code, right.headers["location"]) == (303, "/sync?notice=unlinked")
    assert load_access_url("alex") is None


def test_wrong_passwords_here_lock_the_login(home: TestClient, backup: Path) -> None:
    for _ in range(5):
        send(home, "/backups/delete", name=backup.name, password="not the password")
    home.cookies.clear()
    home.get("/login")
    login = send(home, "/login", password=RIGHT, next="/")
    assert login.status_code == 400
    assert texts(Page(login.text), "error")[0].startswith("Too many wrong passwords:")
    assert backup.exists()
