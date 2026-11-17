from datetime import UTC, date, datetime
from importlib import import_module
from unittest.mock import Mock

import pytest

from finances.domain.proposals import KINDS, Proposal


def proposal(kind):
    return Proposal(
        id=11,
        kind=kind,
        target_id=7,
        other_id=8,
        value="handled" if kind == "finding_status" else "Synthetic value",
        reason="Synthetic reason",
        status="open",
        created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        decided_at=None,
        pattern="ACME",
        match="contains",
        priority=5,
        source="ACME SOURCE",
        group="Synthetic group",
        transfer=True,
        income=False,
        sensitive=True,
        tax=True,
        before="Synthetic before",
        finding_type="fee",
        finding_subject="Synthetic subject",
        finding_month=date(2026, 1, 1),
    )


CASES = [
    (
        "category",
        {
            "id": 11,
            "kind": "category",
            "transaction_id": 7,
            "in_id": 8,
            "category": "Synthetic value",
            "rule": None,
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "transfer",
        {
            "id": 11,
            "kind": "transfer",
            "transaction_id": 7,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "not_transfer",
        {
            "id": 11,
            "kind": "not_transfer",
            "transaction_id": 7,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "rule",
        {
            "id": 11,
            "kind": "rule",
            "transaction_id": 7,
            "in_id": 8,
            "category": "Synthetic value",
            "rule": {"match": "contains", "pattern": "ACME", "priority": 5},
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "alias",
        {
            "id": 11,
            "kind": "alias",
            "transaction_id": 7,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": {"source": "ACME SOURCE", "target": "Synthetic value"},
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "group",
        {
            "id": 11,
            "kind": "group",
            "transaction_id": 7,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": None,
            "new": {
                "name": "Synthetic value",
                "group": None,
                "kind": "transfer",
                "sensitive": True,
                "tax": None,
            },
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "new_category",
        {
            "id": 11,
            "kind": "new_category",
            "transaction_id": 7,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": None,
            "new": {
                "name": "Synthetic value",
                "group": "Synthetic group",
                "kind": None,
                "sensitive": None,
                "tax": True,
            },
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "rule_edit",
        {
            "id": 11,
            "kind": "rule_edit",
            "transaction_id": None,
            "in_id": 8,
            "category": "Synthetic value",
            "rule": {"match": "contains", "pattern": "ACME", "priority": 5},
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": {"rule_id": 7, "before": "Synthetic before", "delete": False},
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "rule_delete",
        {
            "id": 11,
            "kind": "rule_delete",
            "transaction_id": None,
            "in_id": 8,
            "category": "Synthetic value",
            "rule": {"match": "contains", "pattern": "ACME", "priority": 5},
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": {"rule_id": 7, "before": "Synthetic before", "delete": True},
            "finding": None,
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "category_rename",
        {
            "id": 11,
            "kind": "category_rename",
            "transaction_id": None,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": {
                "name": "Synthetic before",
                "rename_to": "Synthetic value",
                "delete": False,
                "move_to": None,
            },
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "category_delete",
        {
            "id": 11,
            "kind": "category_delete",
            "transaction_id": None,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": None,
            "category_change": {
                "name": "Synthetic before",
                "rename_to": None,
                "delete": True,
                "move_to": "Synthetic value",
            },
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
    (
        "finding_status",
        {
            "id": 11,
            "kind": "finding_status",
            "transaction_id": None,
            "in_id": 8,
            "category": None,
            "rule": None,
            "alias": None,
            "new": None,
            "waits_for": None,
            "rule_change": None,
            "finding": {
                "type": "fee",
                "about": "Synthetic subject",
                "month": "2026-01",
                "status": "handled",
            },
            "category_change": None,
            "reason": "Synthetic reason",
            "status": "open",
            "created_at": "2026-01-02T03:04:05+00:00",
            "decided_at": None,
            "out_of_date": False,
        },
    ),
]


@pytest.mark.parametrize(("kind", "expected"), CASES, ids=[case[0] for case in CASES])
def test_proposal_json_is_preserved(monkeypatch, kind, expected):
    module = import_module("finances.mcp_server.serialization")
    session = Mock()
    item = proposal(kind)
    waiting = Mock(return_value=None)
    stale = Mock(return_value=False)
    monkeypatch.setattr(module, "waits_for", waiting)
    monkeypatch.setattr(module, "proposal_out_of_date", stale)
    assert module.proposal_item(session, item) == expected
    waiting.assert_called_once_with(session, item)
    stale.assert_called_once_with(session, item)
    assert session.mock_calls == []


def test_all_kinds_are_represented():
    assert tuple(kind for kind, _ in CASES) == KINDS


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (date(2026, 1, 2), "2026-01-02"),
        (datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC), "2026-01-02T03:04:05+00:00"),
    ],
    ids=["none", "date", "timestamp"],
)
def test_iso_preserves_value(value, expected):
    module = import_module("finances.mcp_server.serialization")
    assert module.iso(value) == expected
