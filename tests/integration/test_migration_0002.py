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
from finances.db.orm import AccountRow, BalanceSnapshotRow, StatementRow, TransactionRow

MIGRATIONS = Path(finances.db.__file__).parent / "migrations"
SOURCE = MIGRATIONS / "versions" / "0002_statements.py"
COLUMNS = {
    "statements": [
        ("id", "INTEGER", False),
        ("account_id", "INTEGER", False),
        ("source_filename", "VARCHAR(255)", False),
        ("file_sha256", "VARCHAR(64)", False),
        ("parser_name", "VARCHAR(50)", False),
        ("period_start", "DATE", False),
        ("period_end", "DATE", False),
        ("opening_balance_cents", "BIGINT", False),
        ("closing_balance_cents", "BIGINT", False),
        ("lines_parsed", "INTEGER", False),
        ("rows_inserted", "INTEGER", False),
        ("rows_duplicate", "INTEGER", False),
        ("imported_at", "DATETIME", False),
    ],
    "transactions": [
        ("id", "INTEGER", False),
        ("account_id", "INTEGER", False),
        ("statement_id", "INTEGER", True),
        ("posted_date", "DATE", False),
        ("transaction_date", "DATE", True),
        ("amount_cents", "BIGINT", False),
        ("description", "VARCHAR(500)", False),
        ("section", "VARCHAR(30)", True),
        ("card_last4", "VARCHAR(4)", True),
        ("cardholder", "VARCHAR(100)", True),
        ("external_id", "VARCHAR(100)", True),
        ("source", "VARCHAR(20)", False),
        ("is_pending", "BOOLEAN", False),
        ("fingerprint", "VARCHAR(64)", False),
        ("created_at", "DATETIME", False),
    ],
    "balance_snapshots": [
        ("id", "INTEGER", False),
        ("account_id", "INTEGER", False),
        ("as_of_date", "DATE", False),
        ("balance_cents", "BIGINT", False),
        ("source", "VARCHAR(20)", False),
        ("created_at", "DATETIME", False),
    ],
}
UNIQUES = {
    "statements": [("uq_statements_file_sha256", ["file_sha256"])],
    "transactions": [("uq_transactions_account_fingerprint", ["account_id", "fingerprint"])],
    "balance_snapshots": [
        ("uq_balance_snapshots_account_date_source", ["account_id", "as_of_date", "source"])
    ],
}
FOREIGN_KEYS = {
    "statements": [("fk_statements_account_id_accounts", ["account_id"], "accounts")],
    "transactions": [
        ("fk_transactions_account_id_accounts", ["account_id"], "accounts"),
        ("fk_transactions_statement_id_statements", ["statement_id"], "statements"),
    ],
    "balance_snapshots": [("fk_balance_snapshots_account_id_accounts", ["account_id"], "accounts")],
}
INDEXES = {
    "statements": [],
    "transactions": [
        ("ix_transactions_account_id", ["account_id"]),
        ("ix_transactions_posted_date", ["posted_date"]),
    ],
    "balance_snapshots": [],
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


def transaction(account_id: int, fingerprint: str) -> TransactionRow:
    return TransactionRow(
        account_id=account_id,
        posted_date=date(2026, 1, 5),
        amount_cents=-450,
        description="ACME COFFEE",
        source="statement",
        fingerprint=fingerprint,
    )


@pytest.fixture
def url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def at_0002(url: str) -> str:
    """A database upgraded to revision 0002 only, whatever later migrations exist."""
    command.upgrade(make_config(url), "0002")
    return url


@pytest.fixture
def with_accounts(at_0002: str) -> str:
    engine = get_engine(at_0002)
    with session_scope(engine) as session:
        session.add(AccountRow(name="Test Card", institution="Test Bank", type="credit_card"))
        session.add(AccountRow(name="Test Checking", institution="Test Bank", type="checking"))
    engine.dispose()
    return at_0002


def test_0002_follows_0001(url: str) -> None:
    scripts = ScriptDirectory.from_config(make_config(url))
    assert scripts.get_revision("0002").down_revision == "0001"
    assert len(scripts.get_heads()) == 1


def test_migration_file_is_self_contained() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert "finances" not in source
    assert "server_default" not in source
    assert source.count("DateTime(timezone=True)") == 3


def test_upgrade_adds_the_three_tables(at_0002: str) -> None:
    assert table_names(at_0002) == [
        "accounts",
        "alembic_version",
        "balance_snapshots",
        "statements",
        "transactions",
    ]
    assert versions(at_0002) == ["0002"]


@pytest.mark.parametrize("table", TABLES)
def test_columns_types_and_nulls(at_0002: str, table: str) -> None:
    columns = reflect(at_0002, table, "get_columns")
    found = [(column["name"], str(column["type"]), column["nullable"]) for column in columns]
    assert found == COLUMNS[table]
    assert [column["default"] for column in columns] == [None] * len(columns)


@pytest.mark.parametrize("table", TABLES)
def test_primary_key_is_named(at_0002: str, table: str) -> None:
    primary_key = reflect(at_0002, table, "get_pk_constraint")
    assert primary_key["name"] == f"pk_{table}"
    assert primary_key["constrained_columns"] == ["id"]


@pytest.mark.parametrize("table", TABLES)
def test_unique_constraints(at_0002: str, table: str) -> None:
    uniques = reflect(at_0002, table, "get_unique_constraints")
    assert [(unique["name"], unique["column_names"]) for unique in uniques] == UNIQUES[table]


@pytest.mark.parametrize("table", TABLES)
def test_foreign_keys(at_0002: str, table: str) -> None:
    keys = reflect(at_0002, table, "get_foreign_keys")
    found = sorted((key["name"], key["constrained_columns"], key["referred_table"]) for key in keys)
    assert found == FOREIGN_KEYS[table]
    assert all(key["referred_columns"] == ["id"] for key in keys)


@pytest.mark.parametrize("table", TABLES)
def test_indexes(at_0002: str, table: str) -> None:
    indexes = reflect(at_0002, table, "get_indexes")
    found = sorted((index["name"], index["column_names"]) for index in indexes)
    assert found == INDEXES[table]
    assert all(not index["unique"] for index in indexes)


def test_upgrade_keeps_existing_accounts(url: str) -> None:
    config = make_config(url)
    command.upgrade(config, "0001")
    engine = get_engine(url)
    with session_scope(engine) as session:
        session.add(AccountRow(name="Test Card", institution="Test Bank", type="credit_card"))
    engine.dispose()
    command.upgrade(config, "0002")
    engine = get_engine(url)
    with session_scope(engine) as session:
        names = [row.name for row in session.query(AccountRow).all()]
    engine.dispose()
    assert names == ["Test Card"]


def test_the_tables_work_with_the_orm(with_accounts: str) -> None:
    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        statement = StatementRow(
            account_id=1,
            source_filename="jan.pdf",
            file_sha256="a" * 64,
            parser_name="fake_bank",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            opening_balance_cents=-10000,
            closing_balance_cents=-10450,
            lines_parsed=1,
            rows_inserted=1,
            rows_duplicate=0,
        )
        session.add(statement)
        session.flush()
        row = transaction(1, "f" * 64)
        row.statement_id = statement.id
        session.add(row)
        session.add(
            BalanceSnapshotRow(
                account_id=1, as_of_date=date(2026, 1, 31), balance_cents=-10450, source="statement"
            )
        )
    with session_scope(engine) as session:
        stored = session.query(TransactionRow).one()
        found = (stored.statement_id, stored.is_pending, stored.transaction_date, stored.section)
        assert found == (1, False, None, None)
        assert session.query(StatementRow).one().imported_at is not None
        assert session.query(BalanceSnapshotRow).one().balance_cents == -10450
    engine.dispose()


def test_amounts_beyond_32_bits_are_stored_exactly(with_accounts: str) -> None:
    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        row = transaction(1, "f" * 64)
        row.amount_cents = -9007199254740993
        session.add(row)
    with session_scope(engine) as session:
        assert session.query(TransactionRow).one().amount_cents == -9007199254740993
    engine.dispose()


def test_a_transaction_needs_a_real_account(with_accounts: str) -> None:
    engine = get_engine(with_accounts)
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(transaction(99, "f" * 64))
    engine.dispose()


def test_a_fingerprint_is_unique_within_one_account(with_accounts: str) -> None:
    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        session.add(transaction(1, "f" * 64))
        session.add(transaction(2, "f" * 64))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(transaction(1, "f" * 64))
    engine.dispose()


def test_a_file_hash_is_stored_once(with_accounts: str) -> None:
    def statement(account_id: int) -> StatementRow:
        return StatementRow(
            account_id=account_id,
            source_filename="jan.pdf",
            file_sha256="a" * 64,
            parser_name="fake_bank",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            opening_balance_cents=0,
            closing_balance_cents=0,
            lines_parsed=0,
            rows_inserted=0,
            rows_duplicate=0,
        )

    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        session.add(statement(1))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(statement(2))
    engine.dispose()


def test_one_balance_per_account_date_and_source(with_accounts: str) -> None:
    def snapshot(account_id: int, day: int, source: str) -> BalanceSnapshotRow:
        return BalanceSnapshotRow(
            account_id=account_id, as_of_date=date(2026, 1, day), balance_cents=0, source=source
        )

    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        session.add(snapshot(1, 31, "statement"))
        session.add(snapshot(1, 31, "aggregator"))
        session.add(snapshot(1, 30, "statement"))
        session.add(snapshot(2, 31, "statement"))
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(snapshot(1, 31, "statement"))
    engine.dispose()


def test_downgrade_removes_only_the_three_tables(with_accounts: str) -> None:
    command.downgrade(make_config(with_accounts), "0001")
    assert table_names(with_accounts) == ["accounts", "alembic_version"]
    assert versions(with_accounts) == ["0001"]
    engine = get_engine(with_accounts)
    with session_scope(engine) as session:
        assert session.query(AccountRow).count() == 2
    engine.dispose()


def test_downgrade_then_upgrade_restores_the_tables(at_0002: str) -> None:
    config = make_config(at_0002)
    command.downgrade(config, "0001")
    command.upgrade(config, "0002")
    assert table_names(at_0002)[2:] == ["balance_snapshots", "statements", "transactions"]
    assert reflect(at_0002, "transactions", "get_indexes") != []
