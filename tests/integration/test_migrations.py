from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import finances.db
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, Base, to_account
from finances.domain.models import AccountType

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
COLUMNS = [
    ("id", "INTEGER", False),
    ("name", "VARCHAR(100)", False),
    ("institution", "VARCHAR(100)", False),
    ("type", "VARCHAR(20)", False),
    ("currency", "VARCHAR(3)", False),
    ("last4", "VARCHAR(4)", True),
    ("is_active", "BOOLEAN", False),
    ("created_at", "DATETIME", False),
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
def migrated(url: str) -> str:
    """A database upgraded to revision 0001 only, whatever later migrations exist."""
    command.upgrade(make_config(url), "0001")
    return url


def test_0001_is_the_first_migration(url: str) -> None:
    scripts = ScriptDirectory.from_config(make_config(url))
    assert scripts.get_base() == "0001"
    assert scripts.get_revision("0001").down_revision is None
    assert len(scripts.get_heads()) == 1


def test_migration_file_is_self_contained() -> None:
    source = (MIGRATIONS / "versions" / "0001_accounts.py").read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source


def test_created_at_is_declared_with_a_time_zone() -> None:
    source = (MIGRATIONS / "versions" / "0001_accounts.py").read_text(encoding="utf-8")
    assert "DateTime(timezone=True)" in source


def test_upgrade_creates_the_accounts_table(migrated: str) -> None:
    assert table_names(migrated) == ["accounts", "alembic_version"]


def test_upgrade_records_the_revision(migrated: str) -> None:
    engine = get_engine(migrated)
    with engine.connect() as connection:
        versions = connection.execute(text("SELECT version_num FROM alembic_version")).all()
    engine.dispose()
    assert [row[0] for row in versions] == ["0001"]


def test_columns_types_and_nulls(migrated: str) -> None:
    engine = get_engine(migrated)
    columns = inspect(engine).get_columns("accounts")
    engine.dispose()
    found = [(column["name"], str(column["type"]), column["nullable"]) for column in columns]
    assert found == COLUMNS


def test_no_server_defaults(migrated: str) -> None:
    engine = get_engine(migrated)
    columns = inspect(engine).get_columns("accounts")
    engine.dispose()
    assert [column["default"] for column in columns] == [None] * 8


def test_primary_key_is_named(migrated: str) -> None:
    engine = get_engine(migrated)
    primary_key = inspect(engine).get_pk_constraint("accounts")
    engine.dispose()
    assert primary_key["name"] == "pk_accounts"
    assert primary_key["constrained_columns"] == ["id"]


def test_name_is_the_only_unique_constraint(migrated: str) -> None:
    engine = get_engine(migrated)
    uniques = inspect(engine).get_unique_constraints("accounts")
    engine.dispose()
    assert [(unique["name"], unique["column_names"]) for unique in uniques] == [
        ("uq_accounts_name", ["name"])
    ]


def test_no_indexes_and_no_foreign_keys(migrated: str) -> None:
    engine = get_engine(migrated)
    inspector = inspect(engine)
    indexes = inspector.get_indexes("accounts")
    foreign_keys = inspector.get_foreign_keys("accounts")
    engine.dispose()
    assert indexes == []
    assert foreign_keys == []


def test_fully_migrated_database_matches_the_orm(url: str) -> None:
    command.upgrade(make_config(url), "head")
    engine = get_engine(url)
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert differences == []


def test_upgrade_twice_changes_nothing(migrated: str) -> None:
    command.upgrade(make_config(migrated), "0001")
    assert table_names(migrated) == ["accounts", "alembic_version"]


def test_the_table_works_with_the_orm(migrated: str) -> None:
    engine = get_engine(migrated)
    with session_scope(engine) as session:
        session.add(AccountRow(name="Test Checking", institution="Test Bank", type="checking"))
    with session_scope(engine) as session:
        account = to_account(session.query(AccountRow).one())
    engine.dispose()
    assert account.id == 1
    assert account.type is AccountType.CHECKING
    assert account.currency == "USD"
    assert account.is_active is True


def test_the_table_rejects_a_duplicate_name(migrated: str) -> None:
    engine = get_engine(migrated)
    with session_scope(engine) as session:
        session.add(AccountRow(name="Test Checking", institution="Test Bank", type="checking"))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(AccountRow(name="Test Checking", institution="Other Bank", type="savings"))
    engine.dispose()


def test_upgrade_writes_only_the_database_file(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    command.upgrade(make_config(url), "head")
    assert [path.name for path in tmp_path.iterdir()] == ["test.db"]


def test_downgrade_removes_the_accounts_table(migrated: str) -> None:
    command.downgrade(make_config(migrated), "base")
    assert table_names(migrated) == ["alembic_version"]


def test_downgrade_then_upgrade_restores_the_table(migrated: str) -> None:
    config = make_config(migrated)
    command.downgrade(config, "base")
    command.upgrade(config, "0001")
    assert table_names(migrated) == ["accounts", "alembic_version"]
