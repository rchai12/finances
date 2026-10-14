import dataclasses

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finances.db.engine import session_scope
from finances.db.orm import AccountOwnerRow, PersonRow, to_person
from finances.db.repositories import (
    PersonExistsError,
    create_account,
    create_person,
    get_person_by_name,
    list_account_owners,
    list_cardholder_aliases,
    list_people,
    set_account_owner,
    set_cardholder_alias,
)
from finances.domain.models import Person


@pytest.fixture
def session(db_engine: Engine):
    """Two accounts, Test Card (id 1) and Test Checking (id 2), and no people."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        create_account(opened, "Test Checking", "Test Bank", "checking")
        yield opened


def people_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(PersonRow))


# ----- create_person (R6) -----


def test_create_person_cleans_the_name(session: Session) -> None:
    person = create_person(session, "  Alex Doe ")
    assert person == Person(id=1, name="Alex Doe")
    assert session.scalars(select(PersonRow.name)).all() == ["Alex Doe"]


def test_a_duplicate_in_another_case_is_refused(session: Session) -> None:
    create_person(session, "Alex")
    with pytest.raises(PersonExistsError) as caught:
        create_person(session, " ALEX ")
    assert str(caught.value) == "a person with this name already exists"
    assert people_count(session) == 1


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("  ", "a person's name must be 1 to 100 characters"),
        ("x" * 101, "a person's name must be 1 to 100 characters"),
        ("Joint", "joint and unassigned are reserved names"),
        ("UNASSIGNED", "joint and unassigned are reserved names"),
    ],
)
def test_unusable_names_are_refused(session: Session, name: str, message: str) -> None:
    with pytest.raises(ValueError) as caught:
        create_person(session, name)
    assert str(caught.value) == message
    assert people_count(session) == 0


# ----- get_person_by_name (R7) -----


def test_get_person_by_name_ignores_case_and_outer_spaces(session: Session) -> None:
    sam = create_person(session, "Sam")
    assert get_person_by_name(session, "  sAM ") == sam
    assert get_person_by_name(session, "Sam") == sam


def test_get_person_by_name_for_an_unknown_name(session: Session) -> None:
    create_person(session, "Sam")
    assert get_person_by_name(session, "Pat") is None


# ----- list_people (R8) -----


def test_list_people_when_empty(session: Session) -> None:
    assert list_people(session) == []


def test_list_people_sorts_by_name_without_case(session: Session) -> None:
    create_person(session, "sam")
    create_person(session, "Pat")
    create_person(session, "alex")
    assert [person.name for person in list_people(session)] == ["alex", "Pat", "sam"]


# ----- set_account_owner and list_account_owners (R9, R10) -----


def test_owners_joint_and_unowned_accounts(session: Session) -> None:
    alex = create_person(session, "Alex")
    assert list_account_owners(session) == {}
    set_account_owner(session, 1, alex.id)
    assert list_account_owners(session) == {1: alex.id}
    set_account_owner(session, 2, None)
    assert list_account_owners(session) == {1: alex.id, 2: None}


def test_a_new_owner_replaces_the_old_one(session: Session) -> None:
    alex = create_person(session, "Alex")
    sam = create_person(session, "Sam")
    set_account_owner(session, 1, alex.id)
    set_account_owner(session, 1, sam.id)
    assert list_account_owners(session) == {1: sam.id}
    set_account_owner(session, 1, None)
    assert list_account_owners(session) == {1: None}
    set_account_owner(session, 1, alex.id)
    assert list_account_owners(session) == {1: alex.id}
    count = session.scalar(select(func.count()).select_from(AccountOwnerRow))
    assert count == 1


@pytest.mark.parametrize(("account_id", "person_id"), [(99, 1), (1, 99)])
def test_an_unknown_account_or_person_is_refused(
    session: Session, account_id: int, person_id: int
) -> None:
    create_person(session, "Alex")
    with pytest.raises(IntegrityError):
        set_account_owner(session, account_id, person_id)
    session.rollback()


# ----- set_cardholder_alias and list_cardholder_aliases (R11, R12) -----


def test_the_alias_is_stored_normalized(session: Session) -> None:
    sam = create_person(session, "Sam")
    assert list_cardholder_aliases(session) == {}
    assert set_cardholder_alias(session, "  sam \t doe ", sam.id) == "SAM DOE"
    assert set_cardholder_alias(session, "s doe", sam.id) == "S DOE"
    assert list_cardholder_aliases(session) == {"SAM DOE": sam.id, "S DOE": sam.id}


def test_the_same_name_for_another_person_replaces_the_first(session: Session) -> None:
    sam = create_person(session, "Sam")
    pat = create_person(session, "Pat")
    set_cardholder_alias(session, "SAM DOE", sam.id)
    assert set_cardholder_alias(session, "Sam Doe", pat.id) == "SAM DOE"
    assert list_cardholder_aliases(session) == {"SAM DOE": pat.id}


@pytest.mark.parametrize("cardholder", ["", "  \t ", "X" * 101])
def test_unusable_cardholder_names_are_refused(session: Session, cardholder: str) -> None:
    sam = create_person(session, "Sam")
    with pytest.raises(ValueError) as caught:
        set_cardholder_alias(session, cardholder, sam.id)
    assert str(caught.value) == "a cardholder name must be 1 to 100 characters"
    assert list_cardholder_aliases(session) == {}


def test_a_100_character_cardholder_name_is_kept(session: Session) -> None:
    sam = create_person(session, "Sam")
    assert set_cardholder_alias(session, "X" * 100, sam.id) == "X" * 100


def test_an_alias_for_an_unknown_person_is_refused(session: Session) -> None:
    with pytest.raises(IntegrityError):
        set_cardholder_alias(session, "SAM DOE", 99)
    session.rollback()


# ----- to_person and Person (R2) -----


def test_to_person() -> None:
    assert to_person(PersonRow(id=7, name="Alex")) == Person(id=7, name="Alex")


def test_person_is_frozen_with_its_fields_in_order() -> None:
    person = Person(id=1, name="Alex")
    assert [field.name for field in dataclasses.fields(Person)] == ["id", "name"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        person.name = "Sam"  # type: ignore[misc]


# ----- across sessions -----


def test_a_later_session_sees_what_an_earlier_one_wrote(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        alex = create_person(session, "Alex")
        set_account_owner(session, 1, alex.id)
        set_cardholder_alias(session, "ALEX DOE", alex.id)
    with session_scope(db_engine) as session:
        assert list_people(session) == [Person(id=1, name="Alex")]
        assert get_person_by_name(session, "alex") == Person(id=1, name="Alex")
        assert list_account_owners(session) == {1: 1}
        assert list_cardholder_aliases(session) == {"ALEX DOE": 1}
