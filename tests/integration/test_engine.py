from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finances.config import Settings
from finances.db.engine import get_engine, session_scope

MEMORY_URLS = ["sqlite://", "sqlite:///:memory:"]
OTHER_URLS = ["postgresql://user:secret@host/db", "mysql://user:secret@host/folder/db"]
CREATE_CHILD = (
    "CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER NOT NULL REFERENCES parent (id))"
)


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def count_parents(engine: Engine) -> int:
    with engine.connect() as connection:
        return connection.execute(text("SELECT COUNT(*) FROM parent")).scalar_one()


def foreign_keys(connection) -> int:
    return connection.execute(text("PRAGMA foreign_keys")).scalar_one()


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = get_engine(sqlite_url(tmp_path / "test.db"))
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
        connection.execute(text(CREATE_CHILD))
    yield engine
    engine.dispose()


def test_get_engine_returns_an_engine(engine: Engine) -> None:
    assert isinstance(engine, Engine)


def test_get_engine_uses_the_configured_database_by_default(tmp_settings: Settings) -> None:
    engine = get_engine()
    url = engine.url.render_as_string(hide_password=False)
    engine.dispose()
    assert url == tmp_settings.effective_database_url
    assert tmp_settings.data_dir.is_dir()


def test_get_engine_creates_missing_parent_folders(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "app.db"
    get_engine(sqlite_url(target)).dispose()
    assert target.parent.is_dir()


def test_get_engine_accepts_an_existing_folder(tmp_path: Path) -> None:
    get_engine(sqlite_url(tmp_path / "app.db")).dispose()
    get_engine(sqlite_url(tmp_path / "app.db")).dispose()


def test_get_engine_creates_folders_for_a_relative_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    get_engine("sqlite:///nested/dir/app.db").dispose()
    assert (tmp_path / "nested" / "dir").is_dir()


@pytest.mark.parametrize("url", MEMORY_URLS)
def test_get_engine_in_memory_creates_nothing_on_disk(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    engine = get_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
    engine.dispose()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("url", OTHER_URLS)
def test_get_engine_rejects_other_backends(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError) as excinfo:
        get_engine(url)
    assert str(excinfo.value) == "only SQLite databases are supported"
    assert list(tmp_path.iterdir()) == []


def test_foreign_keys_are_on(engine: Engine) -> None:
    with engine.connect() as connection:
        assert foreign_keys(connection) == 1


def test_foreign_keys_are_on_for_every_connection(engine: Engine) -> None:
    with engine.connect() as first, engine.connect() as second:
        assert foreign_keys(first) == 1
        assert foreign_keys(second) == 1


@pytest.mark.parametrize("url", MEMORY_URLS)
def test_foreign_keys_are_on_in_memory(url: str) -> None:
    engine = get_engine(url)
    with engine.connect() as connection:
        assert foreign_keys(connection) == 1
    engine.dispose()


def test_a_broken_foreign_key_is_rejected(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("INSERT INTO child (id, parent_id) VALUES (1, 99)"))


def test_session_scope_yields_a_session_bound_to_the_engine(engine: Engine) -> None:
    with session_scope(engine) as session:
        assert isinstance(session, Session)
        assert session.get_bind() is engine


def test_session_scope_commits_on_success(engine: Engine) -> None:
    with session_scope(engine) as session:
        session.execute(text("INSERT INTO parent (id) VALUES (1)"))
    assert count_parents(engine) == 1


def test_session_scope_rolls_back_on_error(engine: Engine) -> None:
    with pytest.raises(RuntimeError), session_scope(engine) as session:
        session.execute(text("INSERT INTO parent (id) VALUES (1)"))
        raise RuntimeError("boom")
    assert count_parents(engine) == 0


def test_session_scope_reraises_the_same_exception(engine: Engine) -> None:
    error = RuntimeError("boom")
    with pytest.raises(RuntimeError) as excinfo, session_scope(engine):
        raise error
    assert excinfo.value is error


def test_session_scope_keeps_earlier_work_after_a_later_error(engine: Engine) -> None:
    with session_scope(engine) as session:
        session.execute(text("INSERT INTO parent (id) VALUES (1)"))
    with pytest.raises(RuntimeError), session_scope(engine) as session:
        session.execute(text("INSERT INTO parent (id) VALUES (2)"))
        raise RuntimeError("boom")
    assert count_parents(engine) == 1


@pytest.mark.parametrize("fail", [False, True])
def test_session_scope_closes_the_session(
    engine: Engine, monkeypatch: pytest.MonkeyPatch, fail: bool
) -> None:
    closed = []
    real_close = Session.close

    def spy(self: Session) -> None:
        closed.append(self)
        real_close(self)

    monkeypatch.setattr(Session, "close", spy)
    if fail:
        with pytest.raises(RuntimeError), session_scope(engine) as session:
            raise RuntimeError("boom")
    else:
        with session_scope(engine) as session:
            pass
    assert session in closed
