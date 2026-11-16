import ast
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from finances.db import time as db_time
from finances.db.engine import session_scope
from finances.db.orm import TransactionRow
from finances.db.repositories import (
    accept_proposal,
    category_changes,
    create_account,
    create_rule,
    decline_proposal,
    dismiss_advice,
    finding_proposals,
    list_advice,
    list_changes,
    list_finding_statuses,
    list_proposals,
    log_advice,
    new_categories,
    proposals,
    rule_changes,
    set_finding_status,
    transfers,
)
from finances.domain.insights import Finding

T1 = datetime(2026, 1, 2, 3, 4, 1, 123456, tzinfo=UTC)
T2 = datetime(2026, 1, 2, 3, 4, 2, 234567, tzinfo=UTC)
T3 = datetime(2026, 1, 2, 3, 4, 3, 345678, tzinfo=UTC)
T4 = datetime(2026, 1, 2, 3, 4, 4, 456789, tzinfo=UTC)
FINDING = Finding("spike", "low", date(2026, 1, 1), "Groceries", 900, "Synthetic finding")
CREATIONS = [
    (proposals.propose_category, proposals, (1, "Dining"), {}, "category"),
    (proposals.propose_transfer, transfers, (1, 2), {}, "transfer"),
    (proposals.propose_not_transfer, transfers, (1, 2), {}, "not_transfer"),
    (proposals.propose_rule, proposals, (1, "COFFEE", "Dining"), {}, "rule"),
    (proposals.propose_merchant_alias, proposals, (1, "ACME CAFE"), {}, "alias"),
    (new_categories.propose_group, new_categories, (1, "Synthetic Group"), {}, "group"),
    (
        new_categories.propose_new_category,
        new_categories,
        (1, "Synthetic Leaf", "Food"),
        {},
        "new_category",
    ),
    (rule_changes.propose_rule_change, rule_changes, (1,), {"priority": 7}, "rule_edit"),
    (rule_changes.propose_rule_change, rule_changes, (1,), {"delete": True}, "rule_delete"),
    (
        category_changes.propose_category_change,
        category_changes,
        ("Dining",),
        {"rename_to": "Synthetic Dining"},
        "category_rename",
    ),
    (
        category_changes.propose_category_change,
        category_changes,
        ("Dining",),
        {"delete": True, "move_to": "Groceries"},
        "category_delete",
    ),
    (
        finding_proposals.propose_finding_status,
        finding_proposals,
        (FINDING, "handled"),
        {},
        "finding_status",
    ),
]


@pytest.fixture
def prepared(db_engine):
    with session_scope(db_engine) as session:
        one = create_account(session, "Synthetic Checking", "Synthetic Bank", "checking")
        two = create_account(session, "Synthetic Savings", "Synthetic Bank", "savings")
        for number, account, cents in ((1, one.id, -700), (2, two.id, 700)):
            session.add(
                TransactionRow(
                    account_id=account,
                    posted_date=date(2026, 1, 1),
                    amount_cents=cents,
                    description="ACME COFFEE",
                    source="statement",
                    fingerprint=str(number).ljust(64, "0"),
                )
            )
        session.flush()
        create_rule(session, "ACME", "Dining")
    return db_engine


def strict_clock(monkeypatch, *values):
    clock = Mock(side_effect=list(values))
    monkeypatch.setattr(db_time, "utc_now", clock)
    return clock


@pytest.mark.parametrize("writer,module,args,kwargs,kind", CREATIONS)
@pytest.mark.parametrize("marker", [False, True], ids=["cleaned", "helper-return"])
def test_creation_sites_store_shared_reason_and_timestamp(
    prepared, monkeypatch, writer, module, args, kwargs, kind, marker
):
    raw = " \tSynthetic\n reason\u00a0 here "
    expected = "SHARED HELPER MARKER" if marker else "Synthetic reason here"
    helper = Mock(return_value=expected)
    if marker:
        monkeypatch.setattr(module, "clean_reason", helper)
    clock = Mock(return_value=T1)
    monkeypatch.setattr(db_time, "utc_now", clock)
    with session_scope(prepared) as session:
        item = writer(session, *args, reason=raw, **kwargs)
        assert (item.kind, item.reason, item.created_at) == (kind, expected, T1)
        assert item.created_at.tzinfo is UTC
    if marker:
        helper.assert_called_once_with(raw)
    # Category dry runs retain their own rolled-back audit clock read.
    assert clock.call_count == (2 if module is category_changes else 1)
    with Session(prepared) as session:
        [stored] = list_proposals(session)
        assert (stored.kind, stored.reason, stored.created_at) == (kind, expected, T1)
        assert stored.created_at.tzinfo is UTC


def category_proposal(engine):
    with session_scope(engine) as session:
        return proposals.propose_category(session, 1, "Dining", "Synthetic reason")


