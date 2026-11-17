import ast
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, call

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from finances.db.repositories.categories import CategoryExistsError
from finances.mcp_server import helpers, proposals, reports, tools


@pytest.fixture
def context(monkeypatch):
    session = Mock()
    events = []

    @contextmanager
    def writing():
        events.append("enter")
        try:
            yield session
        except Exception as error:
            events.append(type(error))
            raise
        else:
            events.append("success")

    monkeypatch.setattr(proposals, "writing", writing)
    monkeypatch.setattr(proposals, "reading", writing)
    return session, events


CASES = [
    (
        "propose_category",
        "store_category_proposal",
        (7, "Coffee", "Reason"),
        {},
        (7, "Coffee", "Reason"),
        {},
    ),
    ("propose_transfer", "store_transfer", (7, 8, "Reason"), {}, (7, 8, "Reason"), {}),
    ("propose_not_transfer", "store_not_transfer", (7, 8, "Reason"), {}, (7, 8, "Reason"), {}),
    (
        "propose_rule",
        "store_rule",
        (7, "ACME", "Coffee", "Reason"),
        {"match": "equals", "priority": -9},
        (7, "ACME", "Coffee", "Reason"),
        {"match": "equals", "priority": -9},
    ),
    ("propose_merchant_alias", "store_alias", (7, "ACME", "Reason"), {}, (7, "ACME", "Reason"), {}),
    (
        "propose_group",
        "store_group",
        ("Synthetic", 7, "Reason"),
        {"kind": "income", "sensitive": True},
        (7, "Synthetic", "Reason"),
        {"kind": "income", "sensitive": True},
    ),
    (
        "propose_new_category",
        "store_new_category",
        ("Synthetic", "Food", 7, "Reason"),
        {"tax": True},
        (7, "Synthetic", "Food", "Reason"),
        {"tax": True},
    ),
    (
        "propose_rule_change",
        "store_rule_change",
        (7, "Reason"),
        {"delete": True, "pattern": "ACME", "match": "equals", "priority": 9, "category": "Coffee"},
        (7, "Reason"),
        {"delete": True, "pattern": "ACME", "match": "equals", "priority": 9, "category": "Coffee"},
    ),
    (
        "propose_category_change",
        "store_category_change",
        ("Coffee", "Reason"),
        {"rename_to": "Synthetic", "delete": True, "move_to": "Food"},
        ("Coffee", "Reason"),
        {"rename_to": "Synthetic", "delete": True, "move_to": "Food"},
    ),
    (
        "propose_finding_status",
        "store_finding_status",
        ("fee", "handled", "Reason"),
        {"about": "Synthetic", "month": "2026-02"},
        ("finding", "handled", "Reason"),
        {},
    ),
]


@pytest.mark.parametrize("name,seam,args,kwargs,passed,options", CASES)
def test_adapter_arguments_and_context(
    monkeypatch, context, name, seam, args, kwargs, passed, options
):
    session, events = context
    row = object()
    marker = {"synthetic": name}
    repository = Mock(return_value=row)
    serialize = Mock(return_value=marker)
    monkeypatch.setattr(proposals, seam, repository)
    monkeypatch.setattr(proposals.serialization, "proposal_item", serialize)
    lookup = Mock(return_value="finding")
    monkeypatch.setattr(proposals, "find_finding", lookup)
    assert getattr(tools, name)(*args, **kwargs) == {"proposal": marker}
    repository.assert_called_once_with(session, *passed, **options)
    serialize.assert_called_once_with(session, row)
    assert events == ["enter", "success"] and session.mock_calls == []
    if name == "propose_finding_status":
        lookup.assert_called_once_with(session, date(2026, 2, 1), "fee", "Synthetic")


@pytest.mark.parametrize(
    "error", [ValueError("synthetic"), CategoryExistsError("synthetic"), LookupError("synthetic")]
)
def test_error_exits_context_before_translation(monkeypatch, context, error):
    session, events = context
    monkeypatch.setattr(proposals, "store_category_proposal", Mock(side_effect=error))
    expected = LookupError if type(error) is LookupError else ToolError
    with pytest.raises(expected, match="^synthetic$") as caught:
        tools.propose_category(7, "Coffee", "Reason")
    assert events == ["enter", type(error)]
    assert session.mock_calls == []
    if expected is LookupError:
        assert caught.value is error
    else:
        assert caught.value.__suppress_context__ is True


