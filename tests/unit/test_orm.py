from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Boolean, DateTime, Enum, Integer, String, UniqueConstraint

from finances.db.orm import AccountRow, Base, to_account
from finances.domain.models import Account, AccountType

TABLE = AccountRow.__table__
CREATED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
COLUMN_NAMES = [
    "id",
    "name",
    "institution",
    "type",
    "currency",
    "last4",
    "is_active",
    "created_at",
]


def make_row(**changes: object) -> AccountRow:
    values = {
        "id": 3,
        "name": "Test Card",
        "institution": "Test Bank",
        "type": "credit_card",
        "currency": "USD",
        "last4": "4321",
        "is_active": True,
        "created_at": CREATED,
    }
    values.update(changes)
    return AccountRow(**values)


def test_table_is_named_accounts() -> None:
    assert TABLE.name == "accounts"
    assert Base.metadata.tables["accounts"] is TABLE


def test_columns_in_order() -> None:
    assert [column.name for column in TABLE.columns] == COLUMN_NAMES


@pytest.mark.parametrize(
    ("name", "type_class", "length"),
    [
        ("id", Integer, None),
        ("name", String, 100),
        ("institution", String, 100),
        ("type", String, 20),
        ("currency", String, 3),
        ("last4", String, 4),
        ("is_active", Boolean, None),
        ("created_at", DateTime, None),
    ],
)
def test_column_type(name: str, type_class: type, length: int | None) -> None:
    column_type = TABLE.columns[name].type
    assert isinstance(column_type, type_class)
    assert not isinstance(column_type, Enum)
    if length is not None:
        assert column_type.length == length


@pytest.mark.parametrize("name", COLUMN_NAMES)
def test_only_last4_allows_null(name: str) -> None:
    assert TABLE.columns[name].nullable is (name == "last4")


def test_id_is_the_only_primary_key() -> None:
    assert [column.name for column in TABLE.primary_key.columns] == ["id"]


def test_name_is_the_only_unique_column() -> None:
    unique = [
        [column.name for column in constraint.columns]
        for constraint in TABLE.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    assert unique == [["name"]]


def test_currency_defaults_to_usd() -> None:
    assert TABLE.columns["currency"].default.arg == "USD"


def test_is_active_defaults_to_true() -> None:
    assert TABLE.columns["is_active"].default.arg is True


def test_created_at_keeps_the_time_zone() -> None:
    assert TABLE.columns["created_at"].type.timezone is True


def test_created_at_defaults_to_now_in_utc() -> None:
    value = TABLE.columns["created_at"].default.arg(None)
    assert isinstance(value, datetime)
    assert value.utcoffset() == timedelta(0)
    assert abs(datetime.now(UTC) - value) < timedelta(minutes=1)


@pytest.mark.parametrize("name", ["id", "name", "institution", "type", "last4"])
def test_columns_without_a_default(name: str) -> None:
    assert TABLE.columns[name].default is None


@pytest.mark.parametrize("name", COLUMN_NAMES)
def test_no_server_defaults(name: str) -> None:
    assert TABLE.columns[name].server_default is None


def test_to_account_copies_every_value() -> None:
    assert to_account(make_row()) == Account(
        id=3,
        name="Test Card",
        institution="Test Bank",
        type=AccountType.CREDIT_CARD,
        currency="USD",
        last4="4321",
        is_active=True,
        created_at=CREATED,
    )


def test_to_account_returns_an_account() -> None:
    assert type(to_account(make_row())) is Account


@pytest.mark.parametrize("member", list(AccountType))
def test_to_account_converts_type_to_the_enum(member: AccountType) -> None:
    assert to_account(make_row(type=member.value)).type is member


def test_to_account_rejects_an_unknown_type() -> None:
    with pytest.raises(ValueError):
        to_account(make_row(type="brokerage"))


def test_to_account_keeps_a_missing_last4() -> None:
    assert to_account(make_row(last4=None)).last4 is None


def test_to_account_keeps_inactive() -> None:
    assert to_account(make_row(is_active=False)).is_active is False


def test_to_account_treats_a_naive_time_as_utc() -> None:
    naive = datetime(2026, 1, 2, 3, 4, 5)
    account = to_account(make_row(created_at=naive))
    assert account.created_at == CREATED
    assert account.created_at.utcoffset() == timedelta(0)


def test_to_account_keeps_an_aware_time_unchanged() -> None:
    plus_five = timezone(timedelta(hours=5))
    aware = datetime(2026, 1, 2, 8, 4, 5, tzinfo=plus_five)
    account = to_account(make_row(created_at=aware))
    assert account.created_at == CREATED
    assert account.created_at.utcoffset() == timedelta(hours=5)
