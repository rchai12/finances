from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import FindingStatusRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
COLUMNS = [
    ("id", "INTEGER", False),
    ("type", "VARCHAR(30)", False),
    ("subject", "VARCHAR(100)", False),
    ("month", "DATE", True),
    ("status", "VARCHAR(10)", False),
    ("set_at", "DATETIME", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_0025_follows_0024() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0025")
    assert script.down_revision == "0024"


def test_the_table_and_its_row_class(url: str) -> None:
    command.upgrade(make_config(url), "0025")
    engine = get_engine(url)
    found = inspect(engine)
    shown = [
        (c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns("finding_statuses")
    ]
    primary = found.get_pk_constraint("finding_statuses")
    others = (
        found.get_unique_constraints("finding_statuses"),
        found.get_foreign_keys("finding_statuses"),
    )
    engine.dispose()
    assert shown == COLUMNS
    assert (primary["name"], primary["constrained_columns"]) == ("pk_finding_statuses", ["id"])
    assert others == ([], [])
    orm = [(c.name, str(c.type), c.nullable) for c in FindingStatusRow.__table__.columns]
    assert orm == COLUMNS
    assert FindingStatusRow.__tablename__ == "finding_statuses"


def test_down_and_up_again(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0025")
    command.downgrade(config, "0024")
    engine = get_engine(url)
    names = inspect(engine).get_table_names()
    engine.dispose()
    assert "finding_statuses" not in names
    command.upgrade(config, "0025")
