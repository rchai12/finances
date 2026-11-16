from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from finances.db import time as db_time
from finances.db.repositories import proposals as repo
from finances.domain import proposals as domain
from finances.domain.models import CONFIRMED

NOW = datetime(2026, 1, 1, tzinfo=UTC)
ACCEPT = {
    domain.CATEGORY: "set_category_by_hand",
    domain.TRANSFER: "create_transfer_pair",
    domain.NOT_TRANSFER: "reject_transfer",
    domain.RULE: "create_rule",
    domain.ALIAS: "add_alias",
    domain.GROUP: "new_categories.accept_new",
    domain.NEW_CATEGORY: "new_categories.accept_new",
    domain.CATEGORY_RENAME: "accept_category_change",
    domain.CATEGORY_DELETE: "accept_category_change",
    domain.RULE_EDIT: "accept_rule_change",
    domain.RULE_DELETE: "accept_rule_change",
    domain.FINDING_STATUS: "finding_proposals.accept_finding_status",
}
STALE = {
    domain.GROUP: "new_categories.new_is_out_of_date",
    domain.NEW_CATEGORY: "new_categories.new_is_out_of_date",
    domain.CATEGORY_RENAME: "category_change_is_out_of_date",
    domain.CATEGORY_DELETE: "category_change_is_out_of_date",
    domain.FINDING_STATUS: "finding_proposals.finding_status_is_out_of_date",
    domain.RULE_EDIT: "rule_change_is_out_of_date",
    domain.RULE_DELETE: "rule_change_is_out_of_date",
    domain.CATEGORY: "category_is_out_of_date",
    domain.TRANSFER: "pair_is_out_of_date",
    domain.NOT_TRANSFER: "pair_is_out_of_date",
    domain.RULE: None,
    domain.ALIAS: None,
}


def proposal(kind):
    return domain.Proposal(
        17,
        kind,
        23,
        "Synthetic category",
        "Synthetic reason",
        domain.OPEN,
        NOW,
        None,
        other_id=24,
        pattern="ACME",
        match="contains",
        priority=3,
        source="ACME COFFEE",
    )


def patches(monkeypatch, names):
    found = {}
    for name in set(names):
        if name is None:
            continue
        module, _, attr = name.rpartition(".")
        target = f"finances.db.repositories.{module or 'proposals'}.{attr}"
        mock = Mock()
        monkeypatch.setattr(target, mock)
        found[name] = mock
    return found


def test_matrix_inventory_is_complete():
    assert set(ACCEPT) == set(STALE) == set(domain.KINDS)
    assert len(ACCEPT) == 12


@pytest.mark.parametrize("kind", ACCEPT)
def test_acceptance_dispatches_exactly_one_handler(monkeypatch, kind):
    original = proposal(kind)
    row = SimpleNamespace(**vars(original))
    session = Mock()
    writers = patches(monkeypatch, ACCEPT.values())
    waiting = Mock(return_value=None)
    stale = Mock(return_value=False)
    monkeypatch.setattr(repo, "_open_row", lambda s, n: row)
    monkeypatch.setattr(repo, "to_proposal", lambda r: domain.Proposal(**vars(r)))
    monkeypatch.setattr(repo, "waits_for", waiting)
    monkeypatch.setattr(repo, "proposal_out_of_date", stale)
    monkeypatch.setattr(db_time, "utc_now", lambda: NOW)
    audit = Mock()
    monkeypatch.setattr(repo, "record_change", audit)
    order = Mock()
    order.attach_mock(waiting, "waiting")
    order.attach_mock(stale, "stale")
    result = repo.accept_proposal(session, 17)
    assert order.mock_calls == [call.waiting(session, original), call.stale(session, original)]
    arguments = {
        domain.CATEGORY: (session, 23, "Synthetic category"),
        domain.TRANSFER: (session, 23, 24, CONFIRMED),
        domain.NOT_TRANSFER: (session, 23, 24),
        domain.RULE: (session, "ACME", "Synthetic category", "contains", 3),
        domain.ALIAS: (session, "ACME COFFEE", "Synthetic category"),
    }
    for name, writer in writers.items():
        if name == ACCEPT[kind]:
            writer.assert_called_once_with(*arguments.get(kind, (session, row)))
        else:
            writer.assert_not_called()
    assert result == replace(original, status=domain.ACCEPTED, decided_at=NOW)
    assert row.status == domain.ACCEPTED and row.decided_at == NOW
    assert session.mock_calls == [call.flush()]
    audit.assert_called_once_with(
        session,
        action="proposal_accepted",
        kind="proposal",
        record_id=17,
        after=domain.proposal_text(result),
    )


