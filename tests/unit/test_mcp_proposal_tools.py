from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from finances.mcp_server import tools


@pytest.mark.parametrize(
    "name",
    [
        "propose_category",
        "propose_transfer",
        "propose_not_transfer",
        "propose_rule",
        "propose_merchant_alias",
        "propose_group",
        "propose_new_category",
        "propose_rule_change",
        "propose_category_change",
        "propose_finding_status",
        "list_proposals",
        "log_advice",
        "list_advice",
    ],
)
def test_facade_identity(name):
    from finances.mcp_server import proposals

    assert getattr(tools, name) is getattr(proposals, name)
    assert getattr(tools, name).__module__ == proposals.__name__


@pytest.mark.parametrize("kind", ["value", "category", "unexpected"])
def test_error_translation(kind):
    from finances.db.repositories.categories import CategoryExistsError
    from finances.mcp_server import proposals

    errors = {
        "value": ValueError("synthetic refusal"),
        "category": CategoryExistsError("synthetic refusal"),
        "unexpected": LookupError("synthetic refusal"),
    }
    work = Mock(side_effect=errors[kind])
    expected = LookupError if kind == "unexpected" else ToolError
    with pytest.raises(expected, match="^synthetic refusal$") as caught:
        proposals._as_tool(work)
    if kind != "unexpected":
        assert caught.value.__suppress_context__ is True
    work.assert_called_once_with()


def test_advice_json(monkeypatch):
    from finances.mcp_server import proposals

    session = Mock()
    row = SimpleNamespace(
        id=7,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        subject="Synthetic",
        text="Synthetic note",
        dismissed_at=None,
    )
    store = Mock(return_value=row)
    monkeypatch.setattr(proposals, "writing", lambda: nullcontext(session))
    monkeypatch.setattr(proposals, "keep_advice", store)
    assert tools.log_advice("Synthetic note", "Synthetic") == {
        "advice": {
            "id": 7,
            "created_at": "2026-01-02T00:00:00+00:00",
            "subject": "Synthetic",
            "text": "Synthetic note",
            "dismissed_at": None,
        }
    }
    store.assert_called_once_with(session, "Synthetic note", "Synthetic")
    assert session.mock_calls == []
