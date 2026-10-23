from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.spending import load_flows
from finances.categorize.service import categorize
from finances.categorize.transfers import pair_transfers
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    clear_categories_by_hand,
    clear_category_by_hand,
    clear_split,
    count_uncategorized,
    create_account,
    create_rule,
    create_transfer_pair,
    delete_category,
    delete_feed_transaction,
    get_category_by_name,
    insert_feed_transaction,
    list_category_assignments,
    list_changes,
    list_uncategorized,
    proposal_out_of_date,
    propose_category,
    set_categories_by_hand,
    set_category_by_hand,
    set_split,
    splits_for,
    update_feed_transaction,
)
from finances.domain.audit import SYSTEM
from finances.domain.models import CONFIRMED, DataSource, NewTransaction
from finances.domain.splits import SPLIT, SplitPart

PARTS = [(-1200, "groceries"), (-800, "Home & Garden")]
FROM_PARTS = "a split transaction takes its categories from its parts"
NOT_A_TRANSFER = "a split transaction cannot be in a transfer"
IN_USE = "Home & Garden is in use (transactions: 1, rules: 0); choose a category to move them to"


def add(
    session: Session,
    account_id: int,
    day: int,
    cents: int,
    description: str,
    *,
    pending: bool = False,
) -> int:
    row = TransactionRow(
        account_id=account_id,
        posted_date=date(2026, 5, day),
        amount_cents=cents,
        description=description,
        source="statement",
        is_pending=pending,
        fingerprint=f"{account_id}-{day}-{cents}-{int(pending)}".ljust(64, "0"),
    )
    session.add(row)
    session.flush()
    return row.id


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        card = create_account(opened, "Test Card", "Test Bank", "credit_card")
        checking = create_account(opened, "Test Checking", "Test Bank", "checking")
        savings = create_account(opened, "Test Savings", "Test Bank", "savings")
        grocery = add(opened, card.id, 1, -2000, "FOOBAR GROCERY")
        pending = add(opened, card.id, 2, -1500, "ACME PENDING", pending=True)
        outflow = add(opened, checking.id, 3, -5000, "PROBE TRANSFER")
        inflow = add(opened, savings.id, 3, 5000, "PROBE TRANSFER")
        assert (grocery, pending, outflow, inflow) == (1, 2, 3, 4)
        create_rule(opened, "FOOBAR", "Groceries")
        categorize(opened)
        yield opened


def grocery_and_home(session: Session) -> tuple[int, int]:
    grocery = get_category_by_name(session, "Groceries")
    home = get_category_by_name(session, "Home & Garden")
    assert grocery is not None and home is not None
    return grocery.id, home.id


def add_feed(session: Session, feed_id: str) -> int:
    item = NewTransaction(
        account_id=1,
        statement_id=None,
        posted_date=date(2026, 5, 10),
        transaction_date=None,
        amount_cents=-2000,
        description="FOOBAR GROCERY",
        section=None,
        card_last4=None,
        cardholder=None,
        external_id=None,
        source=DataSource.AGGREGATOR,
        is_pending=False,
        fingerprint=feed_id.ljust(64, "0"),
    )
    return insert_feed_transaction(session, item, feed_id).id


def rewrite(
    session: Session,
    transaction_id: int,
    *,
    amount_cents: int,
    description: str,
    fingerprint: str,
    feed_id: str,
) -> None:
    update_feed_transaction(
        session,
        transaction_id,
        feed_id=feed_id,
        posted_date=date(2026, 5, 10),
        transaction_date=None,
        amount_cents=amount_cents,
        description=description,
        card_last4=None,
        is_pending=False,
        fingerprint=fingerprint,
    )


def test_set_split_stores_parts_and_removes_the_own_category(session: Session) -> None:
    grocery_id, home_id = grocery_and_home(session)
    found = set_split(session, 1, PARTS)
    assert found == [
        SplitPart(transaction_id=1, position=1, amount_cents=-1200, category_id=grocery_id),
        SplitPart(transaction_id=1, position=2, amount_cents=-800, category_id=home_id),
    ]
    assert 1 not in list_category_assignments(session)
    logged = list_changes(session, action="split_set")
    assert [(item.kind, item.record_id, item.before, item.after) for item in logged] == [
        ("transaction", 1, None, "Groceries, Home & Garden")
    ]
    set_split(session, 1, [(-1500, "Dining"), (-500, "Groceries")])
    again = list_changes(session, action="split_set")
    assert (again[0].before, again[0].after) == ("Groceries, Home & Garden", "Dining, Groceries")


def test_set_split_refusals_store_nothing(session: Session) -> None:
    with pytest.raises(ValueError) as missing:
        set_split(session, 99, PARTS)
    assert str(missing.value) == "transaction not found"
    with pytest.raises(ValueError) as pending:
        set_split(session, 2, [(-100, "Groceries"), (-50, "Dining")])
    assert str(pending.value) == "a pending transaction cannot be split"
    create_transfer_pair(session, 3, 4, CONFIRMED)
    with pytest.raises(ValueError) as paired:
        set_split(session, 3, [(-3000, "Dining"), (-2000, "Groceries")])
    assert str(paired.value) == "a transfer cannot be split"
    with pytest.raises(ValueError) as count:
        set_split(session, 1, [(-2000, "Groceries")])
    assert str(count.value) == "a split has 2 to 10 parts"
    with pytest.raises(ValueError) as group:
        set_split(session, 1, [(-1200, "Home"), (-800, "Dining")])
    assert str(group.value) == "rules and transactions take a category, not a group"
    assert splits_for(session, [1, 2, 3, 4]) == {}
    assert list_changes(session, action="split_set") == []


