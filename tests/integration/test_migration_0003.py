from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import finances.db
from finances.db.engine import get_engine, session_scope
from finances.db.orm import AccountRow, Base, FeedItemRow, FeedPullRow, TransactionRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0003_feed.py"
COLUMNS = {
    "feed_items": [
        ("id", "INTEGER", False),
        ("account_id", "INTEGER", False),
        ("feed_id", "VARCHAR(100)", False),
        ("transaction_id", "INTEGER", False),
    ],
    "feed_pulls": [
        ("id", "INTEGER", False),
        ("account_id", "INTEGER", False),
        ("inserted", "INTEGER", False),
        ("updated", "INTEGER", False),
        ("removed", "INTEGER", False),
        ("unchanged", "INTEGER", False),
        ("feed_total_cents", "BIGINT", False),
        ("balance_cents", "BIGINT", True),
        ("balance_date", "DATE", True),
        ("drift_cents", "BIGINT", True),
        ("pulled_at", "DATETIME", False),
    ],
}
UNIQUES = {
    "feed_items": [
        ("uq_feed_items_account_feed", ["account_id", "feed_id"]),
        ("uq_feed_items_transaction_id", ["transaction_id"]),
    ],
    "feed_pulls": [],
}
FOREIGN_KEYS = {
    "feed_items": [
        ("fk_feed_items_account_id_accounts", ["account_id"], "accounts"),
        ("fk_feed_items_transaction_id_transactions", ["transaction_id"], "transactions"),
    ],
    "feed_pulls": [("fk_feed_pulls_account_id_accounts", ["account_id"], "accounts")],
}
INDEXES = {"feed_items": [], "feed_pulls": [("ix_feed_pulls_account_id", ["account_id"])]}
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


def transaction(account_id: int, fingerprint: str) -> TransactionRow:
    return TransactionRow(
        account_id=account_id,
        posted_date=date(2026, 1, 5),
        amount_cents=-450,
        description="ACME COFFEE",
        source="aggregator",
        fingerprint=fingerprint,
    )


def pull(account_id: int, **changes: object) -> FeedPullRow:
    values = {"inserted": 0, "updated": 0, "removed": 0, "unchanged": 0, "feed_total_cents": 0}
    return FeedPullRow(account_id=account_id, **{**values, **changes})


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def at_0003(url: str) -> str:
    """A database upgraded to revision 0003 only, whatever later migrations exist."""
    command.upgrade(make_config(url), "0003")
    return url


@pytest.fixture
def with_rows(at_0003: str) -> str:
    """Two accounts, and three transactions: ids 1 and 2 in account 1, id 3 in account 2."""
    engine = get_engine(at_0003)
    with session_scope(engine) as session:
        session.add(AccountRow(name="Test Card", institution="Test Bank", type="credit_card"))
        session.add(AccountRow(name="Test Checking", institution="Test Bank", type="checking"))
        session.flush()
        session.add(transaction(1, "a" * 64))
        session.add(transaction(1, "b" * 64))
        session.add(transaction(2, "c" * 64))
    engine.dispose()
    return at_0003


def test_0003_follows_0002(url: str) -> None:
    scripts = ScriptDirectory.from_config(make_config(url))
    assert scripts.get_revision("0003").down_revision == "0002"
    assert len(scripts.get_heads()) == 1


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source
    assert source.count("DateTime(timezone=True)") == 1


def test_upgrade_adds_the_two_tables(at_0003: str) -> None:
    assert table_names(at_0003) == [
        "accounts",
        "alembic_version",
        "balance_snapshots",
        "feed_items",
        "feed_pulls",
        "statements",
        "transactions",
    ]
    assert versions(at_0003) == ["0003"]


@pytest.mark.parametrize("table", TABLES)
def test_columns_types_and_nulls(at_0003: str, table: str) -> None:
    columns = reflect(at_0003, table, "get_columns")
    found = [(column["name"], str(column["type"]), column["nullable"]) for column in columns]
    assert found == COLUMNS[table]
    assert [column["default"] for column in columns] == [None] * len(columns)


@pytest.mark.parametrize("table", TABLES)
def test_primary_key_is_named(at_0003: str, table: str) -> None:
    primary_key = reflect(at_0003, table, "get_pk_constraint")
    assert primary_key["name"] == f"pk_{table}"
    assert primary_key["constrained_columns"] == ["id"]


@pytest.mark.parametrize("table", TABLES)
def test_unique_constraints(at_0003: str, table: str) -> None:
    uniques = reflect(at_0003, table, "get_unique_constraints")
    found = sorted((unique["name"], unique["column_names"]) for unique in uniques)
    assert found == UNIQUES[table]


