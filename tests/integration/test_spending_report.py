from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from finances.analysis.spending import load_flows, spending_report
from finances.cli.main import app
from finances.config import Settings
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_category,
    create_person,
    create_transfer_pair,
    list_transactions_between,
    set_account_owner,
    set_cardholder_alias,
    set_category_by_hand,
)
from finances.domain.models import CONFIRMED
from finances.domain.spending import (
    INCOME,
    NO_CARD,
    SPENDING,
    TRANSFER,
    UNASSIGNED,
    UNCATEGORIZED,
    UNSORTED_IN,
    month_bounds,
)

MAY_FIRST, MAY_LAST = date(2026, 5, 1), date(2026, 5, 31)
CHECKING, CARD = 1, 2


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    """Test Checking (1) with no owner, and Test Card (2) owned by Pat Example."""
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Checking", "Test Bank", "checking")
        create_account(opened, "Test Card", "Example Card Co", "credit_card")
        pat = create_person(opened, "Pat Example")
        set_account_owner(opened, CARD, pat.id)
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
    last4: str | None = None,
    cardholder: str | None = None,
) -> int:
    row = TransactionRow(
        account_id=account,
        posted_date=posted,
        transaction_date=bought,
        amount_cents=cents,
        description=description,
        card_last4=last4,
        cardholder=cardholder,
        is_pending=pending,
        source="statement",
        fingerprint=f"p{account}-{posted}-{bought}-{cents}-{pending}".ljust(64, "0"),
    )
    session.add(row)
    session.flush()
    return row.id


def between_ids(session: Session, start: date = MAY_FIRST, end: date = MAY_LAST) -> list[int]:
    return [item.id for item in list_transactions_between(session, start, end)]


def only_flow(session: Session):
    (flow,) = load_flows(session, MAY_FIRST, MAY_LAST)
    return flow


def test_the_day_bought_decides_the_range(session: Session) -> None:
    inside = add(session, CHECKING, date(2026, 6, 1), -100, bought=date(2026, 5, 31))
    add(session, CHECKING, date(2026, 5, 1), -200, bought=date(2026, 4, 30))
    assert between_ids(session) == [inside]


def test_the_posted_day_counts_when_there_is_no_day_bought(session: Session) -> None:
    inside = add(session, CHECKING, date(2026, 5, 15), -100)
    add(session, CHECKING, date(2026, 6, 15), -200)
    assert between_ids(session) == [inside]


def test_pending_transactions_are_left_out(session: Session) -> None:
    posted = add(session, CHECKING, date(2026, 5, 10), -100)
    add(session, CHECKING, date(2026, 5, 11), -200, pending=True)
    assert between_ids(session) == [posted]


def test_both_ends_of_the_range_are_included(session: Session) -> None:
    first = add(session, CHECKING, MAY_FIRST, -100)
    last = add(session, CHECKING, MAY_LAST, -200)
    add(session, CHECKING, date(2026, 4, 30), -300)
    add(session, CHECKING, date(2026, 6, 1), -400)
    assert between_ids(session) == [first, last]


def test_transactions_come_in_id_order(session: Session) -> None:
    later = add(session, CHECKING, date(2026, 5, 20), -100)
    earlier = add(session, CHECKING, date(2026, 5, 2), -200)
    assert between_ids(session) == [later, earlier]


def test_a_paired_transaction_is_a_transfer(session: Session) -> None:
    out = add(session, CHECKING, date(2026, 5, 20), -5000, description="PAYMENT TO TEST CARD")
    into = add(session, CARD, date(2026, 5, 21), 5000, description="PAYMENT THANK YOU")
    create_transfer_pair(session, out, into, CONFIRMED)
    flows = load_flows(session, MAY_FIRST, MAY_LAST)
    assert [(flow.kind, flow.category) for flow in flows] == [
        (TRANSFER, UNCATEGORIZED),
        (TRANSFER, UNCATEGORIZED),
    ]


def test_a_transfer_category_makes_a_transfer(session: Session) -> None:
    item = add(session, CHECKING, date(2026, 5, 20), -5000)
    set_category_by_hand(session, item, "Credit Card Payment")
    flow = only_flow(session)
    assert (flow.kind, flow.category, flow.group) == (TRANSFER, "Credit Card Payment", "Transfers")


