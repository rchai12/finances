from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import TransactionNoteRow, TransactionTagRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
TAGS = [
    ("id", "INTEGER", False),
    ("transaction_id", "INTEGER", False),
    ("tag", "VARCHAR(30)", False),
]
NOTES = [
    ("id", "INTEGER", False),
    ("transaction_id", "INTEGER", False),
    ("text", "VARCHAR(500)", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_0018_follows_0017() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0018")
    assert script.down_revision == "0017"


@pytest.mark.parametrize(
    ("table", "columns", "row", "unique"),
    [
        (
            "transaction_tags",
            TAGS,
            TransactionTagRow,
            ("uq_transaction_tags_transaction_id_tag", ["transaction_id", "tag"]),
        ),
        (
            "transaction_notes",
            NOTES,
            TransactionNoteRow,
            ("uq_transaction_notes_transaction_id", ["transaction_id"]),
        ),
    ],
)
def test_the_tables_and_their_row_classes(
    url: str, table: str, columns: list, row: type, unique: tuple
) -> None:
    command.upgrade(make_config(url), "0018")
    engine = get_engine(url)
    found = inspect(engine)
    shown = [(c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns(table)]
    primary = found.get_pk_constraint(table)
    uniques = [(u["name"], u["column_names"]) for u in found.get_unique_constraints(table)]
    keys = [
        (k["name"], k["constrained_columns"], k["referred_table"])
        for k in found.get_foreign_keys(table)
    ]
    engine.dispose()
    assert shown == columns
    assert (primary["name"], primary["constrained_columns"]) == (f"pk_{table}", ["id"])
    assert uniques == [unique]
    assert keys == [(f"fk_{table}_transaction_id_transactions", ["transaction_id"], "transactions")]
    orm = [(c.name, str(c.type), c.nullable) for c in row.__table__.columns]
    assert orm[: len(columns)] == columns


def test_down_and_up_again(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0018")
    command.downgrade(config, "0017")
    engine = get_engine(url)
    names = inspect(engine).get_table_names()
    engine.dispose()
    assert "transaction_tags" not in names and "transaction_notes" not in names
    command.upgrade(config, "0018")
