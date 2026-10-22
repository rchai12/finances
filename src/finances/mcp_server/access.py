"""A read-only session that refuses to open until the schema is current."""

from collections.abc import Iterator
from contextlib import contextmanager

from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.orm import Session

from finances.db.engine import get_engine, session_scope
from finances.db.migrate import current_revision, head_revision

NOT_MIGRATED = "The database is not up to date. Run: fin db upgrade"


@contextmanager
def reading() -> Iterator[Session]:
    if current_revision() != head_revision():
        raise ToolError(NOT_MIGRATED)
    engine = get_engine(read_only=True)
    try:
        with session_scope(engine) as session:
            yield session
    finally:
        engine.dispose()
