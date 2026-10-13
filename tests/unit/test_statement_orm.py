from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Enum, Integer, String

from finances.db.orm import (
    BalanceSnapshotRow,
    StatementRow,
    TransactionRow,
    to_balance_snapshot,
    to_statement,
    to_transaction,
)
from finances.domain.models import BalanceSnapshot, DataSource, Statement, Transaction

WHEN = datetime(2026, 2, 3, 4, 5, 6, tzinfo=UTC)
NAIVE = datetime(2026, 2, 3, 4, 5, 6)
PLUS_FIVE = timezone(timedelta(hours=5))
AWARE = datetime(2026, 2, 3, 9, 5, 6, tzinfo=PLUS_FIVE)

STATEMENT_COLUMNS = [
    "id",
    "account_id",
    "source_filename",
    "file_sha256",
    "parser_name",
    "period_start",
    "period_end",
    "opening_balance_cents",
    "closing_balance_cents",
    "lines_parsed",
    "rows_inserted",
    "rows_duplicate",
    "imported_at",
]
TRANSACTION_COLUMNS = [
    "id",
    "account_id",
    "statement_id",
    "posted_date",
    "transaction_date",
    "amount_cents",
    "description",
    "section",
    "card_last4",
    "cardholder",
    "external_id",
    "source",
    "is_pending",
    "fingerprint",
    "created_at",
]
SNAPSHOT_COLUMNS = [
    "id",
    "account_id",
    "as_of_date",
    "balance_cents",
    "source",
    "created_at",
]
COLUMN_TYPES = {
    "statements": {
        "id": (Integer, None),
        "account_id": (Integer, None),
        "source_filename": (String, 255),
        "file_sha256": (String, 64),
        "parser_name": (String, 50),
        "period_start": (Date, None),
        "period_end": (Date, None),
        "opening_balance_cents": (BigInteger, None),
        "closing_balance_cents": (BigInteger, None),
        "lines_parsed": (Integer, None),
        "rows_inserted": (Integer, None),
        "rows_duplicate": (Integer, None),
        "imported_at": (DateTime, None),
    },
    "transactions": {
        "id": (Integer, None),
        "account_id": (Integer, None),
        "statement_id": (Integer, None),
        "posted_date": (Date, None),
        "transaction_date": (Date, None),
        "amount_cents": (BigInteger, None),
        "description": (String, 500),
        "section": (String, 30),
        "card_last4": (String, 4),
        "cardholder": (String, 100),
        "external_id": (String, 100),
        "source": (String, 20),
        "is_pending": (Boolean, None),
        "fingerprint": (String, 64),
        "created_at": (DateTime, None),
    },
    "balance_snapshots": {
        "id": (Integer, None),
        "account_id": (Integer, None),
        "as_of_date": (Date, None),
        "balance_cents": (BigInteger, None),
        "source": (String, 20),
        "created_at": (DateTime, None),
    },
}
NULLABLE = {
    "statements": set(),
    "transactions": {
        "statement_id",
        "transaction_date",
        "section",
        "card_last4",
        "cardholder",
        "external_id",
    },
    "balance_snapshots": set(),
}
TABLES = {
    "statements": StatementRow.__table__,
    "transactions": TransactionRow.__table__,
    "balance_snapshots": BalanceSnapshotRow.__table__,
}
COLUMN_NAMES = {
    "statements": STATEMENT_COLUMNS,
    "transactions": TRANSACTION_COLUMNS,
    "balance_snapshots": SNAPSHOT_COLUMNS,
}


def test_column_names_are_in_order() -> None:
    for name, table in TABLES.items():
        assert [column.name for column in table.columns] == COLUMN_NAMES[name]


@pytest.mark.parametrize("table_name", sorted(TABLES))
def test_column_types_lengths_and_nulls(table_name: str) -> None:
    table = TABLES[table_name]
    for column in table.columns:
        type_class, length = COLUMN_TYPES[table_name][column.name]
        assert isinstance(column.type, type_class)
        assert not isinstance(column.type, Enum)
        if length is not None:
            assert column.type.length == length
        assert column.nullable is (column.name in NULLABLE[table_name])


def test_source_and_section_are_plain_strings() -> None:
    assert isinstance(TransactionRow.__table__.columns["source"].type, String)
    assert isinstance(TransactionRow.__table__.columns["section"].type, String)
    assert isinstance(BalanceSnapshotRow.__table__.columns["source"].type, String)
    assert isinstance(StatementRow.__table__.columns["parser_name"].type, String)


def test_keys_constraints_and_indexes_use_the_design_names() -> None:
    statements = StatementRow.__table__
    transactions = TransactionRow.__table__
    snapshots = BalanceSnapshotRow.__table__
    assert statements.primary_key.name == "pk_statements"
    assert transactions.primary_key.name == "pk_transactions"
    assert snapshots.primary_key.name == "pk_balance_snapshots"
    assert _uniques(statements) == {"uq_statements_file_sha256": ["file_sha256"]}
    assert _uniques(transactions) == {
        "uq_transactions_account_fingerprint": ["account_id", "fingerprint"]
    }
    assert _uniques(snapshots) == {
        "uq_balance_snapshots_account_date_source": ["account_id", "as_of_date", "source"]
    }
    assert _foreign_keys(statements) == {"fk_statements_account_id_accounts": ["account_id"]}
    assert _foreign_keys(transactions) == {
        "fk_transactions_account_id_accounts": ["account_id"],
        "fk_transactions_statement_id_statements": ["statement_id"],
    }
    assert _foreign_keys(snapshots) == {"fk_balance_snapshots_account_id_accounts": ["account_id"]}
    indexes = {
        (index.name, tuple(column.name for column in index.columns), index.unique)
        for index in transactions.indexes
    }
    assert indexes == {
        ("ix_transactions_account_id", ("account_id",), False),
        ("ix_transactions_posted_date", ("posted_date",), False),
    }
    assert list(statements.indexes) == []
    assert list(snapshots.indexes) == []