@pytest.mark.parametrize("status", ["accepted", "declined"])
def test_read_lists_order_and_limits(monkeypatch, context, status):
    session, events = context
    monkeypatch.setattr(proposals, "writing", Mock(side_effect=AssertionError("write entered")))
    rows = [object(), object()]
    load = Mock(return_value=rows)
    monkeypatch.setattr(proposals, "load_proposals", load)
    serialize = Mock(side_effect=[{"id": 2}, {"id": 1}])
    monkeypatch.setattr(proposals.serialization, "proposal_item", serialize)
    assert tools.list_proposals(status, 3) == {"proposals": [{"id": 2}, {"id": 1}]}
    load.assert_called_once_with(session, status=status, limit=3)
    assert serialize.call_args_list == [call(session, row) for row in rows]
    dt = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)
    load_advice = Mock(
        return_value=[
            NS(id=2, created_at=dt, subject="", text="Synthetic", dismissed_at=None),
            NS(id=1, created_at=dt, subject="Synthetic", text="Note", dismissed_at=dt),
        ]
    )
    monkeypatch.setattr(proposals, "load_advice", load_advice)
    assert tools.list_advice(3) == {
        "advice": [
            {
                "id": 2,
                "created_at": "2026-01-02T03:04:05.123456+00:00",
                "subject": "",
                "text": "Synthetic",
                "dismissed_at": None,
            },
            {
                "id": 1,
                "created_at": "2026-01-02T03:04:05.123456+00:00",
                "subject": "Synthetic",
                "text": "Note",
                "dismissed_at": "2026-01-02T03:04:05.123456+00:00",
            },
        ]
    }
    load_advice.assert_called_once_with(session, limit=3)
    assert events == ["enter", "success", "enter", "success"] and session.mock_calls == []


@pytest.mark.parametrize("subject", [None, "Synthetic"])
def test_advice_default_and_explicit_subject(monkeypatch, context, subject):
    session, events = context
    dt = datetime(2026, 1, 2, tzinfo=UTC)
    repo = Mock(
        return_value=NS(id=1, created_at=dt, subject=subject or "", text="Note", dismissed_at=None)
    )
    monkeypatch.setattr(proposals, "keep_advice", repo)
    result = tools.log_advice("Note", *(() if subject is None else (subject,)))
    assert result == {
        "advice": {
            "id": 1,
            "created_at": "2026-01-02T00:00:00+00:00",
            "subject": subject or "",
            "text": "Note",
            "dismissed_at": None,
        }
    }
    repo.assert_called_once_with(session, "Note", subject or "")
    assert events == ["enter", "success"] and session.mock_calls == []


def test_month_helper_clock_errors_and_aliases(monkeypatch):
    clock = Mock(return_value=date(2026, 1, 15))
    monkeypatch.setattr(helpers.clock, "today", clock)
    assert helpers.month_start("2026-02") == date(2026, 2, 1)
    clock.assert_not_called()
    assert helpers.month_start("") == date(2026, 1, 1)
    clock.assert_called_once_with()
    with pytest.raises(ToolError, match="^month must be a year and month, like 2026-05$"):
        helpers.month_start("2026-13")
    assert clock.call_count == 1
    assert reports._month_start is proposals._month_start is helpers.month_start


@pytest.mark.parametrize("error", [ValueError("finding not found"), LookupError("synthetic")])
def test_finding_failure_aborts_store(monkeypatch, context, error):
    session, events = context
    store = Mock()
    monkeypatch.setattr(proposals, "store_finding_status", store)

    def lookup(*args):
        assert events == ["enter"]
        assert args == (session, date(2026, 2, 1), "fee", "Synthetic")
        raise error

    monkeypatch.setattr(proposals, "find_finding", lookup)
    with pytest.raises(ToolError if isinstance(error, ValueError) else LookupError):
        tools.propose_finding_status("fee", "handled", "Reason", about="Synthetic", month="2026-02")
    store.assert_not_called()
    assert session.mock_calls == []
    assert events == ["enter", type(error)]


def test_structure_and_size():
    for module, limit in [(tools, 716), (proposals, 400), (helpers, 400)]:
        source = Path(module.__file__).read_text()
        assert len(source.splitlines()) <= limit
        if module is tools:
            continue
        tree = ast.parse(source)
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert all(not name or not name.endswith((".tools", ".server")) for name in imports)
        assert not any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in {"__import__", "eval", "exec"}
            for n in ast.walk(tree)
        )
    tree = ast.parse(Path(helpers.__file__).read_text())
    assert {n.module for n in tree.body if isinstance(n, ast.ImportFrom)} == {
        "datetime",
        "mcp.server.mcpserver.exceptions",
        "finances.domain",
    }
