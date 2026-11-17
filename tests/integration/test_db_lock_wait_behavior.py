import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError, OperationalError

from finances.config import get_settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import AccountRow


def account(name):
    return AccountRow(name=name, institution="Test Bank", type="checking", currency="USD")


def names(engine):
    with session_scope(engine) as session:
        return list(session.scalars(select(AccountRow.name).order_by(AccountRow.name)))


def configured(monkeypatch, value):
    monkeypatch.setenv("FIN_DB_BUSY_TIMEOUT_MS", str(value))
    get_settings.cache_clear()


@pytest.fixture
def migrated(tmp_settings):
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        session.add(account("Seed"))
    try:
        yield engine
    finally:
        engine.dispose()


def start_holder(engine):
    holder = engine.connect()
    holder.exec_driver_sql("BEGIN IMMEDIATE")
    holder.execute(
        text(
            "INSERT INTO accounts (name, institution, type, currency, is_active, created_at) "
            "VALUES ('Holder', 'Test Bank', 'checking', 'USD', 1, '2026-01-01')"
        )
    )
    return holder


def launch_writer(engine):
    issuing = Event()
    done = Event()
    executions = []

    @event.listens_for(engine, "before_cursor_execute")
    def before(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO ACCOUNTS"):
            executions.append(statement)
            issuing.set()

    def worker():
        try:
            with session_scope(engine) as session:
                assert (
                    session.scalar(select(AccountRow.name).where(AccountRow.name == "Seed"))
                    == "Seed"
                )
                session.add(account("Worker"))
                session.flush()
        finally:
            done.set()

    pool = ThreadPoolExecutor(max_workers=1)
    return pool, pool.submit(worker), issuing, done, executions


def test_waiting_writer_commits_once_after_release(migrated, monkeypatch):
    configured(monkeypatch, 2000)
    worker_engine = get_engine()
    holder = start_holder(migrated)
    pool, future, issuing, done, executions = launch_writer(worker_engine)
    try:
        assert issuing.wait(5)
        assert not done.wait(0.1)
        holder.commit()
        future.result(timeout=5)
        assert len(executions) == 1
        assert names(migrated) == ["Holder", "Seed", "Worker"]
    finally:
        holder.close()
        pool.shutdown(wait=True)
        worker_engine.dispose()


@pytest.mark.parametrize("timeout_ms", [50, 0], ids=["held-lock-timeout", "zero-wait"])
def test_blocked_writer_rolls_back_and_later_succeeds(migrated, monkeypatch, timeout_ms):
    configured(monkeypatch, timeout_ms)
    worker_engine = get_engine()
    holder = start_holder(migrated)
    pool, future, issuing, done, executions = launch_writer(worker_engine)
    try:
        assert issuing.wait(5)
        with pytest.raises(OperationalError) as caught:
            future.result(timeout=5)
        assert isinstance(caught.value.orig, sqlite3.OperationalError)
        assert caught.value.orig.sqlite_errorcode & 0xFF == sqlite3.SQLITE_BUSY
        assert done.is_set() and len(executions) == 1
        holder.commit()
        assert names(migrated) == ["Holder", "Seed"]
        with session_scope(worker_engine) as session:
            session.add(account("After"))
        assert names(migrated) == ["After", "Holder", "Seed"]
    finally:
        holder.close()
        pool.shutdown(wait=True)
        worker_engine.dispose()


@pytest.mark.parametrize("value", [0, 30000, 120000])
@pytest.mark.parametrize("url", ["sqlite://", "sqlite:///:memory:"])
def test_timeout_boundaries_on_reopened_connections(tmp_settings, monkeypatch, value, url):
    configured(monkeypatch, value)
    engine = get_engine(url)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == value
        engine.dispose()
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == value
    finally:
        engine.dispose()


def test_cache_clear_and_file_parent(tmp_settings, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    configured(monkeypatch, 137)
    first = get_engine("sqlite:///nested/test.db")
    configured(monkeypatch, 271)
    second = get_engine("sqlite:///nested/test.db")
    try:
        with first.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 137
        with second.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 271
        assert (tmp_path / "nested").is_dir()
    finally:
        first.dispose()
        second.dispose()


def test_foreign_keys_readonly_and_unsupported(migrated, tmp_settings):
    with pytest.raises(ValueError, match="^only SQLite databases are supported$"):
        get_engine("postgresql://host/db")
    with pytest.raises(IntegrityError), migrated.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO balance_snapshots (account_id, as_of_date, balance_cents, source, "
            "created_at) VALUES (99999, '2026-01-01', 1, 'statement', '2026-01-01')"
        )
    readonly = get_engine(read_only=True)
    try:
        with pytest.raises(OperationalError), readonly.begin() as connection:
            connection.exec_driver_sql("DELETE FROM accounts")
        assert names(migrated) == ["Seed"]
    finally:
        readonly.dispose()


def test_tmp_settings_clears_poisoned_environment(monkeypatch, request):
    monkeypatch.setenv("FIN_DB_BUSY_TIMEOUT_MS", "17")
    settings = request.getfixturevalue("tmp_settings")
    assert settings.db_busy_timeout_ms == 30000
    assert get_settings().db_busy_timeout_ms == 30000
