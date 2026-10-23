from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import AuditRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
COLUMNS = [
    ("id", "INTEGER", False),
    ("at", "DATETIME", False),
    ("who", "VARCHAR(10)", False),
    ("action", "VARCHAR(30)", False),
    ("kind", "VARCHAR(20)", False),
    ("record_id", "INTEGER", True),
    ("before", "VARCHAR(200)", True),
    ("after", "VARCHAR(200)", True),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_0012_follows_0011() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0012")
    assert script.down_revision == "0011"


def test_the_table_and_its_row_class(url: str) -> None:
    command.upgrade(make_config(url), "0012")
    engine = get_engine(url)
    found = inspect(engine)
    columns = [(c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns("audit_log")]
    primary = found.get_pk_constraint("audit_log")
    extras = (
        found.get_unique_constraints("audit_log"),
        found.get_foreign_keys("audit_log"),
        found.get_indexes("audit_log"),
    )
    engine.dispose()
    assert columns == COLUMNS
    assert (primary["name"], primary["constrained_columns"]) == ("pk_audit_log", ["id"])
    assert extras == ([], [], [])
    assert [(c.name, str(c.type), c.nullable) for c in AuditRow.__table__.columns] == COLUMNS


def test_down_and_up_again(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0012")
    command.downgrade(config, "0011")
    engine = get_engine(url)
    assert "audit_log" not in inspect(engine).get_table_names()
    engine.dispose()
    command.upgrade(config, "0012")
    engine = get_engine(url)
    assert "audit_log" in inspect(engine).get_table_names()
    engine.dispose()
