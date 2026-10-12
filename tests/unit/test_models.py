import dataclasses
from datetime import UTC, datetime
from enum import StrEnum

import pytest

from finances.domain.models import Account, AccountType

CREATED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def make_account(**changes: object) -> Account:
    values = {
        "id": 1,
        "name": "Test Checking",
        "institution": "Test Bank",
        "type": AccountType.CHECKING,
        "currency": "USD",
        "last4": "1234",
        "is_active": True,
        "created_at": CREATED,
    }
    values.update(changes)
    return Account(**values)


def test_account_type_is_a_str_enum() -> None:
    assert issubclass(AccountType, StrEnum)


def test_account_type_members_in_order() -> None:
    names = [member.name for member in AccountType]
    assert names == ["CHECKING", "SAVINGS", "CREDIT_CARD", "OTHER"]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("CHECKING", "checking"),
        ("SAVINGS", "savings"),
        ("CREDIT_CARD", "credit_card"),
        ("OTHER", "other"),
    ],
)
def test_account_type_values(name: str, value: str) -> None:
    member = AccountType[name]
    assert member.value == value
    assert str(member) == value
    assert AccountType(value) is member


def test_account_type_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        AccountType("brokerage")


def test_account_fields_in_order() -> None:
    names = [field.name for field in dataclasses.fields(Account)]
    assert names == [
        "id",
        "name",
        "institution",
        "type",
        "currency",
        "last4",
        "is_active",
        "created_at",
    ]


def test_account_has_no_default_values() -> None:
    fields = dataclasses.fields(Account)
    assert len(fields) == 8
    for field in fields:
        assert field.default is dataclasses.MISSING
        assert field.default_factory is dataclasses.MISSING


def test_account_keeps_its_values() -> None:
    account = make_account()
    assert account.id == 1
    assert account.name == "Test Checking"
    assert account.institution == "Test Bank"
    assert account.type is AccountType.CHECKING
    assert account.currency == "USD"
    assert account.last4 == "1234"
    assert account.is_active is True
    assert account.created_at == CREATED


def test_account_last4_may_be_none() -> None:
    assert make_account(last4=None).last4 is None


def test_account_is_frozen() -> None:
    account = make_account()
    with pytest.raises(dataclasses.FrozenInstanceError):
        account.name = "Other"


def test_accounts_with_equal_values_are_equal() -> None:
    assert make_account() == make_account()
    assert make_account() != make_account(id=2)
    assert hash(make_account()) == hash(make_account())
