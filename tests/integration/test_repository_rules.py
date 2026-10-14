from datetime import date

import pytest
from sqlalchemy import Engine

from finances.db.engine import session_scope
from finances.db.repositories import (
    create_account,
    create_person,
    create_statement,
    list_feed_accounts,
    map_feed_account,
    resolve_owner,
    statement_periods,
)

BAD_ID = "feed account id must be 1 to 200 characters"
BAD_TYPE = "type must be one of: checking, savings, credit_card, other"


@pytest.fixture
def card(db_engine: Engine) -> Engine:
    with session_scope(db_engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        create_account(session, "Test Other", "Test Bank", "credit_card")
    return db_engine


def mappings(engine: Engine) -> list[tuple[int, str, str]]:
    with session_scope(engine) as session:
        return [(m.account_id, m.provider_account_id, m.link) for m in list_feed_accounts(session)]


def test_a_mapping_keeps_the_id_without_outer_spaces(card: Engine) -> None:
    with session_scope(card) as session:
        map_feed_account(session, 1, "  ACT-1 ", "alex")
    assert mappings(card) == [(1, "ACT-1", "alex")]


@pytest.mark.parametrize("feed_id", ["", "  ", "X" * 201])
def test_a_mapping_with_an_unusable_id_is_refused(card: Engine, feed_id: str) -> None:
    with session_scope(card) as session, pytest.raises(ValueError, match=f"^{BAD_ID}$"):
        map_feed_account(session, 1, feed_id, "alex")
    assert mappings(card) == []


def test_the_same_id_with_spaces_is_the_same_mapping(card: Engine) -> None:
    with session_scope(card) as session:
        map_feed_account(session, 1, "ACT-1", "alex")
    with session_scope(card) as session, pytest.raises(ValueError, match="already mapped"):
        map_feed_account(session, 2, " ACT-1 ", "alex")


@pytest.mark.parametrize("owner", ["joint", "JOINT", "  Joint  "])
def test_joint_is_no_person(db_engine: Engine, owner: str) -> None:
    with session_scope(db_engine) as session:
        assert resolve_owner(session, owner) is None


def test_a_person_is_found_ignoring_case_and_spaces(db_engine: Engine) -> None:
    with session_scope(db_engine) as session:
        kim = create_person(session, "Kim")
        assert resolve_owner(session, "  kIM ") == kim


@pytest.mark.parametrize("owner", ["Nobody", "", "  "])
def test_an_unknown_owner_is_refused(db_engine: Engine, owner: str) -> None:
    with session_scope(db_engine) as session:
        create_person(session, "Kim")
        with pytest.raises(ValueError, match="^person not found$"):
            resolve_owner(session, owner)


@pytest.mark.parametrize("kind", ["loan", "", "CHECKING", "credit card"])
def test_an_unknown_type_gets_a_plain_message(db_engine: Engine, kind: str) -> None:
    with session_scope(db_engine) as session, pytest.raises(ValueError, match=f"^{BAD_TYPE}$"):
        create_account(session, "Probe", "Probe Bank", kind)


def test_the_type_is_checked_first(db_engine: Engine) -> None:
    with session_scope(db_engine) as session, pytest.raises(ValueError, match=f"^{BAD_TYPE}$"):
        create_account(session, "", "", "loan", currency="usd", last4="12")


def test_statement_periods(card: Engine) -> None:
    with session_scope(card) as session:
        assert statement_periods(session, 1) == []
        for account_id, start, end, sha in (
            (1, date(2026, 1, 1), date(2026, 1, 31), "a"),
            (1, date(2026, 2, 1), date(2026, 2, 28), "b"),
            (2, date(2026, 3, 1), date(2026, 3, 31), "c"),
        ):
            create_statement(
                session,
                account_id=account_id,
                source_filename=f"{sha}.pdf",
                file_sha256=sha * 64,
                parser_name="probe",
                period_start=start,
                period_end=end,
                opening_balance_cents=0,
                closing_balance_cents=0,
                lines_parsed=0,
                rows_inserted=0,
                rows_duplicate=0,
            )
        assert sorted(statement_periods(session, 1)) == [
            (date(2026, 1, 1), date(2026, 1, 31)),
            (date(2026, 2, 1), date(2026, 2, 28)),
        ]
