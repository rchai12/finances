from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from finances.analysis import listings
from finances.analysis.people import Attribution
from finances.domain.models import Account, AccountType
from finances.mcp_server import accounts, tools

CARD = Account(
    1,
    "Synthetic Card",
    "Synthetic Bank",
    AccountType.CHECKING,
    "USD",
    None,
    True,
    datetime(2026, 1, 1, tzinfo=UTC),
)


@pytest.mark.parametrize(
    ("owners", "people", "display", "joint"),
    [
        ({}, [], None, False),
        ({1: 7}, [SimpleNamespace(id=7, name="Synthetic Person")], "Synthetic Person", False),
        ({1: None}, [], "Joint", True),
        ({1: 7}, [SimpleNamespace(id=7, name="Joint")], "Joint", False),
    ],
    ids=["unassigned", "sole", "joint", "name-collision"],
)
def test_analysis_keeps_display_and_joint_distinct(monkeypatch, owners, people, display, joint):
    session = Mock()
    accounts = Mock(return_value=[CARD])
    owner_loader = Mock(return_value=owners)
    people_loader = Mock(return_value=people)
    monkeypatch.setattr(listings, "list_accounts", accounts)
    monkeypatch.setattr(listings, "list_account_owners", owner_loader)
    monkeypatch.setattr(listings, "list_people", people_loader)
    # Predecessor seam: let its lossy display-only path run without a real DB.
    monkeypatch.setattr(
        listings,
        "load_attribution",
        lambda s: Attribution(owners={} if display is None else {1: display}, aliases={}),
        raising=False,
    )
    found = listings.account_listing(session, include_inactive=True)
    assert len(found) == 1
    assert found[0].account is CARD
    assert found[0].owner == display
    assert found[0].joint is joint
    accounts.assert_called_once_with(session, include_inactive=True)
    owner_loader.assert_called_once_with(session)
    people_loader.assert_called_once_with(session)
    assert session.mock_calls == []


def test_existing_two_argument_listing_defaults_to_nonjoint():
    assert listings.AccountListing(CARD, "Joint").joint is False


@pytest.mark.parametrize("include_inactive", [False, True], ids=["active", "all"])
def test_mcp_serializes_shared_listing_only(monkeypatch, include_inactive):
    session = Mock()
    monkeypatch.setattr(accounts, "reading", lambda: nullcontext(session))
    rows = [
        SimpleNamespace(account=CARD, owner=owner, joint=joint)
        for owner, joint in [
            (None, False),
            ("Synthetic Person", False),
            ("Joint", True),
            ("Joint", False),
        ]
    ]
    loader = Mock(return_value=rows)
    monkeypatch.setattr(accounts, "account_listing", loader, raising=False)
    direct = []
    for name in ("list_people", "list_account_owners", "load_accounts"):
        spy = Mock(return_value=[])
        monkeypatch.setattr(accounts, name, spy, raising=False)
        direct.append(spy)
    assert tools.list_accounts(include_inactive) == {
        "accounts": [
            {
                "name": "Synthetic Card",
                "institution": "Synthetic Bank",
                "type": "checking",
                "currency": "USD",
                "last4": None,
                "active": True,
                "owner": None,
                "joint": False,
            },
            {
                "name": "Synthetic Card",
                "institution": "Synthetic Bank",
                "type": "checking",
                "currency": "USD",
                "last4": None,
                "active": True,
                "owner": "Synthetic Person",
                "joint": False,
            },
            {
                "name": "Synthetic Card",
                "institution": "Synthetic Bank",
                "type": "checking",
                "currency": "USD",
                "last4": None,
                "active": True,
                "owner": None,
                "joint": True,
            },
            {
                "name": "Synthetic Card",
                "institution": "Synthetic Bank",
                "type": "checking",
                "currency": "USD",
                "last4": None,
                "active": True,
                "owner": "Joint",
                "joint": False,
            },
        ]
    }
    loader.assert_called_once_with(session, include_inactive=include_inactive)
    for spy in direct:
        spy.assert_not_called()
    assert session.mock_calls == []
