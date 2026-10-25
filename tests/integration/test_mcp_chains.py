from datetime import UTC, date, datetime

import anyio
import pytest
from mcp.client import Client

from finances.config import Settings
from finances.db.engine import get_engine, session_scope
from finances.db.migrate import upgrade_to_head
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    create_account,
    get_category_by_name,
    list_categories,
    list_category_assignments,
)
from finances.mcp_server.server import build_server
from tests.support import failed_cleanly, run, table_rows

GROUP = {"name": "Pets", "example_id": 1, "reason": "pet costs"}
CATEGORY = {"name": "Dog Food", "group": "pets", "example_id": 1, "reason": "a pet shop"}
PUT = {"transaction_id": 1, "category": "dog food", "reason": "dog food"}
RULE = {"example_id": 1, "pattern": "FOOBAR PET", "category": "Dog Food", "reason": "the shop"}


def call(name: str, arguments: dict | None = None):
    async def go():
        async with Client(build_server()) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def made(name: str, arguments: dict) -> dict:
    return call(name, arguments).structured_content["proposal"]


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


@pytest.fixture
def chain(card: Settings) -> Settings:
    """1 a group Pets; 2 a category Dog Food in it; 3 transaction 1 in Dog Food; 4 a rule into
    Dog Food. 2 waits for 1, and 3 and 4 wait for 2."""
    made("propose_group", GROUP)
    made("propose_new_category", CATEGORY)
    made("propose_category", PUT)
    made("propose_rule", RULE)
    return card


def states() -> list[list[str]]:
    return [[row[0], row[6], row[8]] for row in table_rows(run("review", "list").stdout)[1:]]


def category_of_transaction() -> str | None:
    engine = get_engine()
    with session_scope(engine) as session:
        found = list_category_assignments(session).get(1)
        names = {category.id: category.name for category in list_categories(session)}
    engine.dispose()
    return None if found is None else names[found.category_id]


def test_each_proposal_names_what_it_waits_for(card: Settings) -> None:
    assert made("propose_group", GROUP)["waits_for"] is None
    second = made("propose_new_category", CATEGORY)
    assert (second["new"]["group"], second["waits_for"]) == ("Pets", 1)
    third = made("propose_category", PUT)
    assert (third["category"], third["waits_for"]) == ("Dog Food", 2)
    fourth = made("propose_rule", RULE)
    assert (fourth["category"], fourth["waits_for"]) == ("Dog Food", 2)
    listed = call("list_proposals").structured_content["proposals"]
    assert [(item["id"], item["waits_for"]) for item in listed] == [
        (4, 2),
        (3, 2),
        (2, 1),
        (1, None),
    ]


def test_the_list_shows_what_waits(chain: Settings) -> None:
    assert states() == [
        ["4", 'a rule: contains "FOOBAR PET" -> Dog Food (priority 0)', "waits for #2"],
        ["3", "Dog Food", "waits for #2"],
        ["2", "a new category: Dog Food in Pets", "waits for #1"],
        ["1", "a new group: Pets", "open"],
    ]


def test_an_unknown_name_is_still_refused(card: Settings) -> None:
    refused = call("propose_category", {**PUT, "category": "Cat Food"})
    assert [item.text for item in refused.content] == [
        "Error executing tool propose_category: category not found"
    ]
    refused = call("propose_new_category", {**CATEGORY, "group": "Birds"})
    assert [item.text for item in refused.content] == [
        "Error executing tool propose_new_category: group not found"
    ]


def test_a_waiting_proposal_is_not_accepted_alone(chain: Settings) -> None:
    assert failed_cleanly(run("review", "accept", "--id", "3"), "proposal 3 waits for proposal 2")
    assert failed_cleanly(
        run("review", "accept", "--id", "3", "--id", "1"), "proposal 3 waits for proposal 2"
    )
    engine = get_engine()
    with session_scope(engine) as session:
        assert get_category_by_name(session, "Pets") is None
    engine.dispose()


def test_a_chain_accepted_together_goes_parents_first(chain: Settings) -> None:
    accepted = run("review", "accept", "--id", "3", "--id", "2", "--id", "1")
    assert (accepted.exit_code, accepted.stdout) == (
        0,
        "Accepted proposal 1: the group Pets.\n"
        "Accepted proposal 2: the category Dog Food in Pets.\n"
        "Accepted proposal 3: Dog Food for transaction 1.\n",
    )
    assert category_of_transaction() == "Dog Food"
    assert states() == [["4", 'a rule: contains "FOOBAR PET" -> Dog Food (priority 0)', "open"]]


def test_accepting_the_parent_ends_the_waiting(chain: Settings) -> None:
    run("review", "accept", "--id", "1")
    assert states()[-1] == ["2", "a new category: Dog Food in Pets", "open"]
    assert states()[0][2] == "waits for #2"


def test_declining_a_parent_declines_what_waits_on_it(chain: Settings) -> None:
    declined = run("review", "decline", "--id", "1")
    assert (declined.exit_code, declined.stdout) == (
        0,
        "Declined proposal 1.\n"
        "Declined proposal 2, which waited for 1.\n"
        "Declined proposal 3, which waited for 2.\n"
        "Declined proposal 4, which waited for 2.\n",
    )
    assert run("review", "list").stdout == "No open proposals.\n"


def test_a_parent_and_its_child_declined_together(chain: Settings) -> None:
    declined = run("review", "decline", "--id", "2", "--id", "3")
    assert (declined.exit_code, declined.stdout) == (
        0,
        "Declined proposal 2.\n"
        "Declined proposal 3, which waited for 2.\n"
        "Declined proposal 4, which waited for 2.\n",
    )
    assert states() == [["1", "a new group: Pets", "open"]]


def test_made_by_hand_the_proposals_stop_waiting(chain: Settings) -> None:
    run("categories", "add-group", "--name", "Pets")
    run("categories", "add", "--name", "Dog Food", "--group", "Pets")
    assert [row[2] for row in states()] == ["open", "open", "out of date", "out of date"]
    assert run("review", "decline", "--id", "2").stdout == "Declined proposal 2.\n"
    accepted = run("review", "accept", "--id", "3")
    assert accepted.stdout == "Accepted proposal 3: Dog Food for transaction 1.\n"
    assert category_of_transaction() == "Dog Food"
