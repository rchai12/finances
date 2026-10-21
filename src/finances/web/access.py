"""Database access for web routes, gated on the restore lock."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.db.engine import get_engine, session_scope
from finances.web import app as web_app


@contextmanager
def _engine() -> Iterator[Engine]:
    with web_app._RESTORE_GATE:
        engine = get_engine()
        try:
            yield engine
        finally:
            engine.dispose()


@contextmanager
def _reading() -> Iterator[Session]:
    with _engine() as engine:
        with session_scope(engine) as session:
            yield session
