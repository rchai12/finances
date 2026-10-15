import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finances.config import Settings, get_settings
from finances.db.backup import find_backup, list_set_asides, taken_at
from finances.db.migrate import upgrade_to_head
from finances.web import app as web
from finances.web.app import create_app
from tests.support import WEB_PORT, Page, post, texts

NAME = "finances-20261015-143005.db"


@pytest.fixture
def client(tmp_settings: Settings) -> TestClient:
    return TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")


def test_a_missing_folder_has_no_set_aside_copies(tmp_path: Path) -> None:
    assert list_set_asides(tmp_path / "missing") == []


def test_a_folder_with_a_backup_name_is_not_a_backup(tmp_path: Path) -> None:
    (tmp_path / NAME).mkdir()
    with pytest.raises(ValueError, match=f"^{NAME} is not a backup in the folder$"):
        find_backup(tmp_path, NAME)


def test_taken_at_reads_both_kinds_of_name() -> None:
    assert taken_at(Path(NAME)) == datetime(2026, 10, 15, 14, 30, 5, tzinfo=UTC)
    assert taken_at(Path("finances-20261017-090001-before-restore.db")) == datetime(
        2026, 10, 17, 9, 0, 1, tzinfo=UTC
    )


def test_requests_wait_while_a_restore_runs(client: TestClient) -> None:
    upgrade_to_head()
    answers: list[int] = []

    def open_accounts() -> None:
        answers.append(client.get("/accounts").status_code)

    waiting = threading.Thread(target=open_accounts)
    with web._RESTORE_GATE:
        waiting.start()
        waiting.join(timeout=0.2)
        assert waiting.is_alive()
        assert answers == []
    waiting.join(timeout=10)
    assert not waiting.is_alive()
    assert answers == [200]


def test_opening_an_unreadable_backup_shows_the_backups_page(
    client: TestClient, tmp_settings: Settings
) -> None:
    folder = tmp_settings.effective_backup_dir
    folder.mkdir(parents=True)
    (folder / NAME).write_text("not a database", encoding="utf-8")
    response = client.get(f"/backups/restore?name={NAME}")
    assert response.status_code == 400
    found = Page(response.text)
    assert ("error", f"{NAME} is not a readable finances backup") in found.paragraphs
    assert texts(found, "hint")[0].startswith(f"Kept in {folder.resolve()}:")


def test_back_up_now_shows_a_refusal(
    client: TestClient, tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    upgrade_to_head()
    monkeypatch.setenv("FIN_BACKUP_KEEP", "0")
    get_settings.cache_clear()
    client.get("/backups")
    response = post(client, "/backups/run")
    assert response.status_code == 400
    assert ("error", "keep must be at least 1") in Page(response.text).paragraphs
    assert not tmp_settings.effective_backup_dir.exists()
