from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import Base, TransferPairRow, TransferRejectionRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0009_transfers.py"
COLUMNS = {
    "transfer_pairs": [
        ("id", "INTEGER", False),
        ("out_transaction_id", "INTEGER", False),
        ("in_transaction_id", "INTEGER", False),
        ("status", "VARCHAR(10)", False),
    ],
    "transfer_rejections": [
        ("id", "INTEGER", False),
        ("out_transaction_id", "INTEGER", False),
        ("in_transaction_id", "INTEGER", False),
    ],
}
UNIQUES = {
    "transfer_pairs": [
        ("uq_transfer_pairs_in_transaction_id", ["in_transaction_id"]),
        ("uq_transfer_pairs_out_transaction_id", ["out_transaction_id"]),
    ],
    "transfer_rejections": [
        ("uq_transfer_rejections_pair", ["out_transaction_id", "in_transaction_id"])
    ],
}


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def at_0009(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    command.upgrade(make_config(url), "0009")
    return url


def test_0009_follows_0008(tmp_path: Path) -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0009")
    assert script.down_revision == "0008"


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source


@pytest.mark.parametrize("table", sorted(COLUMNS))
def test_columns_keys_and_constraints(at_0009: str, table: str) -> None:
    engine = get_engine(at_0009)
    found = inspect(engine)
    columns = [(c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns(table)]
    uniques = sorted((u["name"], u["column_names"]) for u in found.get_unique_constraints(table))
    foreign = sorted(
        (item["constrained_columns"], item["referred_table"])
        for item in found.get_foreign_keys(table)
    )
    primary = found.get_pk_constraint(table)
    engine.dispose()
    assert columns == COLUMNS[table]
    assert uniques == UNIQUES[table]
    assert foreign == [
        (["in_transaction_id"], "transactions"),
        (["out_transaction_id"], "transactions"),
    ]
    assert (primary["name"], primary["constrained_columns"]) == (f"pk_{table}", ["id"])


@pytest.mark.parametrize(
    ("row_class", "table"),
    [(TransferPairRow, "transfer_pairs"), (TransferRejectionRow, "transfer_rejections")],
)
def test_the_orm_classes_match(at_0009: str, row_class, table: str) -> None:
    assert row_class.__table__ is Base.metadata.tables[table]
    assert [
        (column.name, str(column.type), column.nullable) for column in row_class.__table__.columns
    ] == COLUMNS[table]


def test_downgrade_removes_only_the_two_tables(at_0009: str) -> None:
    command.downgrade(make_config(at_0009), "0008")
    engine = get_engine(at_0009)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert names.isdisjoint({"transfer_pairs", "transfer_rejections"})
    assert "transaction_categories" in names
