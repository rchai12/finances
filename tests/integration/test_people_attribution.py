from datetime import date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.people import (
    Attribution,
    list_transactions_with_people,
    load_attribution,
)
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_person,
    set_account_owner,
    set_cardholder_alias,
)
from finances.domain.people import JOINT


def add(session: Session, account_id: int, day: int, cents: int, cardholder: str | None) -> None:
    session.add(
        TransactionRow(
            account_id=account_id,
            posted_date=date(2026, 5, day),
            amount_cents=cents,
            description=f"ACME {day}",
            cardholder=cardholder,
            source="statement",
            fingerprint=f"{account_id}-{day}".ljust(64, "x"),
        )
    )
    session.flush()


@pytest.fixture
def session(db_engine: Engine):
    """Alex owns the card, the checking account is joint, the savings account has no owner.

    Sam's cardholder name is SAM DOE. Transactions, newest first: savings on the 9th, a card
    purchase by SAM DOE on the 8th, checking on the 7th, a card purchase by PAT DOE (no alias)
    on the 6th, and a card purchase with no cardholder on the 5th.
    """
    with session_scope(db_engine) as opened:
        card = create_account(opened, "Test Card", "Test Bank", "credit_card")
        checking = create_account(opened, "Test Checking", "Test Bank", "checking")
        savings = create_account(opened, "Test Savings", "Test Bank", "savings")
        alex = create_person(opened, "Alex")
        sam = create_person(opened, "Sam")
        set_account_owner(opened, card.id, alex.id)
        set_account_owner(opened, checking.id, None)
        set_cardholder_alias(opened, "Sam  Doe", sam.id)
        add(opened, savings.id, 9, 1000, None)
        add(opened, card.id, 8, -800, "SAM DOE")
        add(opened, checking.id, 7, -700, None)
        add(opened, card.id, 6, -600, "PAT DOE")
        add(opened, card.id, 5, -500, None)
        yield opened


def people(found: list) -> list[tuple[int, str | None]]:
    return [(row.amount_cents, who) for row, who in found]


def test_load_attribution(session: Session) -> None:
    attribution = load_attribution(session)
    assert attribution == Attribution(owners={1: "Alex", 2: JOINT}, aliases={"SAM DOE": "Sam"})
    assert (attribution.owner(1), attribution.owner(2), attribution.owner(3)) == (
        "Alex",
        JOINT,
        None,
    )


def test_every_transaction_with_its_person(session: Session) -> None:
    assert people(list_transactions_with_people(session)) == [
        (1000, None),
        (-800, "Sam"),
        (-700, JOINT),
        (-600, "Alex"),
        (-500, "Alex"),
    ]


@pytest.mark.parametrize(
    ("person", "expected"),
    [
        ("Alex", [(-600, "Alex"), (-500, "Alex")]),
        ("  sAm ", [(-800, "Sam")]),
        ("joint", [(-700, JOINT)]),
        ("JOINT", [(-700, JOINT)]),
        ("unassigned", [(1000, None)]),
        (" Unassigned ", [(1000, None)]),
    ],
)
def test_one_persons_transactions(session: Session, person: str, expected: list) -> None:
    assert people(list_transactions_with_people(session, person=person)) == expected


def test_the_limit_applies_after_the_person_filter(session: Session) -> None:
    assert people(list_transactions_with_people(session, limit=1, person="alex")) == [
        (-600, "Alex")
    ]
    assert people(list_transactions_with_people(session, limit=2)) == [(1000, None), (-800, "Sam")]


def test_the_other_filters_still_apply(session: Session) -> None:
    found = list_transactions_with_people(
        session, account_id=1, start=date(2026, 5, 6), end=date(2026, 5, 8)
    )
    assert people(found) == [(-800, "Sam"), (-600, "Alex")]
    assert people(list_transactions_with_people(session, account_id=1, person="sam")) == [
        (-800, "Sam")
    ]


def test_an_unknown_person(session: Session) -> None:
    with pytest.raises(ValueError) as caught:
        list_transactions_with_people(session, person="Nobody")
    assert str(caught.value) == "person not found"


def test_a_limit_below_one(session: Session) -> None:
    with pytest.raises(ValueError) as caught:
        list_transactions_with_people(session, limit=0, person="alex")
    assert str(caught.value) == "limit must be at least 1"


def test_changing_an_owner_or_an_alias_changes_the_attribution(session: Session) -> None:
    pat = create_person(session, "Pat")
    set_cardholder_alias(session, "pat doe", pat.id)
    set_account_owner(session, 1, None)
    assert people(list_transactions_with_people(session, account_id=1)) == [
        (-800, "Sam"),
        (-600, "Pat"),
        (-500, JOINT),
    ]
