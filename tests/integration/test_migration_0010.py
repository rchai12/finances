from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import Base, BudgetRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
COLUMNS = [
    ("id", "INTEGER", False),
    ("category_id", "INTEGER", False),
    ("amount_cents", "BIGINT", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def at_0010(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    command.upgrade(make_config(url), "0010")
    return url


def test_0010_follows_0009() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0010")
    assert script.down_revision == "0009"


def test_the_table(at_0010: str) -> None:
    engine = get_engine(at_0010)
    found = inspect(engine)
    columns = [(c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns("budgets")]
    uniques = [(u["name"], u["column_names"]) for u in found.get_unique_constraints("budgets")]
    foreign = [
        (f["constrained_columns"], f["referred_table"]) for f in found.get_foreign_keys("budgets")
    ]
    primary = found.get_pk_constraint("budgets")
    engine.dispose()
    assert columns == COLUMNS
    assert uniques == [("uq_budgets_category_id", ["category_id"])]
    assert foreign == [(["category_id"], "categories")]
    assert (primary["name"], primary["constrained_columns"]) == ("pk_budgets", ["id"])
    assert [(c.name, str(c.type), c.nullable) for c in BudgetRow.__table__.columns] == COLUMNS
    assert BudgetRow.__table__ is Base.metadata.tables["budgets"]


def test_downgrade_removes_only_the_table(at_0010: str) -> None:
    command.downgrade(make_config(at_0010), "0009")
    engine = get_engine(at_0010)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert "budgets" not in names and "transfer_pairs" in names