def test_clear_split_removes_the_parts(session: Session) -> None:
    set_split(session, 1, PARTS)
    clear_split(session, 1)
    assert splits_for(session, [1]) == {}
    assert 1 not in list_category_assignments(session)
    logged = list_changes(session, action="split_cleared")
    assert [(item.kind, item.record_id, item.before, item.who) for item in logged] == [
        ("transaction", 1, "Groceries, Home & Garden", "person")
    ]
    with pytest.raises(ValueError) as caught:
        clear_split(session, 1)
    assert str(caught.value) == "the transaction is not split"
    assert splits_for(session, []) == {}


def test_categorize_skips_a_split_transaction(session: Session) -> None:
    set_split(session, 1, PARTS)
    result = categorize(session)
    assert 1 not in list_category_assignments(session)
    assert result.total == 4
    assert result.uncategorized == 3


def test_by_hand_refuses_a_split_and_changes_none(session: Session) -> None:
    set_split(session, 1, PARTS)
    set_category_by_hand(session, 3, "Groceries")
    with pytest.raises(ValueError) as several:
        set_categories_by_hand(session, [3, 1], "Dining")
    assert str(several.value) == FROM_PARTS
    assert (
        list_category_assignments(session)[3].category_id
        == get_category_by_name(session, "Groceries").id
    )
    with pytest.raises(ValueError) as one:
        set_category_by_hand(session, 1, "Dining")
    assert str(one.value) == FROM_PARTS
    with pytest.raises(ValueError) as clear_one:
        clear_category_by_hand(session, 1)
    assert str(clear_one.value) == FROM_PARTS
    with pytest.raises(ValueError) as clear_several:
        clear_categories_by_hand(session, [3, 1])
    assert str(clear_several.value) == FROM_PARTS
    assert (
        list_category_assignments(session)[3].category_id
        == get_category_by_name(session, "Groceries").id
    )


def test_a_split_is_decided_and_an_earlier_proposal_is_out_of_date(session: Session) -> None:
    proposal = propose_category(session, 1, "Dining", "a grocer")
    set_split(session, 1, PARTS)
    assert proposal_out_of_date(session, proposal) is True
    with pytest.raises(ValueError) as caught:
        propose_category(session, 1, "Dining", "a grocer")
    assert str(caught.value) == "a person has already decided this transaction"


def test_uncategorized_leaves_a_split_out(session: Session) -> None:
    before = count_uncategorized(session)
    set_split(session, 1, PARTS)
    assert count_uncategorized(session) == before
    assert 1 not in {item.id for item in list_uncategorized(session, 50)}


def test_a_split_is_never_a_transfer(session: Session) -> None:
    set_split(session, 3, [(-3000, "Dining"), (-2000, "Groceries")])
    assert pair_transfers(session).paired == 0
    with pytest.raises(ValueError) as caught:
        create_transfer_pair(session, 3, 4, CONFIRMED)
    assert str(caught.value) == NOT_A_TRANSFER


def test_feed_delete_and_amount_change_look_after_parts(session: Session) -> None:
    deleted_id = add_feed(session, "gone-1")
    set_split(session, deleted_id, PARTS)
    assert delete_feed_transaction(session, deleted_id) is True
    kept_id = add_feed(session, "keep-1")
    set_split(session, kept_id, PARTS)
    rewrite(
        session,
        kept_id,
        amount_cents=-1800,
        description="FOOBAR GROCERY",
        fingerprint="u" * 64,
        feed_id="post-1",
    )
    assert splits_for(session, [kept_id]) == {}
    cleared = list_changes(session, action="split_cleared")
    assert [(item.who, item.before, item.record_id) for item in cleared] == [
        (SYSTEM, "Groceries, Home & Garden", kept_id)
    ]
    same_id = add_feed(session, "same-1")
    set_split(session, same_id, PARTS)
    rewrite(
        session,
        same_id,
        amount_cents=-2000,
        description="FOOBAR MARKET",
        fingerprint="s" * 64,
        feed_id="post-2",
    )
    grocery_id, home_id = grocery_and_home(session)
    assert splits_for(session, [same_id])[same_id] == [
        SplitPart(transaction_id=same_id, position=1, amount_cents=-1200, category_id=grocery_id),
        SplitPart(transaction_id=same_id, position=2, amount_cents=-800, category_id=home_id),
    ]


def test_delete_category_counts_and_moves_parts(session: Session) -> None:
    set_split(session, 1, PARTS)
    with pytest.raises(ValueError) as caught:
        delete_category(session, "Home & Garden")
    assert str(caught.value) == IN_USE
    deleted = delete_category(session, "Home & Garden", move_to="Dining")
    assert deleted.transactions == 1
    dining = get_category_by_name(session, "Dining")
    assert dining is not None
    assert splits_for(session, [1])[1][1].category_id == dining.id


def test_load_flows_labels_a_split(session: Session) -> None:
    set_split(session, 1, PARTS)
    found = [
        flow
        for flow in load_flows(session, date(2026, 5, 1), date(2026, 5, 31))
        if flow.amount_cents == -2000
    ]
    assert len(found) == 1
    assert (found[0].category, found[0].group) == (SPLIT, SPLIT)
