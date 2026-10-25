from datetime import UTC, date, datetime

import anyio
import pytest
from mcp.client import Client

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import create_account, get_category_by_name
from finances.mcp_server.server import build_server
from tests.support import failed_cleanly, run, table_rows

GROUP = {"name": " Pets ", "example_id": 1, "reason": "pet costs"}
CATEGORY = {"name": "Pet Supplies", "group": "home", "example_id": 1, "reason": "a pet shop"}
TAKEN = "a category with this name already exists"


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def error(name: str, arguments: dict) -> list[str]:
    return [item.text for item in call(name, arguments).content]


@pytest.fixture
def card(tmp_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """One card purchase with no category: transaction 1, FOOBAR PET SUPPLY, -$25.99."""
    for module in ("proposals", "new_categories"):
        monkeypatch.setattr(
            f"finances.db.repositories.{module}._now",
            lambda: datetime(2026, 5, 25, 12, 0, tzinfo=UTC),
        )
    upgrade_to_head()
    engine = get_engine()
    with session_scope(engine) as session:
        create_account(session, "Test Card", "Test Bank", "credit_card")
        session.add(
            TransactionRow(
                account_id=1,
                posted_date=date(2026, 5, 1),
                amount_cents=-2599,
                description="FOOBAR PET SUPPLY",
                source="statement",
                fingerprint="t01".ljust(64, "0"),
            )
        )
    engine.dispose()
    return tmp_settings


def item(kind: str, new: dict, reason: str) -> dict:
    return {
        "proposal": {
            "id": 1,
            "kind": kind,
            "transaction_id": 1,
            "in_id": None,
            "category": None,
            "rule": None,
            "alias": None,
            "new": new,
            "reason": reason,
            "status": "open",
            "created_at": "2026-05-25T12:00:00+00:00",
            "decided_at": None,
            "out_of_date": False,
        }
    }


def test_the_agent_proposes_a_group(card: Settings) -> None:
    made = call("propose_group", {**GROUP, "kind": "income", "sensitive": True})
    assert made.structured_content == item(
        "group",
        {"name": "Pets", "group": None, "kind": "income", "sensitive": True, "tax": None},
        "pet costs",
    )


def test_the_agent_proposes_a_category_in_a_group(card: Settings) -> None:
    made = call("propose_new_category", {**CATEGORY, "tax": True})
    assert made.structured_content == item(
        "new_category",
        {"name": "Pet Supplies", "group": "Home", "kind": None, "sensitive": None, "tax": True},
        "a pet shop",
    )


@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        ("propose_group", {**GROUP, "name": "food"}, TAKEN),
        ("propose_group", {**GROUP, "name": "Groceries"}, TAKEN),
        ("propose_group", {**GROUP, "example_id": 9}, "transaction not found"),
        ("propose_new_category", {**CATEGORY, "group": "Dining"}, "group not found"),
        ("propose_new_category", {**CATEGORY, "name": "Dining"}, TAKEN),
        (
            "propose_new_category",
            {**CATEGORY, "reason": " "},
            "a reason must be 1 to 200 characters",
        ),
    ],
)
def test_a_refused_proposal(card: Settings, tool: str, arguments: dict, message: str) -> None:
    assert error(tool, arguments) == [f"Error executing tool {tool}: {message}"]


def test_one_open_proposal_for_a_name(card: Settings) -> None:
    call("propose_group", GROUP)
    again = "this name already has an open proposal"
    assert error("propose_group", GROUP) == [f"Error executing tool propose_group: {again}"]
    assert error("propose_new_category", {**CATEGORY, "name": "pets"}) == [
        f"Error executing tool propose_new_category: {again}"
    ]


def test_a_person_accepts_a_group_in_the_terminal(card: Settings) -> None:
    call("propose_group", {**GROUP, "sensitive": True})
    rows = table_rows(run("review", "list").stdout)
    assert rows[1] == [
        "1",
        "2026-05-01",
        "Test Card",
        "FOOBAR PET SUPPLY",
        "-$25.99",
        "",
        "a new group: Pets (sensitive)",
        "pet costs",
        "open",
    ]
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (0, "Accepted proposal 1: the group Pets.\n")
    assert ["Pets", "", "sensitive"] in table_rows(run("categories", "list").stdout)


def test_a_person_accepts_a_category_in_the_terminal(card: Settings) -> None:
    call("propose_new_category", {**CATEGORY, "tax": True})
    rows = table_rows(run("review", "list").stdout)
    assert rows[1][6] == "a new category: Pet Supplies in Home, tax-relevant"
    accepted = run("review", "accept", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: the category Pet Supplies in Home.\n",
    )
    engine = get_engine()
    with session_scope(engine) as session:
        found = get_category_by_name(session, "Pet Supplies")
        group = get_category_by_name(session, "Home")
    engine.dispose()
    assert found is not None and group is not None
    assert (found.group_id, found.is_tax) == (group.id, True)


def test_a_group_whose_name_was_taken_since_is_out_of_date(card: Settings) -> None:
    call("propose_group", GROUP)
    run("categories", "add-group", "--name", "Pets")
    assert table_rows(run("review", "list").stdout)[1][8] == "out of date"
    assert failed_cleanly(
        run("review", "accept", "--id", "1"),
        "proposal 1 is out of date: the categories changed since",
    )


def test_a_declined_name_is_not_proposed_again(card: Settings) -> None:
    call("propose_group", GROUP)
    assert run("review", "decline", "--id", "1").stdout == "Declined proposal 1.\n"
    assert error("propose_group", GROUP) == [
        "Error executing tool propose_group: a person declined this proposal already"
    ]
