from collections.abc import Iterator
from datetime import UTC, date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    accept_proposal,
    create_account,
    create_category,
    create_rule,
    create_transfer_pair,
    decline_proposal,
    delete_category,
    list_advice,
    list_proposals,
    log_advice,
    proposal_out_of_date,
    propose_category,
)
from finances.domain.models import CONFIRMED
from tests.support import failed_cleanly, run, table_rows


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        create_account(opened, "Test Card", "Test Bank", "credit_card")
        create_account(opened, "Test Checking", "Test Bank", "checking")
        opened.add(
            TransactionRow(
                account_id=1,
                posted_date=date(2026, 5, 1),
                amount_cents=-500,
                description="ACME PROBE COFFEE",
                source="statement",
                fingerprint="p01".ljust(64, "0"),
            )
        )
        opened.flush()
        yield opened


def test_a_proposal_is_stamped_in_utc(session: Session) -> None:
    found = propose_category(session, 1, "Dining", "ACME PROBE is a cafe")
    assert found.created_at.tzinfo is UTC
    note = log_advice(session, "Keep the coffee budget in mind.")
    assert note.created_at.tzinfo is UTC


def test_listing_refuses_a_limit_of_zero(session: Session) -> None:
    with pytest.raises(ValueError, match="limit must be at least 1"):
        list_proposals(session, limit=0)
    with pytest.raises(ValueError, match="limit must be at least 1"):
        list_advice(session, limit=0)


def test_a_declined_proposal_is_not_decided_again(session: Session) -> None:
    propose_category(session, 1, "Dining", "ACME PROBE is a cafe")
    decline_proposal(session, 1)
    with pytest.raises(ValueError, match="proposal 1 is already declined"):
        accept_proposal(session, 1)
    with pytest.raises(ValueError, match="proposal 1 is already declined"):
        decline_proposal(session, 1)


def test_a_rules_category_does_not_make_a_proposal_out_of_date(session: Session) -> None:
    session.add(
        TransactionRow(
            account_id=1,
            posted_date=date(2026, 5, 2),
            amount_cents=-2599,
            description="FOOBAR PROBE GROCERY",
            source="statement",
            fingerprint="p02".ljust(64, "0"),
        )
    )
    session.flush()
    create_rule(session, "FOOBAR PROBE", "Groceries")
    categorize(session)
    found = propose_category(session, 2, "Dining", "FOOBAR PROBE has a deli")
    assert proposal_out_of_date(session, found) is False


def test_pairing_after_a_proposal_makes_it_out_of_date(session: Session) -> None:
    session.add(
        TransactionRow(
            account_id=2,
            posted_date=date(2026, 5, 3),
            amount_cents=500,
            description="ACME PROBE REFUND",
            source="statement",
            fingerprint="p03".ljust(64, "0"),
        )
    )
    session.flush()
    found = propose_category(session, 1, "Dining", "ACME PROBE is a cafe")
    create_transfer_pair(session, 1, 2, CONFIRMED)
    assert proposal_out_of_date(session, found) is True
    with pytest.raises(
        ValueError, match="proposal 1 is out of date: the transaction was decided since"
    ):
        accept_proposal(session, 1)


def test_accepting_after_the_category_was_deleted_is_refused(session: Session) -> None:
    create_category(session, "Probe Pets", "Food")
    propose_category(session, 1, "Probe Pets", "ACME PROBE sells pet treats")
    delete_category(session, "Probe Pets")
    with pytest.raises(ValueError, match="category not found"):
        accept_proposal(session, 1)
    assert list_proposals(session)[0].status == "open"


def add_coffee(session: Session, number: int, description: str) -> None:
    session.add(
        TransactionRow(
            account_id=1,
            posted_date=date(2026, 5, number),
            amount_cents=-500,
            description=description,
            source="statement",
            fingerprint=f"c{number:02d}".ljust(64, "0"),
        )
    )
    session.flush()


def test_a_deleted_transaction_is_out_of_date(tmp_settings: Settings) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        add_coffee(session, 1, "ACME PROBE COFFEE")
        propose_category(session, 1, "Dining", "ACME PROBE is a cafe")
        session.delete(session.get(TransactionRow, 1))
        session.flush()
        found = list_proposals(session)[0]
        assert proposal_out_of_date(session, found) is True
    engine.dispose()
    rows = table_rows(run("review", "list").stdout)
    assert rows[1] == ["1", "", "", "", "", "", "Dining", "ACME PROBE is a cafe", "out of date"]


def test_declining_two_ids(tmp_settings: Settings) -> None:
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        add_coffee(session, 1, "ACME PROBE COFFEE")
        add_coffee(session, 2, "BAZ PROBE CAFE")
        propose_category(session, 1, "Coffee & Dessert", "ACME PROBE is a cafe")
        propose_category(session, 2, "Dining", "BAZ PROBE serves lunch")
    engine.dispose()
    declined = run("review", "decline", "--id", "1", "--id", "2")
    assert (declined.exit_code, declined.stdout) == (
        0,
        "Declined proposal 1.\nDeclined proposal 2.\n",
    )
    assert run("review", "list").stdout == "No open proposals.\n"
    assert failed_cleanly(run("review", "decline", "--id", "1"), "proposal 1 is already declined")
