from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import MerchantAliasRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
COLUMNS = [
    ("id", "INTEGER", False),
    ("source", "VARCHAR(100)", False),
    ("target", "VARCHAR(100)", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_0016_follows_0015() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0016")
    assert script.down_revision == "0015"


def test_the_table_and_its_row_class(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0016")
    engine = get_engine(url)
    found = inspect(engine)
    shown = [
        (c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns("merchant_aliases")
    ]
    primary = found.get_pk_constraint("merchant_aliases")
    uniques = [
        (u["name"], u["column_names"]) for u in found.get_unique_constraints("merchant_aliases")
    ]
    extras = (found.get_foreign_keys("merchant_aliases"), found.get_indexes("merchant_aliases"))
    engine.dispose()
    assert shown == COLUMNS
    assert (primary["name"], primary["constrained_columns"]) == ("pk_merchant_aliases", ["id"])
    assert uniques == [("uq_merchant_aliases_source", ["source"])]
    assert extras == ([], [])
    orm = [(c.name, str(c.type), c.nullable) for c in MerchantAliasRow.__table__.columns]
    assert orm[: len(COLUMNS)] == COLUMNS
    command.downgrade(config, "0015")
    engine = get_engine(url)
    names = inspect(engine).get_table_names()
    engine.dispose()
    assert "merchant_aliases" not in names
    command.upgrade(config, "0016")
