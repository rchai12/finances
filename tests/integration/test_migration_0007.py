from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import finances.db
from finances.db.engine import get_engine, session_scope
from finances.db.orm import Base, FeedSeenAccountRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0007_feed_seen_accounts.py"
COLUMNS = [
    ("id", "INTEGER", False),
    ("link", "VARCHAR(50)", False),
    ("provider_account_id", "VARCHAR(200)", False),
    ("name", "VARCHAR(100)", False),
    ("institution", "VARCHAR(100)", False),
    ("first_seen", "DATE", False),
    ("last_seen", "DATE", False),
    ("ignored", "BOOLEAN", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


def table_names(url: str) -> list[str]:
    engine = get_engine(url)
    names = sorted(inspect(engine).get_table_names())
    engine.dispose()
    return names


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def at_0007(url: str) -> str:
    command.upgrade(make_config(url), "0007")
    return url


def test_0007_follows_0006(url: str) -> None:
    script = ScriptDirectory.from_config(make_config(url)).get_revision("0007")
    assert script.down_revision == "0006"


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source


def test_columns_keys_and_constraints(at_0007: str) -> None:
    engine = get_engine(at_0007)
    found = inspect(engine)
    columns = [
        (column["name"], str(column["type"]), column["nullable"])
        for column in found.get_columns("feed_seen_accounts")
    ]
    primary = found.get_pk_constraint("feed_seen_accounts")
    uniques = [
        (item["name"], item["column_names"])
        for item in found.get_unique_constraints("feed_seen_accounts")
    ]
    foreign = found.get_foreign_keys("feed_seen_accounts")
    engine.dispose()
    assert columns == COLUMNS
    assert (primary["name"], primary["constrained_columns"]) == ("pk_feed_seen_accounts", ["id"])
    assert uniques == [
        ("uq_feed_seen_accounts_link_provider_account", ["link", "provider_account_id"])
    ]
    assert foreign == []


def test_the_orm_class_matches_the_migrated_table(at_0007: str) -> None:
    table = Base.metadata.tables["feed_seen_accounts"]
    assert FeedSeenAccountRow.__table__ is table
    assert [(column.name, str(column.type), column.nullable) for column in table.columns] == COLUMNS


def test_one_row_per_link_and_aggregator_account(at_0007: str) -> None:
    engine = get_engine(at_0007)
    insert = (
        "INSERT INTO feed_seen_accounts (link, provider_account_id, name, institution,"
        " first_seen, last_seen, ignored) VALUES (:link, 'ACT-1', 'Probe', 'Probe Bank',"
        " '2026-05-01', '2026-05-01', 0)"
    )
    with session_scope(engine) as session:
        session.execute(text(insert), {"link": "alex"})
        session.execute(text(insert), {"link": "sam"})
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.execute(text(insert), {"link": "alex"})
    with session_scope(engine) as session:
        row = session.get(FeedSeenAccountRow, 1)
        assert (row.first_seen, row.ignored) == (date(2026, 5, 1), False)
    engine.dispose()


def test_downgrade_removes_only_the_table(at_0007: str) -> None:
    before = table_names(at_0007)
    command.downgrade(make_config(at_0007), "0006")
    assert table_names(at_0007) == sorted(set(before) - {"feed_seen_accounts"})
