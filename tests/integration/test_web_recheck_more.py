from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings
from finances.db.backup import list_backups, make_backup
from finances.db.migrate import upgrade_to_head
from finances.sync.links import load_access_url, save_access_url
from finances.web.app import create_app
from finances.web.login import set_password
from finances.web.session import recheck
from tests.integration.test_web_recheck import RIGHT, TOKEN, send
from tests.support import WEB_PORT, Page, page, texts

NAME_RULE = "a link name is 1 to 30 lowercase letters, digits, or hyphens, starting with a letter"
_CONFIRM_NAME = "type the backup's name to confirm"
_KEYCHAIN = "could not use the system keychain"


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


def test_recheck_with_no_password_or_while_locked() -> None:
    assert recheck("any text at all") is None
    assert recheck("") is None
    set_password(RIGHT, None)
    for _ in range(4):
        assert recheck("not the password") == "wrong password"
    locked = recheck("not the password")
    assert locked is not None and locked.startswith("Too many wrong passwords:")
    assert recheck(RIGHT) == locked


def test_recheck_when_the_keychain_cannot_be_read(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail() -> bool:
        raise ValueError(_KEYCHAIN)

    monkeypatch.setattr("finances.web.session.has_password", fail)
    assert recheck("any text at all") == _KEYCHAIN


def test_restore_checks_the_password_before_the_typed_name(home: TestClient, backup: Path) -> None:
    wrong = send(
        home, "/backups/restore", name=backup.name, confirm="not-the-name", password="not it at all"
    )
    assert (wrong.status_code, texts(Page(wrong.text), "error")) == (400, ["wrong password"])
    named = send(home, "/backups/restore", name=backup.name, confirm="not-the-name", password=RIGHT)
    assert (named.status_code, texts(Page(named.text), "error")) == (400, [_CONFIRM_NAME])


def test_unlink_refuses_a_bad_link_name(client: TestClient) -> None:
    response = client.get("/sync/unlink?link=Bad")
    assert response.status_code == 400
    assert texts(Page(response.text), "error") == [NAME_RULE]


def test_the_four_forms_work_without_a_password(client: TestClient, backup: Path) -> None:
    page(client, "/backups")
    restored = send(client, "/backups/restore", name=backup.name, confirm=backup.name)
    assert (restored.status_code, restored.headers["location"]) == (303, "/backups?notice=restored")
    deleted = send(client, "/backups/delete", name=backup.name)
    assert (deleted.status_code, deleted.headers["location"]) == (303, "/backups?notice=deleted")
    linked = send(client, "/sync/link", link="alex", token=TOKEN)
    assert (linked.status_code, texts(Page(linked.text), "error")) == (
        400,
        ["setup token is not valid"],
    )
    save_access_url("alex", "https://user:secret@bridge.example/simplefin")
    unlinked = send(client, "/sync/unlink", link="alex")
    assert (unlinked.status_code, unlinked.headers["location"]) == (303, "/sync?notice=unlinked")


def test_a_wrong_password_on_link_leaves_the_keychain_empty(home: TestClient) -> None:
    wrong = send(home, "/sync/link", link="alex", token=TOKEN, password="not the password")
    assert (wrong.status_code, texts(Page(wrong.text), "error")) == (400, ["wrong password"])
    assert load_access_url("alex") is None
    assert f'value="{TOKEN}"' not in wrong.text


def test_the_sync_page_without_a_listable_keychain(client: TestClient) -> None:
    assert client.get("/sync").status_code == 200


def test_a_wrong_password_on_a_missing_backup(home: TestClient) -> None:
    missing = "finances-20990101-000000.db"
    wrong = send(home, "/backups/delete", name=missing, password="not the password")
    assert wrong.status_code == 400
    assert texts(Page(wrong.text), "error") == [f"{missing} is not a backup in the folder"]