def test_python_defaults_and_no_server_defaults() -> None:
    for table in TABLES.values():
        for column in table.columns:
            assert column.server_default is None
    assert TransactionRow.__table__.columns["is_pending"].default.arg is False
    for table, column_name in (
        (StatementRow.__table__, "imported_at"),
        (TransactionRow.__table__, "created_at"),
        (BalanceSnapshotRow.__table__, "created_at"),
    ):
        column = table.columns[column_name]
        assert column.type.timezone is True
        value = column.default.arg(None)
        assert value.utcoffset() == timedelta(0)
        assert abs(datetime.now(UTC) - value) < timedelta(minutes=1)


def test_other_columns_have_no_python_default() -> None:
    skipped = {("transactions", "is_pending")}
    timestamps = {
        ("statements", "imported_at"),
        ("transactions", "created_at"),
        ("balance_snapshots", "created_at"),
    }
    for table_name, table in TABLES.items():
        for column in table.columns:
            key = (table_name, column.name)
            if key in skipped or key in timestamps:
                continue
            assert column.default is None


def test_to_statement_copies_every_field() -> None:
    row = StatementRow(
        id=4,
        account_id=8,
        source_filename="jan.pdf",
        file_sha256="a" * 64,
        parser_name="fake_bank",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        opening_balance_cents=-10000,
        closing_balance_cents=-8499,
        lines_parsed=4,
        rows_inserted=3,
        rows_duplicate=1,
        imported_at=WHEN,
    )
    assert to_statement(row) == Statement(
        id=4,
        account_id=8,
        source_filename="jan.pdf",
        file_sha256="a" * 64,
        parser_name="fake_bank",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        opening_balance_cents=-10000,
        closing_balance_cents=-8499,
        lines_parsed=4,
        rows_inserted=3,
        rows_duplicate=1,
        imported_at=WHEN,
    )


def test_to_transaction_copies_every_field_and_the_source_enum() -> None:
    row = _transaction_row(source="aggregator", is_pending=True, created_at=WHEN)
    assert to_transaction(row) == Transaction(
        id=9,
        account_id=8,
        statement_id=4,
        posted_date=date(2026, 1, 5),
        transaction_date=date(2026, 1, 4),
        amount_cents=-450,
        description="ACME COFFEE",
        section="purchases",
        card_last4="2222",
        cardholder="A PERSON",
        external_id="7838",
        source=DataSource.AGGREGATOR,
        is_pending=True,
        fingerprint="f" * 64,
        created_at=WHEN,
    )
    assert to_transaction(row).source is DataSource.AGGREGATOR


def test_to_transaction_rejects_an_unknown_source() -> None:
    with pytest.raises(ValueError):
        to_transaction(_transaction_row(source="brokerage"))


def test_to_balance_snapshot_copies_every_field() -> None:
    row = BalanceSnapshotRow(
        id=2,
        account_id=8,
        as_of_date=date(2026, 1, 31),
        balance_cents=-8499,
        source="statement",
        created_at=WHEN,
    )
    found = to_balance_snapshot(row)
    assert found == BalanceSnapshot(
        id=2,
        account_id=8,
        as_of_date=date(2026, 1, 31),
        balance_cents=-8499,
        source=DataSource.STATEMENT,
        created_at=WHEN,
    )
    assert found.source is DataSource.STATEMENT


def test_to_balance_snapshot_rejects_an_unknown_source() -> None:
    row = BalanceSnapshotRow(
        id=2,
        account_id=8,
        as_of_date=date(2026, 1, 31),
        balance_cents=0,
        source="manual",
        created_at=WHEN,
    )
    with pytest.raises(ValueError):
        to_balance_snapshot(row)


def test_converters_treat_a_naive_time_as_utc_and_keep_an_aware_time() -> None:
    statement = to_statement(
        StatementRow(
            id=4,
            account_id=8,
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
            imported_at=NAIVE,
        )
    )
    assert statement.imported_at == WHEN
    assert statement.imported_at.utcoffset() == timedelta(0)
    transaction = to_transaction(_transaction_row(created_at=AWARE))
    assert transaction.created_at == WHEN
    assert transaction.created_at.utcoffset() == timedelta(hours=5)
    snapshot = to_balance_snapshot(
        BalanceSnapshotRow(
            id=2,
            account_id=8,
            as_of_date=date(2026, 1, 31),
            balance_cents=1,
            source="statement",
            created_at=NAIVE,
        )
    )
    assert snapshot.created_at.utcoffset() == timedelta(0)


def _uniques(table) -> dict[str, list[str]]:
    return {
        constraint.name: [column.name for column in constraint.columns]
        for constraint in table.constraints
        if constraint.name and constraint.name.startswith("uq_")
    }


def _foreign_keys(table) -> dict[str, list[str]]:
    return {
        constraint.name: [column.name for column in constraint.columns]
        for constraint in table.foreign_key_constraints
    }


def _transaction_row(**changes: object) -> TransactionRow:
    values: dict[str, object] = {
        "id": 9,
        "account_id": 8,
        "statement_id": 4,
        "posted_date": date(2026, 1, 5),
        "transaction_date": date(2026, 1, 4),
        "amount_cents": -450,
        "description": "ACME COFFEE",
        "section": "purchases",
        "card_last4": "2222",
        "cardholder": "A PERSON",
        "external_id": "7838",
        "source": "statement",
        "is_pending": False,
        "fingerprint": "f" * 64,
        "created_at": WHEN,
    }
    values.update(changes)
    return TransactionRow(**values)
