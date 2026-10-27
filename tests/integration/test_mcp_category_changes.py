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

RENAME = {"name": "dining", "reason": "clearer", "rename_to": "Restaurants"}
DELETE = {"name": "Dining", "reason": "a duplicate", "delete": True, "move_to": "coffee & dessert"}
IN_USE = "Dining is in use (transactions: 1, rules: 1); choose a category to move them to"


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def made(name: str, arguments: dict) -> dict:
    return call(name, arguments).structured_content["proposal"]


def error(name: str, arguments: dict) -> list[str]:
    return [item.text for item in call(name, arguments).content]


@pytest.fixture
def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Rule 1 puts ACME in Dining, so transaction 1 (ACME COFFEE) is Dining by the rule;
    a person set transaction 2 (FOOBAR GROCERY) to Groceries by hand."""
    for module in ("proposals", "category_changes"):
        monkeypatch.setattr(
            f"finances.db.repositories.{module}._now",
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


def rows() -> list[list[str]]:
    return table_rows(run("review", "list").stdout)[1:]


def test_the_agent_proposes_renaming_a_category(card: Settings) -> None:
    proposal = made("propose_category_change", RENAME)
    assert (proposal["kind"], proposal["transaction_id"], proposal["category_change"]) == (
        "category_rename",
        None,
        {"name": "Dining", "rename_to": "Restaurants", "delete": False, "move_to": None},
    )
    assert rows() == [["1", "", "", "", "", "Dining", "rename to Restaurants", "clearer", "open"]]
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: Dining is now Restaurants.\n",
    )
    assert ["Food", "Restaurants", ""] in table_rows(run("categories", "list").stdout)
    assert category_of(1) == "Restaurants"


def test_a_rename_carries_the_agents_other_proposals(card: Settings) -> None:
    made("propose_category", {"transaction_id": 2, "category": "Dining", "reason": "a deli"})
    made("propose_category_change", RENAME)
    run("review", "accept", "--id", "2")
    assert rows() == [
        [
            "1",
            "2026-05-02",
            "Test Card",
            "FOOBAR GROCERY",
            "-$25.99",
            "Groceries",
            "Restaurants",
            "a deli",
            "open",
        ]
    ]
    assert run("review", "accept", "--id", "1").exit_code == 0
    assert category_of(2) == "Restaurants"


def test_the_agent_proposes_deleting_a_category(card: Settings) -> None:
    proposal = made("propose_category_change", DELETE)
    assert proposal["category_change"] == {
        "name": "Dining",
        "rename_to": None,
        "delete": True,
        "move_to": "Coffee & Dessert",
    }
    assert rows()[0][5:7] == ["Dining", "delete, moving its uses to Coffee & Dessert"]
    accepted = run("review", "accept", "--id", "1")
    assert accepted.stdout == (
        "Accepted proposal 1: Dining deleted, its uses moved to Coffee & Dessert.\n"
    )
    assert category_of(1) == "Coffee & Dessert"


def test_a_delete_puts_the_agents_other_proposals_out_of_date(card: Settings) -> None:
    made("propose_category", {"transaction_id": 2, "category": "Dining", "reason": "a deli"})
    made("propose_category_change", DELETE)
    run("review", "accept", "--id", "2")
    assert [row[8] for row in rows()] == ["out of date"]


def test_the_agent_proposes_deleting_an_empty_group(card: Settings) -> None:
    run("categories", "add-group", "--name", "Spare")
    made("propose_category_change", {"name": "Spare", "reason": "unused", "delete": True})
    assert rows()[0][5:7] == ["Spare", "delete"]
    assert run("review", "accept", "--id", "1").stdout == "Accepted proposal 1: Spare deleted.\n"


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({**RENAME, "name": "Pets"}, "category not found"),
        ({"name": "Dining", "reason": "why"}, "name a new name or delete=true"),
        ({**RENAME, "delete": True}, "rename or delete, not both"),
        ({**RENAME, "rename_to": "groceries"}, "a category with this name already exists"),
        ({**RENAME, "rename_to": "Dining"}, "the name already is like this"),
        ({"name": "Dining", "reason": "why", "delete": True}, IN_USE),
        (
            {"name": "Food", "reason": "why", "delete": True},
            "a group can be deleted only when it has no categories",
        ),
        ({**DELETE, "move_to": "Food"}, "rules and transactions take a category, not a group"),
        ({**DELETE, "move_to": "Dining"}, "a category cannot be moved to itself"),
        ({**RENAME, "reason": " "}, "a reason must be 1 to 200 characters"),
    ],
)
def test_a_refused_change(card: Settings, arguments: dict, message: str) -> None:
    assert error("propose_category_change", arguments) == [
        f"Error executing tool propose_category_change: {message}"
    ]


def test_one_open_change_for_a_category(card: Settings) -> None:
    made("propose_category_change", RENAME)
    assert error("propose_category_change", DELETE) == [
        "Error executing tool propose_category_change: this category already has an open proposal"
    ]


def test_a_category_renamed_by_hand_since_puts_it_out_of_date(card: Settings) -> None:
    made("propose_category_change", RENAME)
    run("categories", "rename", "--name", "Dining", "--to", "Eating Out")
    assert rows()[0][8] == "out of date"
    assert failed_cleanly(
        run("review", "accept", "--id", "1"),
        "proposal 1 is out of date: the categories changed since",
    )


def test_a_declined_change_is_not_proposed_again(card: Settings) -> None:
    made("propose_category_change", RENAME)
    run("review", "decline", "--id", "1")
    assert error("propose_category_change", RENAME) == [
        "Error executing tool propose_category_change: a person declined this proposal already"
    ]
    assert made("propose_category_change", {**RENAME, "rename_to": "Eating Out"})["id"] == 2
