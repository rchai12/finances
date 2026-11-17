from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
from inspect import signature
from unittest.mock import Mock

import anyio
import pytest
from fastapi.testclient import TestClient
from mcp.client import Client
from sqlalchemy.orm import Session

from finances.analysis import listings
from finances.config import get_settings
from finances.db.engine import session_scope
from finances.db.repositories import (
    create_account,
    create_person,
    set_account_active,
    set_account_owner,
)
from finances.mcp_server import tools
from finances.mcp_server.server import build_server
from finances.views.accounts import AccountRow, account_rows
from finances.web.app import create_app
from tests.integration.test_mcp_accounts import call
from tests.support import WEB_PORT, page, run, table_rows


@pytest.fixture
def configured(db_engine, tmp_settings, monkeypatch):
    monkeypatch.setenv("FIN_DATABASE_URL", str(db_engine.url))
    get_settings.cache_clear()
    yield db_engine
    get_settings.cache_clear()


@pytest.fixture
def household(configured):
    with session_scope(configured) as session:
        person = create_person(session, "Alex Synthetic")
        accounts = {}
        for name in ("Zulu Sole", "delta Closed", "Bravo Joint", "alpha Unassigned"):
            accounts[name] = create_account(session, name, "Synthetic Bank", "checking")
        set_account_owner(session, accounts["Zulu Sole"].id, person.id)
        set_account_owner(session, accounts["Bravo Joint"].id, None)
        set_account_active(session, accounts["delta Closed"].id, False)
        accounts["delta Closed"] = replace(accounts["delta Closed"], is_active=False)
    return configured, accounts


def expected_json(include_closed):
    names = ["alpha Unassigned", "Bravo Joint"]
    if include_closed:
        names.append("delta Closed")
    names.append("Zulu Sole")
    return {
        "accounts": [
            dict(
                name=name,
                institution="Synthetic Bank",
                type="checking",
                currency="USD",
                last4=None,
                active=name != "delta Closed",
                owner="Alex Synthetic" if name == "Zulu Sole" else None,
                joint=name == "Bravo Joint",
            )
            for name in names
        ]
    }


@pytest.mark.parametrize("closed", [False, True])
def test_real_analysis_and_views_preserve_all_ownership_forms(household, closed):
    engine, accounts = household
    names = [row["name"] for row in expected_json(closed)["accounts"]]
    with Session(engine) as session:
        actual = listings.account_listing(session, include_inactive=closed)
    expected = [
        listings.AccountListing(
            accounts[name],
            "Joint" if name == "Bravo Joint" else "Alex Synthetic" if name == "Zulu Sole" else None,
            name == "Bravo Joint",
        )
        for name in names
    ]
    assert actual == expected
    assert account_rows(actual) == [
        AccountRow(
            name,
            "Synthetic Bank",
            "checking",
            "",
            "no" if name == "delta Closed" else "yes",
            "Joint" if name == "Bravo Joint" else "Alex Synthetic" if name == "Zulu Sole" else "",
        )
        for name in names
    ]
    with pytest.raises(FrozenInstanceError):
        actual[0].joint = True


@pytest.mark.parametrize("arguments", [{}, {"include_inactive": False}, {"include_inactive": True}])
def test_public_mcp_complete_json_and_order(household, arguments):
    result = call(build_server(), "list_accounts", arguments)
    assert result.is_error is False
    assert result.structured_content == expected_json(arguments.get("include_inactive", False))


def test_empty_public_mcp(configured):
    result = call(build_server(), "list_accounts")
    assert not result.is_error
    assert result.structured_content == {"accounts": []}


@pytest.mark.parametrize("closed", [False, True])
def test_cli_and_web_columns_and_owners_stay_unchanged(household, closed):
    args = ["accounts", "list", *(["--all"] if closed else [])]
    result = run(*args)
    assert result.exit_code == 0
    expected = [
        [
            r["name"],
            "Synthetic Bank",
            "checking",
            "",
            "yes" if r["active"] else "no",
            "Joint" if r["joint"] else r["owner"] or "",
        ]
        for r in expected_json(closed)["accounts"]
    ]
    headers = ["Name", "Institution", "Type", "Last 4", "Active", "Owner"]
    assert table_rows(result.stdout) == [headers, *expected]
    with TestClient(create_app(WEB_PORT), base_url=f"http://127.0.0.1:{WEB_PORT}") as client:
        found = page(client, "/accounts?closed=true" if closed else "/accounts")
    assert found.rows == [headers, *expected]


def test_predecessor_signature_and_tool_metadata():
    assert (
        str(signature(tools.list_accounts))
        == "(include_inactive: bool = False) -> dict[str, typing.Any]"
    )

    async def go():
        async with Client(build_server()) as client:
            return next(t for t in (await client.list_tools()).tools if t.name == "list_accounts")

    tool = anyio.run(go)
    assert tool.name == "list_accounts"
    assert tool.description == (
        "List the household's accounts: name, institution, type, currency, last 4 digits, "
        "whether open, and owner (a person's name, or joint). Closed accounts only when "
        "include_inactive is true. No amounts."
    )
    assert tool.input_schema == {
        "type": "object",
        "properties": {
            "include_inactive": {"default": False, "title": "Include Inactive", "type": "boolean"}
        },
        "title": "list_accountsArguments",
    }
    assert tool.output_schema == {
        "additionalProperties": True,
        "title": "list_accountsDictOutput",
        "type": "object",
    }
    assert tool.annotations.model_dump(
        include={"read_only_hint", "destructive_hint", "idempotent_hint", "open_world_hint"}
    ) == {
        "read_only_hint": True,
        "destructive_hint": False,
        "idempotent_hint": True,
        "open_world_hint": False,
    }


def test_adapter_enters_reading_and_forwards_same_session(monkeypatch):
    session = Mock()
    events = []

    @contextmanager
    def reading():
        events.append("enter")
        yield session
        events.append("exit")

    def load(s, *, include_inactive):
        assert events == ["enter"] and s is session and include_inactive is False
        return []

    loader = Mock(side_effect=load)
    monkeypatch.setattr(tools, "reading", reading)
    monkeypatch.setattr(tools, "account_listing", loader)
    assert tools.list_accounts() == {"accounts": []}
    loader.assert_called_once_with(session, include_inactive=False)
    assert events == ["enter", "exit"] and session.mock_calls == []


@pytest.mark.parametrize("inactive_only", [False, True])
def test_empty_and_inactive_only_load_once_without_cardholder_aliases(monkeypatch, inactive_only):
    from tests.unit.test_account_listing_ownership import CARD

    session = Mock()
    closed = replace(CARD, is_active=False)
    accounts = Mock(return_value=[closed] if inactive_only else [])
    owners = Mock(return_value={})
    people = Mock(return_value=[])
    aliases = Mock(side_effect=AssertionError("account listing must not load aliases"))
    monkeypatch.setattr(listings, "list_accounts", accounts)
    monkeypatch.setattr(listings, "list_account_owners", owners)
    monkeypatch.setattr(listings, "list_people", people)
    monkeypatch.setattr(listings, "list_cardholder_aliases", aliases)
    actual = listings.account_listing(session, include_inactive=True)
    assert actual == ([listings.AccountListing(closed, None, False)] if inactive_only else [])
    accounts.assert_called_once_with(session, include_inactive=True)
    owners.assert_called_once_with(session)
    people.assert_called_once_with(session)
    aliases.assert_not_called()
    assert session.mock_calls == []
