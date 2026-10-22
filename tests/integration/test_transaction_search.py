from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.search import TransactionQuery, search_transactions
from finances.analysis.spending import flows_for, load_flows
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_person,
    create_transfer_pair,
    list_transactions_by_day,
    set_account_owner,
    set_category_by_hand,
)
from finances.domain.models import CONFIRMED
from finances.domain.spending import (
    INCOME,
    NO_CARD,
    PENDING,
    SPENDING,
    TRANSFER,
    UNASSIGNED,
    UNCATEGORIZED,
    Flow,
)

CHECKING, CARD, SHARED = 1, 2, 3
KIND_MESSAGE = "kind must be one of: spending, income, transfer, unsorted_in, pending, refund"


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    """Test Checking (1) has no owner, Test Card (2) is Pat Example's, Shared Card (3) Joint."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Checking", "Test Bank", "checking")
        create_account(opened, "Test Card", "Example Card Co", "credit_card")
        create_account(opened, "Shared Card", "Example Card Co", "credit_card")
        pat = create_person(opened, "Pat Example")
        set_account_owner(opened, CARD, pat.id)
        set_account_owner(opened, SHARED, None)
        yield opened


def add(
    session: Session,
    account: int,
    posted: date,
    cents: int,
    *,
    bought: date | None = None,
    pending: bool = False,
    description: str = "ACME COFFEE #12",
) -> int:
    row = TransactionRow(
        account_id=account,
        posted_date=posted,
        transaction_date=bought,
        amount_cents=cents,
        description=description,
        is_pending=pending,
        source="statement",
        fingerprint=f"s{account}-{posted}-{bought}-{cents}-{pending}".ljust(64, "0"),
    )
    session.add(row)
    session.flush()
    return row.id


def by_day(session: Session, start: date | None, end: date | None) -> list[int]:
    return [item.id for item in list_transactions_by_day(session, start, end)]


def found_ids(session: Session, **fields: object) -> list[int]:
    return [
        item.transaction.id for item in search_transactions(session, TransactionQuery(**fields))
    ]


def test_by_day_with_no_bounds_lists_everything_latest_posted_first(session: Session) -> None:
    early = add(session, CHECKING, date(2026, 5, 1), -100)
    late = add(session, CHECKING, date(2026, 5, 9), -200)
    same_day = add(session, CARD, date(2026, 5, 9), -300)
    assert by_day(session, None, None) == [same_day, late, early]


def test_by_day_with_one_bound_uses_the_day_bought(session: Session) -> None:
    bought_in_april = add(session, CHECKING, date(2026, 5, 2), -100, bought=date(2026, 4, 30))
    posted_in_may = add(session, CHECKING, date(2026, 5, 3), -200)
    assert by_day(session, date(2026, 5, 1), None) == [posted_in_may]
    assert by_day(session, None, date(2026, 4, 30)) == [bought_in_april]


def test_by_day_includes_pending(session: Session) -> None:
    posted = add(session, CHECKING, date(2026, 5, 10), -100)
    pending = add(session, CHECKING, date(2026, 5, 11), -200, pending=True)
    assert by_day(session, date(2026, 5, 1), date(2026, 5, 31)) == [pending, posted]


def test_flows_for_marks_a_pending_transaction_pending(session: Session) -> None:
    add(session, CHECKING, date(2026, 5, 10), -100)
    add(session, CHECKING, date(2026, 5, 11), -200, pending=True)
    transactions = list_transactions_by_day(session, None, None)
    assert [flow.kind for flow in flows_for(session, transactions)] == [PENDING, SPENDING]


def test_load_flows_over_a_month_is_unchanged(session: Session) -> None:
    out = add(session, CHECKING, date(2026, 5, 20), -5000, description="PAYMENT TO TEST CARD")
    into = add(session, CARD, date(2026, 5, 21), 5000, description="PAYMENT THANK YOU")
    create_transfer_pair(session, out, into, CONFIRMED)
    pay = add(session, CHECKING, date(2026, 5, 15), 300000, description="EXAMPLE CORP PAYROLL")
    set_category_by_hand(session, pay, "Paycheck")
    add(session, CARD, date(2026, 5, 2), -450, bought=date(2026, 5, 1))
    add(session, CARD, date(2026, 5, 12), -999, pending=True, description="QUUX STREAMING")

    def flow(cents: int, day: date, kind: str, merchant: str, account: int, **labels) -> Flow:
        person, name, bank = {
            CHECKING: (UNASSIGNED, "Test Checking", "Test Bank"),
            CARD: ("Pat Example", "Test Card", "Example Card Co"),
        }[account]
        return Flow(
            amount_cents=cents,
            day=day,
            kind=kind,
            category=labels.get("category", UNCATEGORIZED),
            group=labels.get("group", UNCATEGORIZED),
            merchant=merchant,
            person=person,
            account=name,
            bank=bank,
            card=NO_CARD,
        )

    assert load_flows(session, date(2026, 5, 1), date(2026, 5, 31)) == [
        flow(-5000, date(2026, 5, 20), TRANSFER, "PAYMENT TO TEST CARD", CHECKING),
        flow(5000, date(2026, 5, 21), TRANSFER, "PAYMENT THANK YOU", CARD),
        flow(
            300000,
            date(2026, 5, 15),
            INCOME,
            "EXAMPLE CORP PAYROLL",
            CHECKING,
            category="Paycheck",
            group="Income",
        ),
        flow(-450, date(2026, 5, 1), SPENDING, "ACME COFFEE", CARD),
    ]


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"kind": "spend"}, KIND_MESSAGE),
        ({"kind": "SPENDING "}, KIND_MESSAGE),
        ({"account": "Nope"}, "account not found"),
        ({"person": "Nobody"}, "person not found"),
        ({"kind": "spend", "account": "Nope", "person": "Nobody"}, KIND_MESSAGE),
        ({"account": "Nope", "person": "Nobody"}, "account not found"),
    ],
)
def test_refusals_come_in_order(session: Session, fields: dict, message: str) -> None:
    with pytest.raises(ValueError, match=f"^{message}$"):
        search_transactions(session, TransactionQuery(**fields))


def test_fields_with_surrounding_spaces_still_match(session: Session) -> None:
    coffee = add(session, CARD, date(2026, 5, 2), -450)
    add(session, CHECKING, date(2026, 5, 3), -2599, description="FOOBAR GROCERY")
    assert found_ids(session, text="  coffee ", merchant=" acme coffee ") == [coffee]
    assert found_ids(session, card="  no card ", bank=" example card co ") == [coffee]


def test_joint_unassigned_and_a_name_in_another_case(session: Session) -> None:
    mine = add(session, CARD, date(2026, 5, 2), -450)
    shared = add(session, SHARED, date(2026, 5, 3), -600)
    nobody = add(session, CHECKING, date(2026, 5, 4), -700)
    assert found_ids(session, person="Joint") == [shared]
    assert found_ids(session, person=" UNASSIGNED ") == [nobody]
    assert found_ids(session, person="pat EXAMPLE") == [mine]


def test_an_account_in_another_case(session: Session) -> None:
    add(session, CARD, date(2026, 5, 2), -450)
    checking = add(session, CHECKING, date(2026, 5, 3), -700)
    assert found_ids(session, account="test CHECKING") == [checking]


def test_every_label_compares_whole(session: Session) -> None:
    add(session, CARD, date(2026, 5, 2), -450)
    assert found_ids(session, merchant="acme") == []
    assert found_ids(session, category="uncat") == []


def test_the_limit_cuts_after_the_filters(session: Session) -> None:
    older = add(session, CHECKING, date(2026, 5, 1), -100)
    add(session, CARD, date(2026, 5, 2), -200)
    newer = add(session, CHECKING, date(2026, 5, 3), -300)
    add(session, CARD, date(2026, 5, 4), -400)
    assert found_ids(session, account="Test Checking", limit=1) == [newer]
    assert found_ids(session, account="Test Checking", limit=5) == [newer, older]


def test_pending_is_a_kind_of_its_own(session: Session) -> None:
    add(session, CHECKING, date(2026, 5, 1), -100)
    pending = add(session, CHECKING, date(2026, 5, 2), -200, pending=True)
    assert found_ids(session, kind="pending") == [pending]
    assert pending not in found_ids(session, kind="spending")
