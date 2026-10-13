from datetime import timedelta

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import AccountRow
from finances.db.repositories import (
    AccountExistsError,
    create_account,
    find_accounts_by_last4,
    get_account_by_name,
    list_accounts,
)
from finances.domain.models import Account, AccountType

EXISTS = "an account with this name already exists"


def add_row(engine: Engine, name: str, **values: object) -> None:
    row = {"name": name, "institution": "Test Bank", "type": "checking"}
    row.update(values)
    with session_scope(engine) as session:
        session.add(AccountRow(**row))


def count_rows(engine: Engine) -> int:
    with session_scope(engine) as session:
        return session.scalar(select(func.count()).select_from(AccountRow))


def stored_names(engine: Engine) -> list[str]:
    with session_scope(engine) as session:
        return list(session.scalars(select(AccountRow.name).order_by(AccountRow.id)))


def test_get_account_by_name_returns_none_when_there_are_no_accounts(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        assert get_account_by_name(session, "Test Checking") is None


def test_get_account_by_name_finds_the_account(db_engine: Engine) -> None:
    add_row(db_engine, "Test Checking", type="savings", last4="1234")
    with session_scope(db_engine) as session:
        account = get_account_by_name(session, "Test Checking")
    assert type(account) is Account
    assert account.id == 1
    assert account.name == "Test Checking"
    assert account.institution == "Test Bank"
    assert account.type is AccountType.SAVINGS
    assert account.last4 == "1234"


@pytest.mark.parametrize(
    "asked",
    ["test checking", "TEST CHECKING", "tEsT cHeCkInG", "  Test Checking", "Test Checking\n"],
)
def test_get_account_by_name_ignores_case_and_outer_spaces(db_engine: Engine, asked: str) -> None:
    add_row(db_engine, "Test Checking")
    with session_scope(db_engine) as session:
        account = get_account_by_name(session, asked)
    assert account is not None
    assert account.name == "Test Checking"


@pytest.mark.parametrize("asked", ["Test", "Checking", "Test Checking 2", "TestChecking", ""])
def test_get_account_by_name_needs_the_whole_name(db_engine: Engine, asked: str) -> None:
    add_row(db_engine, "Test Checking")
    with session_scope(db_engine) as session:
        assert get_account_by_name(session, asked) is None


def test_get_account_by_name_picks_the_right_one(db_engine: Engine) -> None:
    add_row(db_engine, "Test Checking")
    add_row(db_engine, "Test Savings", type="savings")
    add_row(db_engine, "Test Card", type="credit_card")
    with session_scope(db_engine) as session:
        account = get_account_by_name(session, "test savings")
    assert account.id == 2
    assert account.type is AccountType.SAVINGS


def test_create_account_returns_the_new_account(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        account = create_account(session, "Test Checking", "Test Bank", AccountType.CHECKING)
    assert type(account) is Account
    assert account.id == 1
    assert account.name == "Test Checking"
    assert account.institution == "Test Bank"
    assert account.type is AccountType.CHECKING
    assert account.currency == "USD"
    assert account.last4 is None
    assert account.is_active is True
    assert account.created_at.utcoffset() == timedelta(0)


def test_create_account_stores_the_row(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Card", "Test Bank", AccountType.CREDIT_CARD, "CAD", "0042")
    with session_scope(db_engine) as session:
        row = session.scalars(select(AccountRow)).one()
        found = (row.name, row.institution, row.type, row.currency, row.last4, row.is_active)
    assert found == ("Test Card", "Test Bank", "credit_card", "CAD", "0042", True)


def test_create_account_gives_each_account_its_own_id(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        first = create_account(session, "Test Checking", "Test Bank", AccountType.CHECKING)
        second = create_account(session, "Test Savings", "Test Bank", AccountType.SAVINGS)
    assert (first.id, second.id) == (1, 2)


def test_create_account_does_not_commit(db_engine: Engine) -> None:
    session = Session(db_engine)
    account = create_account(session, "Test Checking", "Test Bank", AccountType.CHECKING)
    assert account.id == 1
    session.rollback()
    session.close()
    assert count_rows(db_engine) == 0


def test_create_account_removes_outer_spaces(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        account = create_account(session, "  Test Checking ", " Test Bank\n", AccountType.CHECKING)
    assert (account.name, account.institution) == ("Test Checking", "Test Bank")
    assert stored_names(db_engine) == ["Test Checking"]


@pytest.mark.parametrize("name", ["", "   ", "\n\t"])
def test_create_account_rejects_an_empty_name(db_engine: Engine, name: str) -> None:
    with session_scope(db_engine) as session:
        with pytest.raises(ValueError) as excinfo:
            create_account(session, name, "Test Bank", AccountType.CHECKING)
    assert str(excinfo.value) == "account name must not be empty"
    assert count_rows(db_engine) == 0


@pytest.mark.parametrize("institution", ["", "   "])
def test_create_account_rejects_an_empty_institution(db_engine: Engine, institution: str) -> None:
    with session_scope(db_engine) as session:
        with pytest.raises(ValueError) as excinfo:
            create_account(session, "Test Checking", institution, AccountType.CHECKING)
    assert str(excinfo.value) == "institution must not be empty"
    assert count_rows(db_engine) == 0


@pytest.mark.parametrize(
    "name", ["Test Checking", "test checking", "TEST CHECKING", " Test Checking "]
)
def test_create_account_rejects_a_duplicate_name(db_engine: Engine, name: str) -> None:
    add_row(db_engine, "Test Checking")
    with session_scope(db_engine) as session:
        with pytest.raises(AccountExistsError) as excinfo:
            create_account(session, name, "Other Bank", AccountType.SAVINGS)
    assert str(excinfo.value) == EXISTS
    assert stored_names(db_engine) == ["Test Checking"]


def test_create_account_rejects_a_duplicate_in_the_same_session(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Checking", "Test Bank", AccountType.CHECKING)
        with pytest.raises(AccountExistsError):
            create_account(session, "test checking", "Test Bank", AccountType.CHECKING)
    assert stored_names(db_engine) == ["Test Checking"]


def test_the_session_still_works_after_a_duplicate(db_engine: Engine) -> None:
    add_row(db_engine, "Test Checking")
    with session_scope(db_engine) as session:
        with pytest.raises(AccountExistsError):
            create_account(session, "Test Checking", "Test Bank", AccountType.CHECKING)
        create_account(session, "Test Savings", "Test Bank", AccountType.SAVINGS)
    assert stored_names(db_engine) == ["Test Checking", "Test Savings"]


def test_account_exists_error_is_not_a_value_error() -> None:
    assert not issubclass(AccountExistsError, ValueError)


@pytest.mark.parametrize("member", list(AccountType))
def test_create_account_accepts_the_type_as_text(db_engine: Engine, member: AccountType) -> None:
    with session_scope(db_engine) as session:
        account = create_account(session, "Test Account", "Test Bank", member.value)
    assert account.type is member
    with session_scope(db_engine) as session:
        assert session.scalars(select(AccountRow.type)).one() == member.value


def test_create_account_rejects_an_unknown_type(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        with pytest.raises(ValueError):
            create_account(session, "Test Account", "Test Bank", "brokerage")
    assert count_rows(db_engine) == 0


@pytest.mark.parametrize("last4", ["123", "12345", "12a4", " 1234"])
def test_create_account_rejects_a_bad_last4(db_engine: Engine, last4: str) -> None:
    with session_scope(db_engine) as session:
        with pytest.raises(ValueError) as excinfo:
            create_account(session, "Test Account", "Test Bank", AccountType.OTHER, last4=last4)
    assert str(excinfo.value) == "last4 must be exactly 4 digits"
    assert count_rows(db_engine) == 0


def names(accounts: list[Account]) -> list[str]:
    return [account.name for account in accounts]


def test_find_accounts_by_last4_returns_the_matching_account(db_engine: Engine) -> None:
    add_row(db_engine, "Test Checking", last4="1234")
    add_row(db_engine, "Test Savings", last4="5678")
    with session_scope(db_engine) as session:
        accounts = find_accounts_by_last4(session, "1234")
    assert type(accounts) is list
    assert [type(account) for account in accounts] == [Account]
    assert names(accounts) == ["Test Checking"]


def test_find_accounts_by_last4_returns_every_match_in_id_order(db_engine: Engine) -> None:
    add_row(db_engine, "Zebra Card", last4="1234", type="credit_card")
    add_row(db_engine, "Other Card", last4="9999", type="credit_card")
    add_row(db_engine, "Apple Card", last4="1234", type="credit_card")
    with session_scope(db_engine) as session:
        accounts = find_accounts_by_last4(session, "1234")
    assert [account.id for account in accounts] == [1, 3]
    assert names(accounts) == ["Zebra Card", "Apple Card"]


def test_find_accounts_by_last4_includes_inactive_accounts(db_engine: Engine) -> None:
    add_row(db_engine, "Closed Card", last4="1234", is_active=False)
    with session_scope(db_engine) as session:
        accounts = find_accounts_by_last4(session, "1234")
    assert names(accounts) == ["Closed Card"]
    assert accounts[0].is_active is False


def test_find_accounts_by_last4_no_match_gives_an_empty_list(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        assert find_accounts_by_last4(session, "1234") == []
    add_row(db_engine, "Test Checking", last4="1234")
    with session_scope(db_engine) as session:
        assert find_accounts_by_last4(session, "0000") == []


def test_find_accounts_by_last4_ignores_accounts_without_last4(db_engine: Engine) -> None:
    add_row(db_engine, "No Digits")
    with session_scope(db_engine) as session:
        assert find_accounts_by_last4(session, "1234") == []


@pytest.mark.parametrize("last4", ["", "123", "12345", "12a4", " 1234"])
def test_find_accounts_by_last4_rejects_bad_input(db_engine: Engine, last4: str) -> None:
    add_row(db_engine, "Test Checking", last4="1234")
    with session_scope(db_engine) as session:
        with pytest.raises(ValueError) as excinfo:
            find_accounts_by_last4(session, last4)
    assert str(excinfo.value) == "last4 must be exactly 4 digits"


def test_list_accounts_is_empty_when_there_are_no_accounts(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        accounts = list_accounts(session)
    assert type(accounts) is list
    assert accounts == []


def test_list_accounts_sorted_by_name_ignoring_case(db_engine: Engine) -> None:
    for name in ["cherry", "Banana", "apple", "Date"]:
        add_row(db_engine, name)
    with session_scope(db_engine) as session:
        accounts = list_accounts(session)
    assert type(accounts) is list
    assert [type(account) for account in accounts] == [Account] * 4
    assert names(accounts) == ["apple", "Banana", "cherry", "Date"]


def test_list_accounts_leaves_out_inactive_by_default(db_engine: Engine) -> None:
    add_row(db_engine, "Open One")
    add_row(db_engine, "Closed", is_active=False)
    add_row(db_engine, "Open Two")
    with session_scope(db_engine) as session:
        assert names(list_accounts(session)) == ["Open One", "Open Two"]
        assert names(list_accounts(session, False)) == ["Open One", "Open Two"]
        assert names(list_accounts(session, include_inactive=False)) == ["Open One", "Open Two"]


def test_list_accounts_include_inactive_returns_all(db_engine: Engine) -> None:
    add_row(db_engine, "Open One")
    add_row(db_engine, "Closed", is_active=False)
    add_row(db_engine, "Open Two")
    with session_scope(db_engine) as session:
        accounts = list_accounts(session, include_inactive=True)
    assert names(accounts) == ["Closed", "Open One", "Open Two"]
    assert [account.is_active for account in accounts] == [False, True, True]


def test_list_accounts_is_empty_when_every_account_is_inactive(db_engine: Engine) -> None:
    add_row(db_engine, "Closed", is_active=False)
    with session_scope(db_engine) as session:
        assert list_accounts(session) == []