@pytest.mark.parametrize("table", TABLES)
def test_foreign_keys(at_0003: str, table: str) -> None:
    keys = reflect(at_0003, table, "get_foreign_keys")
    found = sorted((key["name"], key["constrained_columns"], key["referred_table"]) for key in keys)
    assert found == FOREIGN_KEYS[table]
    assert all(key["referred_columns"] == ["id"] for key in keys)


@pytest.mark.parametrize("table", TABLES)
def test_indexes(at_0003: str, table: str) -> None:
    indexes = reflect(at_0003, table, "get_indexes")
    found = sorted((index["name"], index["column_names"]) for index in indexes)
    assert found == INDEXES[table]
    assert all(not index["unique"] for index in indexes)


@pytest.mark.parametrize("table", TABLES)
def test_the_orm_class_matches_the_migrated_table(at_0003: str, table: str) -> None:
    declared = Base.metadata.tables[table]
    columns = reflect(at_0003, table, "get_columns")
    assert [column.name for column in declared.columns] == [column["name"] for column in columns]
    assert [column.nullable for column in declared.columns] == [
        column["nullable"] for column in columns
    ]
    declared_uniques = {
        (constraint.name, tuple(column.name for column in constraint.columns))
        for constraint in declared.constraints
        if type(constraint).__name__ == "UniqueConstraint"
    }
    assert declared_uniques == {(name, tuple(columns)) for name, columns in UNIQUES[table]}
    assert {
        (index.name, tuple(column.name for column in index.columns)) for index in declared.indexes
    } == {(name, tuple(columns)) for name, columns in INDEXES[table]}


def test_upgrade_keeps_existing_transactions(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0002")
    engine = get_engine(url)
    with session_scope(engine) as session:
        session.add(AccountRow(name="Test Card", institution="Test Bank", type="credit_card"))
        session.flush()
        session.add(transaction(1, "a" * 64))
    engine.dispose()
    command.upgrade(config, "0003")
    engine = get_engine(url)
    with session_scope(engine) as session:
        assert [row.fingerprint for row in session.query(TransactionRow).all()] == ["a" * 64]
    engine.dispose()


def test_the_tables_work_with_the_orm(with_rows: str) -> None:
    engine = get_engine(with_rows)
    with session_scope(engine) as session:
        session.add(FeedItemRow(account_id=1, feed_id="feed-1", transaction_id=1))
        session.add(pull(1))
        session.add(
            pull(1, balance_cents=-(2**40), balance_date=date(2026, 1, 31), drift_cents=2**40 + 1)
        )
    with session_scope(engine) as session:
        assert session.query(FeedItemRow).one().feed_id == "feed-1"
        first, second = session.query(FeedPullRow).order_by(FeedPullRow.id).all()
        assert (first.balance_cents, first.balance_date, first.drift_cents) == (None, None, None)
        assert first.pulled_at is not None
        assert (second.balance_cents, second.drift_cents) == (-(2**40), 2**40 + 1)
        assert second.balance_date == date(2026, 1, 31)
    engine.dispose()


def test_a_feed_id_is_unique_within_one_account(with_rows: str) -> None:
    engine = get_engine(with_rows)
    with session_scope(engine) as session:
        session.add(FeedItemRow(account_id=1, feed_id="same", transaction_id=1))
        session.add(FeedItemRow(account_id=2, feed_id="same", transaction_id=3))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(FeedItemRow(account_id=1, feed_id="same", transaction_id=2))
    engine.dispose()


def test_a_transaction_has_at_most_one_feed_id(with_rows: str) -> None:
    engine = get_engine(with_rows)
    with session_scope(engine) as session:
        session.add(FeedItemRow(account_id=1, feed_id="one", transaction_id=1))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(FeedItemRow(account_id=1, feed_id="two", transaction_id=1))
    engine.dispose()


def test_a_feed_item_needs_a_real_transaction_and_account(with_rows: str) -> None:
    engine = get_engine(with_rows)
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(FeedItemRow(account_id=1, feed_id="one", transaction_id=99))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(FeedItemRow(account_id=99, feed_id="one", transaction_id=1))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(pull(99))
    engine.dispose()


def test_downgrade_removes_only_the_two_tables(with_rows: str) -> None:
    command.downgrade(make_config(with_rows), "0002")
    assert table_names(with_rows) == [
        "accounts",
        "alembic_version",
        "balance_snapshots",
        "statements",
        "transactions",
    ]
    assert versions(with_rows) == ["0002"]
    engine = get_engine(with_rows)
    with session_scope(engine) as session:
        assert session.query(TransactionRow).count() == 3
    engine.dispose()


def test_downgrade_then_upgrade_restores_the_tables(at_0003: str) -> None:
    config = make_config(at_0003)
    command.downgrade(config, "0002")
    command.upgrade(config, "0003")
    assert table_names(at_0003)[3:5] == ["feed_items", "feed_pulls"]
    assert reflect(at_0003, "feed_pulls", "get_indexes") != []
