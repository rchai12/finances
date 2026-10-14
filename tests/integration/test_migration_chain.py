from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

import finances.db
from finances.db.engine import get_engine, session_scope
from finances.db.orm import Base
from finances.db.repositories import get_account_by_name
from finances.domain.models import AccountType

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


def revisions(config: Config) -> list[str]:
    """Every revision from the first to head, read from the migrations folder."""
    script = ScriptDirectory.from_config(config)
    return [revision.revision for revision in reversed(list(script.walk_revisions()))]


def schema(url: str) -> dict[str, tuple]:
    """Each table's columns, unique constraints, and foreign keys."""
    engine = get_engine(url)
    inspector = inspect(engine)
    found = {
        table: (
            [
                (column["name"], str(column["type"]), column["nullable"])
                for column in inspector.get_columns(table)
            ],
            sorted(
                (unique["name"], tuple(unique["column_names"]))
                for unique in inspector.get_unique_constraints(table)
            ),
            sorted(
                (
                    key["name"],
                    tuple(key["constrained_columns"]),
                    key["referred_table"],
                    tuple(key["referred_columns"]),
                )
                for key in inspector.get_foreign_keys(table)
            ),
        )
        for table in sorted(inspector.get_table_names())
    }
    engine.dispose()
    return found


def test_there_are_revisions_to_check(db_url: str) -> None:
    found = revisions(make_config(db_url))
    assert found[0] == "0001"
    assert len(found) == len(set(found)) >= 6


def test_each_revision_downgrades_and_upgrades_to_the_same_schema(db_url: str) -> None:
    config = make_config(db_url)
    for revision in revisions(config):
        command.upgrade(config, revision)
        before = schema(db_url)
        command.downgrade(config, "-1")
        assert schema(db_url) != before
        command.upgrade(config, revision)
        assert schema(db_url) == before


def test_downgrade_to_base_and_back_matches_the_models(db_url: str) -> None:
    config = make_config(db_url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    engine = get_engine(db_url)
    assert inspect(engine).get_table_names() == ["alembic_version"]
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM alembic_version")).scalar() == 0
    engine.dispose()

    command.upgrade(config, "head")
    engine = get_engine(db_url)
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    engine.dispose()


def test_an_account_from_the_first_revision_survives_every_upgrade(db_url: str) -> None:
    config = make_config(db_url)
    chain = revisions(config)
    command.upgrade(config, chain[0])
    engine = get_engine(db_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO accounts (name, institution, type, currency, last4, is_active,"
                " created_at) VALUES ('Old Card', 'Acme Bank', 'credit_card', 'USD', '1234',"
                " 1, '2026-01-02 03:04:05.000000')"
            )
        )
    engine.dispose()

    for revision in chain[1:]:
        command.upgrade(config, revision)

    engine = get_engine(db_url)
    with session_scope(engine) as session:
        account = get_account_by_name(session, "Old Card")
    engine.dispose()
    assert account is not None
    assert (account.name, account.institution, account.type) == (
        "Old Card",
        "Acme Bank",
        AccountType.CREDIT_CARD,
    )
    assert (account.currency, account.last4, account.is_active) == ("USD", "1234", True)
    assert account.created_at.replace(tzinfo=None) == datetime(2026, 1, 2, 3, 4, 5)
