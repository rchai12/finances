from datetime import UTC, date, datetime

import anyio
import pytest
from mcp.client import Client

from finances.categorize.service import categorize
from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    create_rule,
    list_categories,
    list_category_assignments,
    set_category_by_hand,
)
from finances.mcp_server.server import build_server
from tests.support import failed_cleanly, run, table_rows

BEFORE = 'contains "ACME" -> Dining (priority 0)'
CHANGE = {"rule_id": 1, "reason": "a coffee shop", "category": "Coffee & Dessert", "priority": 5}


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def error(name: str, arguments: dict) -> list[str]:
    return [item.text for item in call(name, arguments).content]


@pytest.fixture
def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Rule 1 puts ACME in Dining, so transaction 1 (ACME COFFEE) is Dining by the rule;
    a person set transaction 2 (FOOBAR GROCERY) to Groceries by hand."""
    monkeypatch.setattr(
        "finances.db.repositories.proposals._now", lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    )
    monkeypatch.setattr(
        "finances.db.repositories.rule_changes._now",
        lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
    )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        for number, (cents, description) in enumerate(
            ((-500, "ACME COFFEE"), (-2599, "FOOBAR GROCERY")), start=1
        ):
            session.add(
                TransactionRow(
                    account_id=1,
                    posted_date=date(2026, 5, number),
                    amount_cents=cents,
                    description=description,
                    source="statement",
                    fingerprint=f"t{number:02d}".ljust(64, "0"),
                )
            )
        session.flush()
        create_rule(session, "ACME", "Dining")
        categorize(session)
        set_category_by_hand(session, 2, "Groceries")
    engine.dispose()
    return tmp_settings


def category_of(transaction_id: int) -> str | None:
    engine = get_engine()
    with session_scope(engine) as session:
        found = list_category_assignments(session).get(transaction_id)
        names = {category.id: category.name for category in list_categories(session)}
    engine.dispose()
    return None if found is None else names[found.category_id]


def review_row() -> list[str]:
    return table_rows(run("review", "list").stdout)[1]


def test_a_persons_choice_can_be_proposed_over(card: Settings) -> None:
    made = call("propose_category", {"transaction_id": 2, "category": "Dining", "reason": "a deli"})
    assert made.structured_content["proposal"]["category"] == "Dining"
    assert review_row()[5:] == ["Groceries", "Dining", "a deli", "open"]
    accepted = run("review", "accept", "--id", "1")
    assert accepted.stdout == "Accepted proposal 1: Dining for transaction 2.\n"
    assert category_of(2) == "Dining"


def test_the_category_it_has_is_refused(card: Settings) -> None:
    arguments = {"transaction_id": 2, "category": "groceries", "reason": "a grocer"}
    assert error("propose_category", arguments) == [
        "Error executing tool propose_category: the transaction already has this category"
    ]


def test_a_person_changing_it_since_puts_it_out_of_date(card: Settings) -> None:
    call("propose_category", {"transaction_id": 2, "category": "Dining", "reason": "a deli"})
    run("transactions", "set-category", "--id", "2", "--category", "Coffee & Dessert")
    assert review_row()[8] == "out of date"
    assert failed_cleanly(
        run("review", "accept", "--id", "1"),
        "proposal 1 is out of date: the transaction was decided since",
    )


def test_the_agent_proposes_changing_a_rule(card: Settings) -> None:
    made = call("propose_rule_change", CHANGE).structured_content["proposal"]
    assert {key: made[key] for key in ("kind", "transaction_id", "category", "rule")} == {
        "kind": "rule_edit",
        "transaction_id": None,
        "category": "Coffee & Dessert",
        "rule": {"match": "contains", "pattern": "ACME", "priority": 5},
    }
    assert made["rule_change"] == {"rule_id": 1, "before": BEFORE, "delete": False}
    assert review_row() == [
        "1",
        "",
        "",
        "",
        "",
        BEFORE,
        'rule 1: contains "ACME" -> Coffee & Dessert (priority 5)',
        "a coffee shop",
        "open",
    ]
    accepted = run("review", "accept", "--id", "1")
    assert accepted.stdout == (
        'Accepted proposal 1: rule 1 is now contains "ACME" -> Coffee & Dessert (priority 5).\n'
        "Categorized 2 transactions: 1 changed, 0 without a category.\n"
    )
    assert (category_of(1), category_of(2)) == ("Coffee & Dessert", "Groceries")


def test_the_agent_proposes_deleting_a_rule(card: Settings) -> None:
    made = call("propose_rule_change", {"rule_id": 1, "reason": "too broad", "delete": True})
    proposal = made.structured_content["proposal"]
    assert (proposal["kind"], proposal["rule_change"]) == (
        "rule_delete",
        {"rule_id": 1, "before": BEFORE, "delete": True},
    )
    assert review_row()[5:7] == [BEFORE, "delete rule 1"]
    accepted = run("review", "accept", "--id", "1")
    assert accepted.stdout == (
        "Accepted proposal 1: rule 1 deleted.\n"
        "Categorized 2 transactions: 0 changed, 1 without a category.\n"
    )
    assert table_rows(run("rules", "list").stdout)[1:] == []


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({**CHANGE, "rule_id": 9}, "rule not found"),
        ({"rule_id": 1, "reason": "why"}, "name at least one field to change"),
        ({**CHANGE, "delete": True}, "a deletion changes no fields"),
        ({"rule_id": 1, "reason": "why", "category": "dining"}, "the rule already is like this"),
        ({**CHANGE, "category": "Food"}, "rules and transactions take a category, not a group"),
        ({**CHANGE, "category": "Pets"}, "category not found"),
        ({**CHANGE, "reason": " "}, "a reason must be 1 to 200 characters"),
    ],
)
def test_a_refused_rule_change(card: Settings, arguments: dict, message: str) -> None:
    assert error("propose_rule_change", arguments) == [
        f"Error executing tool propose_rule_change: {message}"
    ]


def test_one_open_change_for_a_rule(card: Settings) -> None:
    call("propose_rule_change", CHANGE)
    assert error("propose_rule_change", {"rule_id": 1, "reason": "x", "delete": True}) == [
        "Error executing tool propose_rule_change: this rule already has an open proposal"
    ]


def test_a_rule_edited_since_puts_it_out_of_date(card: Settings) -> None:
    call("propose_rule_change", CHANGE)
    run("rules", "edit", "--id", "1", "--priority", "3")
    assert review_row()[8] == "out of date"
    assert failed_cleanly(
        run("review", "accept", "--id", "1"),
        "proposal 1 is out of date: the rules or categories changed since",
    )


def test_a_declined_change_is_not_proposed_again(card: Settings) -> None:
    call("propose_rule_change", CHANGE)
    run("review", "decline", "--id", "1")
    assert error("propose_rule_change", CHANGE) == [
        "Error executing tool propose_rule_change: a person declined this proposal already"
    ]
    assert (
        call("propose_rule_change", {**CHANGE, "priority": 6}).structured_content["proposal"]["id"]
        == 2
    )
