from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import TransactionSplitRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
COLUMNS = [
    ("id", "INTEGER", False),
    ("transaction_id", "INTEGER", False),
    ("position", "INTEGER", False),
    ("amount_cents", "INTEGER", False),
    ("category_id", "INTEGER", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_0019_follows_0018() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0019")
    assert script.down_revision == "0018"


def test_the_table_and_its_row_class(url: str) -> None:
    command.upgrade(make_config(url), "0019")
    engine = get_engine(url)
    found = inspect(engine)
    shown = [
        (c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns("transaction_splits")
    ]
    primary = found.get_pk_constraint("transaction_splits")
    uniques = [
        (u["name"], u["column_names"]) for u in found.get_unique_constraints("transaction_splits")
    ]
    keys = sorted(
        (k["name"], k["constrained_columns"], k["referred_table"])
        for k in found.get_foreign_keys("transaction_splits")
    )
    engine.dispose()
    assert shown == COLUMNS
    assert (primary["name"], primary["constrained_columns"]) == ("pk_transaction_splits", ["id"])
    assert uniques == [
        ("uq_transaction_splits_transaction_id_position", ["transaction_id", "position"])
    ]
    assert keys == [
        ("fk_transaction_splits_category_id_categories", ["category_id"], "categories"),
        ("fk_transaction_splits_transaction_id_transactions", ["transaction_id"], "transactions"),
    ]
    orm = [(c.name, str(c.type), c.nullable) for c in TransactionSplitRow.__table__.columns]
    assert orm[: len(COLUMNS)] == COLUMNS


def test_down_and_up_again(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0019")
    command.downgrade(config, "0018")
    engine = get_engine(url)
    names = inspect(engine).get_table_names()
    engine.dispose()
    assert "transaction_splits" not in names
    command.upgrade(config, "0019")