@pytest.mark.parametrize("kind", [k for k, v in STALE.items() if v is not None])
@pytest.mark.parametrize("result", [False, True])
def test_staleness_delegates_without_writes(monkeypatch, kind, result):
    delegates = patches(monkeypatch, STALE.values())
    other = patches(
        monkeypatch,
        [
            "_category_row",
            "_rule_exists",
            "check_alias",
            "alias_map",
            "chain_out_of_date",
            *ACCEPT.values(),
            "record_change",
        ],
    )
    delegates[STALE[kind]].return_value = result
    session = Mock()
    item = proposal(kind)
    assert repo.proposal_out_of_date(session, item) is result
    for name, delegate in delegates.items():
        if name == STALE[kind]:
            delegate.assert_called_once_with(session, item)
        else:
            delegate.assert_not_called()
    assert session.mock_calls == []
    assert all(not mock.mock_calls for mock in other.values())


@pytest.mark.parametrize(
    "exists,parent,existing_rule,chain_result,expected",
    [
        (True, 1, True, False, True),
        (False, None, False, True, True),
        (True, None, False, True, True),
        (True, 1, False, False, False),
        (True, 1, False, True, True),
    ],
)
def test_rule_staleness_preserves_category_and_dependency_checks(
    monkeypatch, exists, parent, existing_rule, chain_result, expected
):
    mocks = patches(
        monkeypatch,
        [
            *STALE.values(),
            *ACCEPT.values(),
            "record_change",
            "_category_row",
            "_rule_exists",
            "chain_out_of_date",
            "check_alias",
            "alias_map",
        ],
    )
    mocks["_category_row"].return_value = SimpleNamespace(parent_id=parent) if exists else None
    mocks["_rule_exists"].return_value = existing_rule
    mocks["chain_out_of_date"].return_value = chain_result
    session = Mock()
    item = proposal(domain.RULE)
    assert repo.proposal_out_of_date(session, item) is expected
    mocks["_category_row"].assert_called_once_with(session, item.value)
    mocks["_rule_exists"].assert_called_once_with(session, "contains", "ACME")
    if existing_rule:
        mocks["chain_out_of_date"].assert_not_called()
    else:
        mocks["chain_out_of_date"].assert_called_once_with(
            session, item, target_missing=not exists or parent is None
        )
    for name, mock in mocks.items():
        if name not in ("_category_row", "_rule_exists", "chain_out_of_date"):
            mock.assert_not_called()
    assert session.mock_calls == []


@pytest.mark.parametrize("invalid", [False, True])
def test_alias_staleness_preserves_validation(monkeypatch, invalid):
    mocks = patches(
        monkeypatch,
        [
            *STALE.values(),
            *ACCEPT.values(),
            "record_change",
            "_category_row",
            "_rule_exists",
            "chain_out_of_date",
            "check_alias",
            "alias_map",
        ],
    )
    mapping = {"ACME": "FOOBAR"}
    mocks["alias_map"].return_value = mapping
    if invalid:
        mocks["check_alias"].side_effect = ValueError("synthetic invalid alias")
    session = Mock()
    item = proposal(domain.ALIAS)
    assert repo.proposal_out_of_date(session, item) is invalid
    mocks["alias_map"].assert_called_once_with(session)
    mocks["check_alias"].assert_called_once_with(item.source, item.value, mapping)
    for name, mock in mocks.items():
        if name not in ("check_alias", "alias_map"):
            mock.assert_not_called()
    assert session.mock_calls == []


def test_unknown_domain_proposal_refuses_without_queries():
    session = Mock()
    with pytest.raises(ValueError, match="^unsupported proposal kind$"):
        repo.proposal_out_of_date(session, proposal("private_unknown"))
    assert session.mock_calls == []


def test_unknown_acceptance_refuses_before_dependency(monkeypatch):
    row = SimpleNamespace(**vars(proposal("private_unknown")))
    monkeypatch.setattr(repo, "_open_row", lambda s, n: row)
    waiting = Mock(return_value=99)
    monkeypatch.setattr(repo, "waits_for", waiting)
    session = Mock()
    with pytest.raises(ValueError, match="^unsupported proposal kind$"):
        repo.accept_proposal(session, row.id)
    waiting.assert_not_called()
    assert row.status == domain.OPEN and row.decided_at is None
    assert session.mock_calls == []
