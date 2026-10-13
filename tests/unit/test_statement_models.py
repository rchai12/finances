import dataclasses
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

import pytest

from finances.domain import models
from finances.domain.models import (
    BalanceSnapshot,
    DataSource,
    NewTransaction,
    Statement,
    Transaction,
)

WHEN = datetime(2026, 1, 31, 12, 0, 0)
NEW_FIELDS = [
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
]
NEW_TYPES = [
    int,
    int | None,
    date,
    date | None,
    int,
    str,
    str | None,
    str | None,
    str | None,
    str | None,
    DataSource,
    bool,
    str,
]


def test_data_source_members_and_order() -> None:
    assert issubclass(DataSource, StrEnum)
    assert [(member.name, member.value) for member in DataSource] == [
        ("STATEMENT", "statement"),
        ("AGGREGATOR", "aggregator"),
    ]


def test_statement_fields_order_and_types() -> None:
    fields = dataclasses.fields(Statement)
    assert [field.name for field in fields] == [
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
    assert [field.type for field in fields] == [
        int,
        int,
        str,
        str,
        str,
        date,
        date,
        int,
        int,
        int,
        int,
        int,
        datetime,
    ]


def test_new_transaction_fields_order_and_types() -> None:
    fields = dataclasses.fields(NewTransaction)
    assert [field.name for field in fields] == NEW_FIELDS
    assert [field.type for field in fields] == NEW_TYPES


def test_transaction_fields_order_and_types() -> None:
    fields = dataclasses.fields(Transaction)
    assert [field.name for field in fields] == ["id", *NEW_FIELDS, "created_at"]
    assert [field.type for field in fields] == [int, *NEW_TYPES, datetime]


def test_balance_snapshot_fields_order_and_types() -> None:
    fields = dataclasses.fields(BalanceSnapshot)
    assert [field.name for field in fields] == [
        "id",
        "account_id",
        "as_of_date",
        "balance_cents",
        "source",
        "created_at",
    ]
    assert [field.type for field in fields] == [int, int, date, int, DataSource, datetime]


@pytest.mark.parametrize(
    "cls",
    [Statement, NewTransaction, Transaction, BalanceSnapshot],
)
def test_stored_types_are_frozen_and_have_no_defaults(cls: type) -> None:
    assert cls.__dataclass_params__.frozen is True
    for field in dataclasses.fields(cls):
        assert field.default is dataclasses.MISSING
        assert field.default_factory is dataclasses.MISSING


def test_a_frozen_statement_rejects_assignment() -> None:
    statement = Statement(
        1,
        2,
        "jan.pdf",
        "a" * 64,
        "fake_bank",
        date(2026, 1, 1),
        date(2026, 1, 31),
        -10000,
        -8499,
        4,
        4,
        0,
        WHEN,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        statement.id = 9


def test_domain_models_import_only_the_standard_library() -> None:
    imports = [
        line
        for line in Path(models.__file__).read_text(encoding="utf-8").splitlines()
        if line.startswith(("import ", "from "))
    ]
    assert imports
    assert not any("finances" in line for line in imports)