def test_an_income_category_makes_income(session: Session) -> None:
    item = add(session, CHECKING, date(2026, 5, 15), 300000, description="PAYCHECK EXAMPLE CORP")
    set_category_by_hand(session, item, "Paycheck")
    flow = only_flow(session)
    assert (flow.kind, flow.category, flow.group, flow.amount_cents) == (
        INCOME,
        "Paycheck",
        "Income",
        300000,
    )


def test_money_in_with_no_category_is_unsorted(session: Session) -> None:
    add(session, CHECKING, date(2026, 5, 16), 2500)
    flow = only_flow(session)
    assert (flow.kind, flow.category, flow.group) == (UNSORTED_IN, UNCATEGORIZED, UNCATEGORIZED)


def test_a_category_added_by_hand_reports_its_group(session: Session) -> None:
    create_category(session, "Probe Snacks", "Food")
    item = add(session, CARD, date(2026, 5, 3), -450, last4="1111")
    set_category_by_hand(session, item, "Probe Snacks")
    flow = only_flow(session)
    assert (flow.kind, flow.category, flow.group) == (SPENDING, "Probe Snacks", "Food")


def test_a_flow_names_merchant_account_bank_card_and_day(session: Session) -> None:
    add(
        session,
        CARD,
        date(2026, 6, 1),
        -1250,
        bought=date(2026, 5, 31),
        description="SQ *ACME COFFEE",
        last4="1111",
    )
    flow = only_flow(session)
    assert (flow.merchant, flow.account, flow.bank, flow.card, flow.day, flow.person) == (
        "ACME COFFEE",
        "Test Card",
        "Example Card Co",
        "1111",
        date(2026, 5, 31),
        "Pat Example",
    )


def test_a_cardholder_mapped_to_a_person_names_that_person(session: Session) -> None:
    sam = create_person(session, "Sam Example")
    set_cardholder_alias(session, "SAM EXAMPLE", sam.id)
    add(session, CARD, date(2026, 5, 4), -900, last4="2222", cardholder="SAM EXAMPLE")
    assert only_flow(session).person == "Sam Example"


def test_an_account_with_no_owner_is_unassigned(session: Session) -> None:
    add(session, CHECKING, date(2026, 5, 25), -12000, description="ACME UTILITY")
    flow = only_flow(session)
    assert (flow.person, flow.card) == (UNASSIGNED, NO_CARD)


def test_a_joint_account_is_joint(session: Session) -> None:
    set_account_owner(session, CHECKING, None)
    add(session, CHECKING, date(2026, 5, 25), -12000)
    assert only_flow(session).person == "Joint"


def test_the_report_checks_by_before_the_dates(session: Session) -> None:
    with pytest.raises(ValueError) as caught:
        spending_report(session, MAY_LAST, MAY_FIRST, "vendor")
    assert str(caught.value) == (
        "by must be one of: category, group, merchant, person, account, bank, card"
    )


def test_the_report_refuses_a_start_after_the_end(session: Session) -> None:
    with pytest.raises(ValueError) as caught:
        spending_report(session, MAY_LAST, MAY_FIRST, "merchant")
    assert str(caught.value) == "the start date is after the end date"


def test_the_report_groups_and_totals(session: Session) -> None:
    add(session, CARD, date(2026, 5, 2), -450, description="SQ *ACME COFFEE", last4="1111")
    add(session, CARD, date(2026, 5, 3), -800, description="ACME COFFEE #12", last4="1111")
    add(session, CHECKING, date(2026, 5, 16), 2500, description="VENMO CASHOUT")
    report = spending_report(session, MAY_FIRST, MAY_LAST, "merchant")
    assert (report.start, report.end, report.by) == (MAY_FIRST, MAY_LAST, "merchant")
    assert [(line.label, line.spent_cents, line.count) for line in report.lines] == [
        ("ACME COFFEE", 1250, 2)
    ]
    assert (report.summary.spent_cents, report.summary.unsorted_in_cents) == (1250, 2500)


def test_fin_spending_with_no_options_names_this_month(tmp_settings: Settings) -> None:
    runner = CliRunner(env={"COLUMNS": "200"})
    assert runner.invoke(app, ["db", "upgrade"]).exit_code == 0
    first, last = month_bounds(date.today())
    result = runner.invoke(app, ["spending"])
    assert result.exit_code == 0
    assert result.stdout.splitlines()[:2] == [
        f"Spending from {first.isoformat()} to {last.isoformat()}, by category.",
        "No spending.",
    ]
