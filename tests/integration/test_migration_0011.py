from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import Base, SyncFailureRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
COLUMNS = [
    ("id", "INTEGER", False),
    ("link", "VARCHAR(30)", False),
    ("failed_at", "DATETIME", False),
    ("message", "VARCHAR(200)", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def at_0011(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    command.upgrade(make_config(url), "0011")
    return url


def test_0011_follows_0010() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0011")
    assert script.down_revision == "0010"


def test_the_table(at_0011: str) -> None:
    engine = get_engine(at_0011)
    found = inspect(engine)
    columns = [
        (c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns("sync_failures")
    ]
    uniques = [
        (u["name"], u["column_names"]) for u in found.get_unique_constraints("sync_failures")
    ]
    foreign = [
        (f["constrained_columns"], f["referred_table"])
        for f in found.get_foreign_keys("sync_failures")
    ]
    primary = found.get_pk_constraint("sync_failures")
    engine.dispose()
    assert columns == COLUMNS
    assert uniques == [("uq_sync_failures_link", ["link"])]
    assert foreign == []
    assert (primary["name"], primary["constrained_columns"]) == ("pk_sync_failures", ["id"])
    assert [(c.name, str(c.type), c.nullable) for c in SyncFailureRow.__table__.columns] == COLUMNS
    assert SyncFailureRow.__table__ is Base.metadata.tables["sync_failures"]


def test_downgrade_removes_only_the_table(at_0011: str) -> None:
    command.downgrade(make_config(at_0011), "0010")
    engine = get_engine(at_0011)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert "sync_failures" not in names and "budgets" in names