def test_category_acceptance_keeps_three_distinct_clock_reads(prepared, monkeypatch):
    item = category_proposal(prepared)
    clock = strict_clock(monkeypatch, T1, T2, T3)
    with session_scope(prepared) as session:
        result = accept_proposal(session, item.id)
        assert result.decided_at == T2 and result.decided_at.tzinfo is UTC
    with Session(prepared) as session:
        [stored] = list_proposals(session)
        assert stored.decided_at == T2 and stored.decided_at.tzinfo is UTC
        events = [
            e for e in list_changes(session) if e.action in ("category_set", "proposal_accepted")
        ]
        assert [(e.action, e.at, e.before, e.after) for e in reversed(events)] == [
            ("category_set", T1, None, "Dining"),
            ("proposal_accepted", T3, None, "transaction 1: Dining"),
        ]
        assert all(e.at.tzinfo is UTC for e in events)
    assert clock.call_count == 3


def test_decline_keeps_two_distinct_clock_reads(prepared, monkeypatch):
    item = category_proposal(prepared)
    clock = strict_clock(monkeypatch, T1, T2)
    with session_scope(prepared) as session:
        result = decline_proposal(session, item.id)
        assert result.decided_at == T1 and result.decided_at.tzinfo is UTC
    with Session(prepared) as session:
        [stored] = list_proposals(session)
        assert (stored.status, stored.decided_at) == ("declined", T1)
        assert stored.decided_at.tzinfo is UTC
        [event] = [e for e in list_changes(session) if e.action == "proposal_declined"]
        assert (event.at, event.before, event.after) == (T2, None, "transaction 1: Dining")
        assert event.at.tzinfo is UTC
    assert clock.call_count == 2


def test_advice_creation_and_dismissal_read_once_each_without_audits(prepared, monkeypatch):
    with Session(prepared) as session:
        before = list_changes(session)
    clock = strict_clock(monkeypatch, T1, T2)
    with session_scope(prepared) as session:
        note = log_advice(session, "Synthetic note", "Synthetic subject")
        assert note.created_at == T1 and note.created_at.tzinfo is UTC
        dismissed = dismiss_advice(session, note.id)
        assert dismissed.dismissed_at == T2 and dismissed.dismissed_at.tzinfo is UTC
        with pytest.raises(ValueError) as stopped:
            dismiss_advice(session, note.id)
        assert str(stopped.value) == f"note {note.id} is already dismissed"
    with Session(prepared) as session:
        [stored] = list_advice(session)
        assert (stored.created_at, stored.dismissed_at) == (T1, T2)
        assert stored.created_at.tzinfo is stored.dismissed_at.tzinfo is UTC
        assert list_changes(session) == before
    assert clock.call_count == 2


def test_direct_finding_status_reads_for_status_then_audit(prepared, monkeypatch):
    clock = strict_clock(monkeypatch, T1, T2)
    with session_scope(prepared) as session:
        status = set_finding_status(session, FINDING, "handled")
        assert status.set_at == T1 and status.set_at.tzinfo is UTC
    with Session(prepared) as session:
        [stored] = list_finding_statuses(session)
        assert stored.set_at == T1 and stored.set_at.tzinfo is UTC
        [event] = [e for e in list_changes(session) if e.action == "finding_handled"]
        assert (event.at, event.before, event.after) == (T2, None, "spike for Groceries in 2026-01")
        assert event.at.tzinfo is UTC
    assert clock.call_count == 2


def test_accept_finding_status_keeps_four_event_times(prepared, monkeypatch):
    with session_scope(prepared) as session:
        item = finding_proposals.propose_finding_status(
            session, FINDING, "handled", "Synthetic reason"
        )
    clock = strict_clock(monkeypatch, T1, T2, T3, T4)
    with session_scope(prepared) as session:
        result = accept_proposal(session, item.id)
        assert result.decided_at == T3 and result.decided_at.tzinfo is UTC
    with Session(prepared) as session:
        [status] = list_finding_statuses(session)
        assert status.set_at == T1 and status.set_at.tzinfo is UTC
        [stored] = list_proposals(session)
        assert stored.decided_at == T3 and stored.decided_at.tzinfo is UTC
        events = [
            e for e in list_changes(session) if e.action in ("finding_handled", "proposal_accepted")
        ]
        assert [(e.action, e.at, e.before, e.after) for e in reversed(events)] == [
            ("finding_handled", T2, None, "spike for Groceries in 2026-01"),
            ("proposal_accepted", T4, None, "finding spike for Groceries in 2026-01: handled"),
        ]
        assert all(e.at.tzinfo is UTC for e in events)
    assert clock.call_count == 4


def test_all_fifteen_repository_clock_sites_use_module_lookup():
    counts = {
        "proposals": 6,
        "transfers": 1,
        "new_categories": 2,
        "rule_changes": 1,
        "category_changes": 1,
        "finding_proposals": 1,
        "audit": 1,
        "advice": 1,
        "findings": 1,
    }
    root = Path(__file__).resolve().parents[2] / "src/finances/db/repositories"
    assert sum(counts.values()) == 15
    for module, expected in counts.items():
        tree = ast.parse((root / f"{module}.py").read_text())
        assert not any(isinstance(n, ast.FunctionDef) and n.name == "_now" for n in ast.walk(tree))
        assert not any(
            isinstance(n, ast.ImportFrom) and any(a.name in ("utc_now", "_now") for a in n.names)
            for n in ast.walk(tree)
        )
        calls = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "utc_now"
        ]
        assert len(calls) == expected, module
        assert all(
            isinstance(n.func.value, ast.Name) and n.func.value.id == "db_time" for n in calls
        )
