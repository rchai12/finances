from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect, text

import finances.db.migrate
from finances.config import Settings
from finances.db.engine import get_engine
from finances.db.migrate import current_revision, head_revision, upgrade_to_head

OTHER_URL = "postgresql://user:secret@host/db"
MESSAGE = "only SQLite databases are supported"
REVISION = """revision = "{revision}"
down_revision = {down}


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
"""


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def table_names(url: str) -> list[str]:
    engine = get_engine(url)
    names = sorted(inspect(engine).get_table_names())
    engine.dispose()
    return names


def test_head_revision_is_0001() -> None:
    assert head_revision() == "0001"


def test_head_revision_is_the_same_from_another_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert head_revision() == "0001"
    assert list(tmp_path.iterdir()) == []


def test_head_revision_reads_the_migrations_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    versions = tmp_path / "migrations" / "versions"
    versions.mkdir(parents=True)
    (versions / "0001_first.py").write_text(REVISION.format(revision="0001", down="None"))
    (versions / "0002_second.py").write_text(REVISION.format(revision="0002", down='"0001"'))
    monkeypatch.setattr(finances.db.migrate, "MIGRATIONS", tmp_path / "migrations")
    assert head_revision() == "0002"


def test_upgrade_to_head_returns_the_new_revision(db_url: str) -> None:
    assert upgrade_to_head(db_url) == "0001"


def test_upgrade_to_head_creates_the_tables(db_url: str) -> None:
    upgrade_to_head(db_url)
    assert table_names(db_url) == ["accounts", "alembic_version"]


def test_upgrade_to_head_twice_changes_nothing(db_url: str) -> None:
    upgrade_to_head(db_url)
    assert upgrade_to_head(db_url) == "0001"
    assert table_names(db_url) == ["accounts", "alembic_version"]


def test_upgrade_to_head_works_from_another_folder(
    db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert upgrade_to_head(db_url) == "0001"
    assert list(elsewhere.iterdir()) == []


def test_upgrade_to_head_creates_missing_folders(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "app.db"
    assert upgrade_to_head(sqlite_url(target)) == "0001"
    assert target.is_file()


def test_upgrade_to_head_accepts_a_percent_sign(tmp_path: Path) -> None:
    target = tmp_path / "100%" / "app.db"
    assert upgrade_to_head(sqlite_url(target)) == "0001"
    assert target.is_file()
    assert [path.name for path in tmp_path.iterdir()] == ["100%"]


def test_upgrade_to_head_uses_the_configured_database_by_default(
    tmp_settings: Settings,
) -> None:
    assert upgrade_to_head() == "0001"
    assert (tmp_settings.data_dir / "finances.db").is_file()
    assert table_names(tmp_settings.effective_database_url) == ["accounts", "alembic_version"]


def test_upgrade_to_head_rejects_other_backends() -> None:
    with pytest.raises(ValueError) as excinfo:
        upgrade_to_head(OTHER_URL)
    assert str(excinfo.value) == MESSAGE


def test_current_revision_is_none_for_a_new_database(db_url: str) -> None:
    assert current_revision(db_url) is None
    assert table_names(db_url) == []


def test_current_revision_after_an_upgrade(db_url: str) -> None:
    upgrade_to_head(db_url)
    assert current_revision(db_url) == "0001"


def test_current_revision_is_none_when_the_record_is_empty(db_url: str) -> None:
    upgrade_to_head(db_url)
    engine = get_engine(db_url)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM alembic_version"))
    engine.dispose()
    assert current_revision(db_url) is None


def test_current_revision_accepts_a_percent_sign(tmp_path: Path) -> None:
    url = sqlite_url(tmp_path / "100%" / "app.db")
    assert current_revision(url) is None
    upgrade_to_head(url)
    assert current_revision(url) == "0001"


def test_current_revision_uses_the_configured_database_by_default(
    tmp_settings: Settings,
) -> None:
    assert current_revision() is None
    upgrade_to_head()
    assert current_revision() == "0001"


def test_current_revision_rejects_other_backends() -> None:
    with pytest.raises(ValueError) as excinfo:
        current_revision(OTHER_URL)
    assert str(excinfo.value) == MESSAGE


def test_db_engine_fixture_is_migrated(db_engine: Engine, db_url: str) -> None:
    assert sorted(inspect(db_engine).get_table_names()) == ["accounts", "alembic_version"]
    assert current_revision(db_url) == head_revision()


def test_db_engine_fixture_has_foreign_keys_on(db_engine: Engine) -> None:
    with db_engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_db_url_fixture_points_into_tmp_path(db_url: str, tmp_path: Path) -> None:
    assert db_url == sqlite_url(tmp_path / "test.db")
    assert list(tmp_path.iterdir()) == []
