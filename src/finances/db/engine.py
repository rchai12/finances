"""Database engine and session scope. SQLite is the only supported backend."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from finances.config import get_settings


def get_engine(url: str | None = None, *, read_only: bool = False) -> Engine:
    """Return an engine for url, or for the configured database when url is None."""
    if url is None:
        url = get_settings().effective_database_url

    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        raise ValueError("only SQLite databases are supported")

    # For in-memory databases, don't create any folder structure
    if parsed.database is not None and parsed.database != ":memory:":
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url)

    # Add a connect listener to enable foreign keys for every connection
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        if read_only:
            cursor.execute("PRAGMA query_only=ON")
        cursor.close()

    return engine


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Yield a session; commit when the block succeeds, roll back when it raises."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
