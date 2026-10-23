from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

import finances.db
from finances.config import Settings
from finances.db.backup import make_backup
from finances.db.backup_records import note_backup_deleted, note_backup_restored
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.repositories import create_account, create_person, create_statement, list_changes
from finances.web.app import create_app
from tests.support import WEB_PORT, post, run

NOON = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
FIRST = "finances-20261015-143005.db"
OLDER = "finances-20261014-020000.db"


def trail() -> list[tuple]:
    engine = get_engine()
    with session_scope(engine) as session:
        found = [
            (item.who, item.action, item.kind, item.record_id, item.before, item.after)
            for item in reversed(list_changes(session, limit=1000))
        ]
    engine.dispose()
    return found


@pytest.fixture
def client(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A card added, then a backup FIRST taken; the trail's clock reads NOON."""
    monkeypatch.setattr("finances.db.repositories.audit._now", lambda: NOON)
    monkeypatch.setattr(
        "finances.web.app._now", lambda: datetime(2026, 10, 17, 9, 0, 0, tzinfo=UTC)
    )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
    engine.dispose()
    make_backup(
        tmp_settings.effective_database_url,
        tmp_settings.effective_backup_dir,
        14,
        datetime(2026, 10, 15, 14, 30, 5, tzinfo=UTC),
    )
    found = TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}")
    found.get("/backups")
    return found


def test_a_statement_import_is_recorded_as_the_system(client: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_statement(
            session,
            account_id=1,
            source_filename="card.pdf",
            file_sha256="a" * 64,
            parser_name="test",
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            opening_balance_cents=0,
            closing_balance_cents=0,
            lines_parsed=0,
            rows_inserted=0,
            rows_duplicate=0,
        )
    engine.dispose()
    assert trail()[-1] == (
        "system",
        "statement_imported",
        "statement",
        1,
        None,
        "test, 2026-04-01 to 2026-04-30",
    )


def test_deleting_a_backup_on_the_web(client: TestClient) -> None:
    response = post(client, "/backups/delete", name=FIRST)
    assert response.status_code == 303
    assert trail()[-1] == ("person", "backup_deleted", "backup", None, FIRST, None)


def test_a_restore_keeps_the_restored_history_and_adds_one_row(client: TestClient) -> None:
    engine = get_engine()
    with session_scope(engine) as session:
        create_person(session, "Pat Example")
    engine.dispose()
    response = post(client, "/backups/restore", name=FIRST, confirm=FIRST)
    assert response.headers["location"] == "/backups?notice=restored"
    assert trail() == [
        ("person", "account_added", "account", 1, None, "Test Card"),
        ("person", "backup_restored", "backup", None, None, FIRST),
    ]


def test_restoring_a_backup_from_before_the_trail_records_nothing(
    client: TestClient, tmp_settings: Settings
) -> None:
    older = tmp_settings.effective_backup_dir / OLDER
    config = Config()
    config.set_main_option("script_location", str(Path(finances.db.__file__).parent / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{older.as_posix()}")
    command.upgrade(config, "0011")
    response = post(client, "/backups/restore", name=OLDER, confirm=OLDER)
    assert response.headers["location"] == "/backups?notice=restored-old"
    assert note_backup_restored(tmp_settings.effective_database_url, OLDER) is False


def test_restoring_in_the_terminal(client: TestClient, tmp_settings: Settings) -> None:
    result = run("backup", "restore", str(tmp_settings.effective_backup_dir / FIRST), "--yes")
    assert result.exit_code == 0
    assert trail()[-1] == ("person", "backup_restored", "backup", None, None, FIRST)


def test_nothing_is_noted_on_a_database_that_is_not_migrated(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"
    assert note_backup_deleted(url, FIRST) is False
    assert note_backup_restored(url, FIRST) is False
