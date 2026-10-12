"""Run database migrations from code. There is no alembic.ini, so this works from any folder."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from finances.config import get_settings
from finances.db.engine import get_engine

MIGRATIONS = Path(__file__).parent / "migrations"


def head_revision() -> str:
    """Return the identifier of the newest migration."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    script_dir = ScriptDirectory.from_config(config)
    return script_dir.get_current_head()


def upgrade_to_head(url: str | None = None) -> str:
    """Apply every pending migration and return the revision the database is now at."""
    if url is None:
        url = get_settings().effective_database_url

    # Create config for alembic with proper URL handling (escaping % signs)
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    # Alembic handles % signs specially, so we need to double them
    escaped_url = url.replace("%", "%%")
    config.set_main_option("sqlalchemy.url", escaped_url)

    command.upgrade(config, "head")

    # Get the current revision after upgrade
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    script_dir = ScriptDirectory.from_config(config)
    return script_dir.get_current_head()


def current_revision(url: str | None = None) -> str | None:
    """Return the revision recorded in the database, or None if it has none."""
    if url is None:
        url = get_settings().effective_database_url

    engine = get_engine(url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            return context.get_current_revision()
    finally:
        engine.dispose()
