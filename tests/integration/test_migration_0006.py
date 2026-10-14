from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import finances.db
from finances.db.engine import get_engine, session_scope
from finances.db.orm import Base

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0006_people.py"
COLUMNS = {
    "people": [("id", "INTEGER", False), ("name", "VARCHAR(100)", False)],
    "account_owners": [
        ("id", "INTEGER", False),
        ("account_id", "INTEGER", False),
        ("person_id", "INTEGER", True),
    ],
    "cardholder_aliases": [
        ("id", "INTEGER", False),
        ("cardholder", "VARCHAR(100)", False),
        ("person_id", "INTEGER", False),
    ],
}
UNIQUES = {
    "people": [("uq_people_name", ["name"])],
    "account_owners": [("uq_account_owners_account_id", ["account_id"])],
    "cardholder_aliases": [("uq_cardholder_aliases_cardholder", ["cardholder"])],
}
FOREIGN_KEYS = {
    "people": [],
    "account_owners": [
        ("fk_account_owners_account_id_accounts", ["account_id"], "accounts"),
        ("fk_account_owners_person_id_people", ["person_id"], "people"),
    ],
    "cardholder_aliases": [
        ("fk_cardholder_aliases_person_id_people", ["person_id"], "people"),
    ],
}
TABLES = sorted(COLUMNS)


def make_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    return config


def table_names(url: str) -> list[str]:
    engine = get_engine(url)
    names = sorted(inspect(engine).get_table_names())
    engine.dispose()
    return names


def versions(url: str) -> list[str]:
    engine = get_engine(url)
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT version_num FROM alembic_version")).all()
    engine.dispose()
    return [row[0] for row in rows]


def reflect(url: str, table: str, what: str) -> list:
    engine = get_engine(url)
    result = getattr(inspect(engine), what)(table)
    engine.dispose()
    return result


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def at_0006(url: str) -> str:
    """A database at revision 0006 only, with two accounts."""
    command.upgrade(make_config(url), "0006")
    engine = get_engine(url)
    with session_scope(engine) as session:
        for name in ("Test Card", "Test Checking"):
            session.execute(
                text(
                    "INSERT INTO accounts"
                    " (name, institution, type, currency, is_active, created_at)"
                    " VALUES (:name, 'Test Bank', 'checking', 'USD', 1, '2026-01-01 00:00:00')"
                ),
                {"name": name},
            )
    engine.dispose()
    return url


def execute(url: str, sql: str, **values: object) -> None:
    engine = get_engine(url)
    with session_scope(engine) as session:
        session.execute(text(sql), values)
    engine.dispose()


def test_0006_follows_0005(url: str) -> None:
    scripts = ScriptDirectory.from_config(make_config(url))
    assert scripts.get_revision("0006").down_revision == "0005"
    assert len(scripts.get_heads()) == 1


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source


@pytest.mark.parametrize("table", TABLES)
def test_columns_keys_and_constraints(at_0006: str, table: str) -> None:
    assert versions(at_0006) == ["0006"]
    columns = reflect(at_0006, table, "get_columns")
    assert [(c["name"], str(c["type"]), c["nullable"]) for c in columns] == COLUMNS[table]
    assert all(c["default"] is None for c in columns)
    primary_key = reflect(at_0006, table, "get_pk_constraint")
    assert (primary_key["name"], primary_key["constrained_columns"]) == (f"pk_{table}", ["id"])
    uniques = reflect(at_0006, table, "get_unique_constraints")
    assert sorted((u["name"], u["column_names"]) for u in uniques) == UNIQUES[table]
    keys = reflect(at_0006, table, "get_foreign_keys")
    found = sorted((k["name"], k["constrained_columns"], k["referred_table"]) for k in keys)
    assert found == FOREIGN_KEYS[table]
    assert reflect(at_0006, table, "get_indexes") == []


@pytest.mark.parametrize("table", TABLES)
def test_the_orm_class_matches_the_migrated_table(at_0006: str, table: str) -> None:
    declared = Base.metadata.tables[table]
    assert [(c.name, c.nullable) for c in declared.columns] == [
        (name, nullable) for name, _, nullable in COLUMNS[table]
    ]
    found = {
        (constraint.name, tuple(column.name for column in constraint.columns))
        for constraint in declared.constraints
        if type(constraint).__name__ == "UniqueConstraint"
    }
    assert found == {(name, tuple(columns)) for name, columns in UNIQUES[table]}


def test_the_tables_hold_people_owners_and_aliases(at_0006: str) -> None:
    execute(at_0006, "INSERT INTO people (name) VALUES ('Alex'), ('Sam')")
    execute(at_0006, "INSERT INTO account_owners (account_id, person_id) VALUES (1, 1), (2, NULL)")
    execute(at_0006, "INSERT INTO cardholder_aliases (cardholder, person_id) VALUES ('SAM DOE', 2)")
    with pytest.raises(IntegrityError):
        execute(at_0006, "INSERT INTO people (name) VALUES ('Alex')")
    with pytest.raises(IntegrityError):
        execute(at_0006, "INSERT INTO account_owners (account_id, person_id) VALUES (1, 2)")
    with pytest.raises(IntegrityError):
        execute(at_0006, "INSERT INTO account_owners (account_id, person_id) VALUES (99, 1)")
    with pytest.raises(IntegrityError):
        execute(at_0006, "INSERT INTO account_owners (account_id, person_id) VALUES (2, 99)")
    with pytest.raises(IntegrityError):
        execute(
            at_0006, "INSERT INTO cardholder_aliases (cardholder, person_id) VALUES ('SAM DOE', 1)"
        )
    with pytest.raises(IntegrityError):
        execute(
            at_0006, "INSERT INTO cardholder_aliases (cardholder, person_id) VALUES ('X', NULL)"
        )


def test_downgrade_removes_only_the_three_tables(at_0006: str) -> None:
    before = table_names(at_0006)
    command.downgrade(make_config(at_0006), "0005")
    assert table_names(at_0006) == [
        name for name in before if name not in ("people", "account_owners", "cardholder_aliases")
    ]
    assert versions(at_0006) == ["0005"]
    command.upgrade(make_config(at_0006), "0006")
    assert {"people", "account_owners", "cardholder_aliases"} <= set(table_names(at_0006))
