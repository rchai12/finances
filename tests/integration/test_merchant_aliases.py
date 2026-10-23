from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finances.analysis.refunds import refund_facts
from finances.analysis.spending import load_flows
from finances.categorize.service import categorize
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    add_alias,
    alias_map,
    create_account,
    create_rule,
    delete_alias,
    list_aliases,
    list_categories,
    list_category_assignments,
    list_changes,
    list_rules,
    propose_rule,
)
from finances.domain.merchants import MerchantAlias


@pytest.fixture
def session(db_engine: Engine) -> Iterator[Session]:
    with session_scope(db_engine) as opened:
        yield opened


def add_card(session: Session, rows: tuple[tuple[date, int, str], ...]) -> None:
    create_account(session, "Test Card", "Test Bank", "credit_card")
    for number, (day, cents, description) in enumerate(rows, start=1):
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=day,
                amount_cents=cents,
                description=description,
                source="statement",
                fingerprint=f"a{number:02d}".ljust(64, "0"),
            )
        )
    session.flush()


def assigned(session: Session) -> dict[int, str]:
    names = {item.id: item.name for item in list_categories(session)}
    return {txn: names[row.category_id] for txn, row in list_category_assignments(session).items()}


def test_add_list_delete_and_audit(session: Session) -> None:
    later = add_alias(session, "BAZ CAFE", "BAZ COFFEE")
    first = add_alias(session, "  acme   cafe ", "Acme Coffee")
    assert first == MerchantAlias(2, "ACME CAFE", "ACME COFFEE")
    assert [item.source for item in list_aliases(session)] == ["ACME CAFE", "BAZ CAFE"]
    assert alias_map(session) == {"ACME CAFE": "ACME COFFEE", "BAZ CAFE": "BAZ COFFEE"}
    removed = delete_alias(session, "acme cafe")
    assert removed == first
    assert list_aliases(session) == [later]
    found = [item for item in list_changes(session) if item.kind == "alias"]
    assert [(item.action, item.before, item.after) for item in found] == [
        ("alias_deleted", "ACME CAFE -> ACME COFFEE", None),
        ("alias_added", None, "ACME CAFE -> ACME COFFEE"),
        ("alias_added", None, "BAZ CAFE -> BAZ COFFEE"),
    ]


def test_a_refused_alias_stores_nothing(session: Session) -> None:
    add_alias(session, "ACME CAFE", "ACME COFFEE")
    aliases = list_aliases(session)
    count = len(list_changes(session))
    with pytest.raises(ValueError, match="a merchant cannot be merged into itself"):
        add_alias(session, "ACME CAFE", "ACME CAFE")
    assert list_aliases(session) == aliases
    assert len(list_changes(session)) == count


def test_an_alias_does_not_take_a_category_away(session: Session) -> None:
    add_card(session, ((date(2026, 5, 1), -450, "ACME CAFE"),))
    create_rule(session, "ACME CAFE", "Dining")
    categorize(session)
    assert assigned(session) == {1: "Dining"}
    add_alias(session, "ACME CAFE", "ACME COFFEE")
    categorize(session)
    assert assigned(session) == {1: "Dining"}
    assert list_rules(session)[0].pattern == "ACME CAFE"


def test_load_flows_uses_the_merged_name(session: Session) -> None:
    add_card(session, ((date(2026, 5, 1), -450, "ACME CAFE"),))
    before = load_flows(session, date(2026, 5, 1), date(2026, 5, 31))
    assert [item.merchant for item in before] == ["ACME CAFE"]
    add_alias(session, "ACME CAFE", "ACME COFFEE")
    after = load_flows(session, date(2026, 5, 1), date(2026, 5, 31))
    assert [item.merchant for item in after] == ["ACME COFFEE"]


def test_refund_facts_across_an_alias(session: Session) -> None:
    add_card(
        session,
        (
            (date(2026, 5, 1), -500, "ACME CAFE"),
            (date(2026, 5, 10), 500, "ACME COFFEE"),
        ),
    )
    create_rule(session, "ACME", "Dining")
    categorize(session)
    assert refund_facts(session, 2).purchase is None
    add_alias(session, "ACME CAFE", "ACME COFFEE")
    found = refund_facts(session, 2).purchase
    assert found is not None and found.id == 1


def test_refund_facts_when_the_refund_uses_the_source_name(session: Session) -> None:
    add_card(
        session,
        (
            (date(2026, 5, 1), -500, "ACME COFFEE"),
            (date(2026, 5, 10), 500, "ACME CAFE"),
        ),
    )
    create_rule(session, "ACME", "Dining")
    categorize(session)
    assert refund_facts(session, 2).purchase is None
    add_alias(session, "ACME CAFE", "ACME COFFEE")
    found = refund_facts(session, 2).purchase
    assert found is not None and found.id == 1


def test_propose_rule_matches_either_name(session: Session) -> None:
    add_card(session, ((date(2026, 5, 1), -450, "ACME CAFE"),))
    with pytest.raises(ValueError, match="the rule does not match the example transaction"):
        propose_rule(session, 1, "ACME COFFEE", "Dining", "same shop", match="equals")
    add_alias(session, "ACME CAFE", "ACME COFFEE")
    found = propose_rule(session, 1, "ACME COFFEE", "Dining", "same shop", match="equals")
    assert (found.kind, found.pattern, found.match, found.status) == (
        "rule",
        "ACME COFFEE",
        "equals",
        "open",
    )
