"""Alembic environment. The database URL comes from the Alembic Config, never from a file."""

from alembic import context

from finances.db.engine import get_engine
from finances.db.orm import Base

engine = get_engine(context.config.get_main_option("sqlalchemy.url"))
with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
