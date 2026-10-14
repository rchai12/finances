from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import finances.db
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, Base, FeedAccountRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0004_feed_accounts.py"
COLUMNS = [
    ("id", "INTEGER", False),
    ("account_id", "INTEGER", False),
    ("provider_account_id", "VARCHAR(200)", False),
]
UNIQUES = [
    ("uq_feed_accounts_account_id", ["account_id"]),
    ("uq_feed_accounts_provider_account_id", ["provider_account_id"]),
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


@pytest.fixture
def at_0004(url: str) -> str:
    """A database upgraded to revision 0004 only, whatever later migrations exist."""
    command.upgrade(make_config(url), "0004")
    return url


@pytest.fixture
def with_accounts(at_0004: str) -> str:
    engine = get_engine(at_0004)
    with session_scope(engine) as session:
        session.add(AccountRow(name="Test Card", institution="Test Bank", type="credit_card"))
        session.add(AccountRow(name="Test Checking", institution="Test Bank", type="checking"))
    engine.dispose()
    return at_0004


def test_0004_follows_0003(url: str) -> None:
    scripts = ScriptDirectory.from_config(make_config(url))
    assert scripts.get_revision("0004").down_revision == "0003"
    assert len(scripts.get_heads()) == 1


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source


def test_upgrade_adds_one_table(at_0004: str) -> None:
    assert "feed_accounts" in table_names(at_0004)
    assert len(table_names(at_0004)) == 8
    assert versions(at_0004) == ["0004"]


def test_columns_keys_and_constraints(at_0004: str) -> None:
    columns = reflect(at_0004, "feed_accounts", "get_columns")
    assert [(c["name"], str(c["type"]), c["nullable"]) for c in columns] == COLUMNS
    assert [c["default"] for c in columns] == [None, None, None]
    primary_key = reflect(at_0004, "feed_accounts", "get_pk_constraint")
    assert (primary_key["name"], primary_key["constrained_columns"]) == ("pk_feed_accounts", ["id"])
    uniques = reflect(at_0004, "feed_accounts", "get_unique_constraints")
    assert sorted((u["name"], u["column_names"]) for u in uniques) == UNIQUES
    keys = reflect(at_0004, "feed_accounts", "get_foreign_keys")
    assert [(k["name"], k["constrained_columns"], k["referred_table"]) for k in keys] == [
        ("fk_feed_accounts_account_id_accounts", ["account_id"], "accounts")
    ]
    assert reflect(at_0004, "feed_accounts", "get_indexes") == []


def test_the_orm_class_matches_the_migrated_table(at_0004: str) -> None:
    declared = Base.metadata.tables["feed_accounts"]
    assert FeedAccountRow.__table__ is declared
    assert [(c.name, c.nullable) for c in declared.columns] == [
        (name, nullable) for name, _, nullable in COLUMNS
    ]
    found = {
        (constraint.name, tuple(column.name for column in constraint.columns))
        for constraint in declared.constraints
        if type(constraint).__name__ == "UniqueConstraint"
    }
    assert found == {(name, tuple(columns)) for name, columns in UNIQUES}


def test_one_mapping_per_account_and_per_aggregator_account(with_accounts: str) -> None:
    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        session.add(FeedAccountRow(account_id=1, provider_account_id="ACT-1"))
        session.add(FeedAccountRow(account_id=2, provider_account_id="ACT-2"))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(FeedAccountRow(account_id=1, provider_account_id="ACT-3"))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(FeedAccountRow(account_id=2, provider_account_id="ACT-1"))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(FeedAccountRow(account_id=99, provider_account_id="ACT-9"))
    engine.dispose()


def test_downgrade_removes_only_the_table(with_accounts: str) -> None:
    command.downgrade(make_config(with_accounts), "0003")
    assert "feed_accounts" not in table_names(with_accounts)
    assert len(table_names(with_accounts)) == 7
    assert versions(with_accounts) == ["0003"]
    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        assert session.query(AccountRow).count() == 2
    engine.dispose()
