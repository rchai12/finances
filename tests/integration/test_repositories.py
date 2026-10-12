from datetime import timedelta

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import AccountRow
from finances.db.repositories import AccountExistsError, create_account, get_account_by_name
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
