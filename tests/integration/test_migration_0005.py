from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import finances.db
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, Base

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0005_feed_links.py"
COLUMNS = [
    ("id", "INTEGER", False),
    ("account_id", "INTEGER", False),
    ("provider_account_id", "VARCHAR(200)", False),
    ("link", "VARCHAR(50)", False),
]
UNIQUES = [
    ("uq_feed_accounts_account_id", ["account_id"]),
    ("uq_feed_accounts_link_provider_account", ["link", "provider_account_id"]),
]
INSERT = text(
    "INSERT INTO feed_accounts (account_id, provider_account_id, link)"
    " VALUES (:account, :provider, :link)"
)


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


def versions(url: str) -> list[str]:
    engine = get_engine(url)
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT version_num FROM alembic_version")).all()
    engine.dispose()
    return [row[0] for row in rows]


def reflect(url: str, table: str, what: str) -> list:
    engine = get_engine(url)
    result = getattr(inspect(engine), what)(table)
    engine.dispose()
    return result


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def with_accounts(url: str, revision: str) -> None:
    command.upgrade(make_config(url), revision)
    engine = get_engine(url)
    with session_scope(engine) as session:
        for name in ("Test Card", "Test Checking", "Test Savings"):
            session.add(AccountRow(name=name, institution="Test Bank", type="checking"))
    engine.dispose()


@pytest.fixture
def at_0005(url: str) -> str:
    """A database at revision 0005 only, with three accounts."""
    with_accounts(url, "0005")
    return url


def rows(url: str) -> list[tuple]:
    engine = get_engine(url)
    with engine.connect() as connection:
        found = connection.execute(
            text("SELECT id, account_id, provider_account_id, link FROM feed_accounts ORDER BY id")
        ).all()
    engine.dispose()
    return [tuple(row) for row in found]


def test_0005_follows_0004(url: str) -> None:
    scripts = ScriptDirectory.from_config(make_config(url))
    assert scripts.get_revision("0005").down_revision == "0004"
    assert len(scripts.get_heads()) == 1


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source
    assert "batch_alter_table" in source


def test_columns_and_constraints(at_0005: str) -> None:
    assert len(table_names(at_0005)) == 8
    assert versions(at_0005) == ["0005"]
    columns = reflect(at_0005, "feed_accounts", "get_columns")
    assert [(c["name"], str(c["type"]), c["nullable"]) for c in columns] == COLUMNS
    assert [c["default"] for c in columns] == [None, None, None, None]
    primary_key = reflect(at_0005, "feed_accounts", "get_pk_constraint")
    assert (primary_key["name"], primary_key["constrained_columns"]) == ("pk_feed_accounts", ["id"])
    uniques = reflect(at_0005, "feed_accounts", "get_unique_constraints")
    assert sorted((u["name"], u["column_names"]) for u in uniques) == UNIQUES
    keys = reflect(at_0005, "feed_accounts", "get_foreign_keys")
    assert [(k["name"], k["constrained_columns"], k["referred_table"]) for k in keys] == [
        ("fk_feed_accounts_account_id_accounts", ["account_id"], "accounts")
    ]
    assert reflect(at_0005, "feed_accounts", "get_indexes") == []


def test_the_orm_class_matches_the_migrated_table(at_0005: str) -> None:
    declared = Base.metadata.tables["feed_accounts"]
    assert [(c.name, c.nullable) for c in declared.columns] == [
        (name, nullable) for name, _, nullable in COLUMNS
    ]
    found = {
        (constraint.name, tuple(column.name for column in constraint.columns))
        for constraint in declared.constraints
        if type(constraint).__name__ == "UniqueConstraint"
    }
    assert found == {(name, tuple(columns)) for name, columns in UNIQUES}
    assert declared.columns["link"].default.arg == "default"


def test_existing_mappings_become_the_default_link(url: str) -> None:
    with_accounts(url, "0004")
    engine = get_engine(url)
    with session_scope(engine) as session:
        session.execute(
            text("INSERT INTO feed_accounts (account_id, provider_account_id) VALUES (1, 'ACT-1')")
        )
        session.execute(
            text("INSERT INTO feed_accounts (account_id, provider_account_id) VALUES (2, 'ACT-2')")
        )
    engine.dispose()
    command.upgrade(make_config(url), "0005")
    assert rows(url) == [(1, 1, "ACT-1", "default"), (2, 2, "ACT-2", "default")]


def test_the_same_aggregator_id_under_two_links(at_0005: str) -> None:
    engine = get_engine(at_0005)
    with session_scope(engine) as session:
        session.execute(INSERT, {"account": 1, "provider": "ACT-1", "link": "alex"})
        session.execute(INSERT, {"account": 2, "provider": "ACT-1", "link": "sam"})
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.execute(INSERT, {"account": 3, "provider": "ACT-1", "link": "alex"})
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.execute(INSERT, {"account": 1, "provider": "ACT-9", "link": "sam"})
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.execute(
            text("INSERT INTO feed_accounts (account_id, provider_account_id) VALUES (3, 'ACT-3')")
        )
    engine.dispose()
    assert rows(at_0005) == [(1, 1, "ACT-1", "alex"), (2, 2, "ACT-1", "sam")]


def test_downgrade_restores_0004(at_0005: str) -> None:
    engine = get_engine(at_0005)
    with session_scope(engine) as session:
        session.execute(INSERT, {"account": 1, "provider": "ACT-1", "link": "alex"})
        session.execute(INSERT, {"account": 2, "provider": "ACT-2", "link": "sam"})
    engine.dispose()
    command.downgrade(make_config(at_0005), "0004")
    assert versions(at_0005) == ["0004"]
    columns = reflect(at_0005, "feed_accounts", "get_columns")
    assert [c["name"] for c in columns] == ["id", "account_id", "provider_account_id"]
    uniques = reflect(at_0005, "feed_accounts", "get_unique_constraints")
    assert sorted((u["name"], u["column_names"]) for u in uniques) == [
        ("uq_feed_accounts_account_id", ["account_id"]),
        ("uq_feed_accounts_provider_account_id", ["provider_account_id"]),
    ]
    engine = get_engine(at_0005)
    with engine.connect() as connection:
        kept = connection.execute(
            text("SELECT account_id, provider_account_id FROM feed_accounts ORDER BY id")
        ).all()
    engine.dispose()
    assert [tuple(row) for row in kept] == [(1, "ACT-1"), (2, "ACT-2")]
    command.upgrade(make_config(at_0005), "0005")
    assert rows(at_0005) == [(1, 1, "ACT-1", "default"), (2, 2, "ACT-2", "default")]
