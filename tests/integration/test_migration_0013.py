from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import AdviceRow, ProposalRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
PROPOSALS = [
    ("id", "INTEGER", False),
    ("kind", "VARCHAR(20)", False),
    ("target_id", "INTEGER", False),
    ("value", "VARCHAR(200)", False),
    ("reason", "VARCHAR(200)", False),
    ("status", "VARCHAR(10)", False),
    ("created_at", "DATETIME", False),
    ("decided_at", "DATETIME", True),
]
ADVICE = [
    ("id", "INTEGER", False),
    ("created_at", "DATETIME", False),
    ("subject", "VARCHAR(100)", False),
    ("text", "VARCHAR(1000)", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_0013_follows_0012() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0013")
    assert script.down_revision == "0012"


@pytest.mark.parametrize(
    ("table", "columns", "row", "key"),
    [
        ("proposals", PROPOSALS, ProposalRow, "pk_proposals"),
        ("advice_log", ADVICE, AdviceRow, "pk_advice_log"),
    ],
)
def test_the_tables_and_their_row_classes(
    url: str, table: str, columns: list, row: type, key: str
) -> None:
    command.upgrade(make_config(url), "0013")
    engine = get_engine(url)
    found = inspect(engine)
    shown = [(c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns(table)]
    primary = found.get_pk_constraint(table)
    extras = (
        found.get_unique_constraints(table),
        found.get_foreign_keys(table),
        found.get_indexes(table),
    )
    engine.dispose()
    assert shown == columns
    assert (primary["name"], primary["constrained_columns"]) == (key, ["id"])
    assert extras == ([], [], [])
    assert [(c.name, str(c.type), c.nullable) for c in row.__table__.columns] == columns


def test_down_and_up_again(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0013")
    command.downgrade(config, "0012")
    engine = get_engine(url)
    names = inspect(engine).get_table_names()
    engine.dispose()
    assert "proposals" not in names and "advice_log" not in names
    command.upgrade(config, "0013")
