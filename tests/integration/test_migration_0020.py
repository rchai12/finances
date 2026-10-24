from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import finances.db
from finances.db.engine import get_engine
from finances.db.orm import SettlementRow, SharedExpenseRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SHARED = [
    ("id", "INTEGER", False),
    ("transaction_id", "INTEGER", False),
    ("payer_id", "INTEGER", False),
    ("debtor_id", "INTEGER", False),
    ("owed_cents", "INTEGER", False),
]
SETTLEMENTS = [
    ("id", "INTEGER", False),
    ("payer_id", "INTEGER", False),
    ("payee_id", "INTEGER", False),
    ("amount_cents", "INTEGER", False),
    ("day", "DATE", False),
]


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


def test_0020_follows_0019() -> None:
    script = ScriptDirectory.from_config(make_config("sqlite://")).get_revision("0020")
    assert script.down_revision == "0019"


@pytest.mark.parametrize(
    ("table", "columns", "row", "uniques", "keys"),
    [
        (
            "shared_expenses",
            SHARED,
            SharedExpenseRow,
            [("uq_shared_expenses_transaction_id", ["transaction_id"])],
            [
                ("fk_shared_expenses_debtor_id_people", ["debtor_id"], "people"),
                ("fk_shared_expenses_payer_id_people", ["payer_id"], "people"),
                (
                    "fk_shared_expenses_transaction_id_transactions",
                    ["transaction_id"],
                    "transactions",
                ),
            ],
        ),
        (
            "settlements",
            SETTLEMENTS,
            SettlementRow,
            [],
            [
                ("fk_settlements_payee_id_people", ["payee_id"], "people"),
                ("fk_settlements_payer_id_people", ["payer_id"], "people"),
            ],
        ),
    ],
)
def test_the_tables_and_their_row_classes(
    url: str, table: str, columns: list, row: type, uniques: list, keys: list
) -> None:
    command.upgrade(make_config(url), "0020")
    engine = get_engine(url)
    found = inspect(engine)
    shown = [(c["name"], str(c["type"]), c["nullable"]) for c in found.get_columns(table)]
    primary = found.get_pk_constraint(table)
    unique = [(u["name"], u["column_names"]) for u in found.get_unique_constraints(table)]
    key = sorted(
        (k["name"], k["constrained_columns"], k["referred_table"])
        for k in found.get_foreign_keys(table)
    )
    engine.dispose()
    assert shown == columns
    assert (primary["name"], primary["constrained_columns"]) == (f"pk_{table}", ["id"])
    assert (unique, key) == (uniques, keys)
    orm = [(c.name, str(c.type), c.nullable) for c in row.__table__.columns]
    assert orm[: len(columns)] == columns


def test_down_and_up_again(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0020")
    command.downgrade(config, "0019")
    engine = get_engine(url)
    names = inspect(engine).get_table_names()
    engine.dispose()
    assert "shared_expenses" not in names and "settlements" not in names
    command.upgrade(config, "0020")
