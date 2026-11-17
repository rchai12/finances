import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from finances.mcp_server import tools


@pytest.mark.parametrize(
    "area,name",
    [
        ("accounts", "list_accounts"),
        ("accounts", "get_balances"),
        ("accounts", "get_net_worth"),
        ("queues", "list_transactions"),
        ("queues", "list_uncategorized"),
        ("queues", "list_categories"),
        ("queues", "list_rules"),
        ("queues", "list_transfers"),
        ("queues", "list_transfer_suggestions"),
        ("queues", "data_coverage"),
        ("queues", "find_merchants"),
    ],
)
def test_facade_identity(area, name):
    import importlib

    module = importlib.import_module("finances.mcp_server." + area)
    assert getattr(tools, name) is getattr(module, name)
    assert getattr(tools, name).__module__ == module.__name__


def test_all_mcp_sources_fit():
    folder = Path(tools.__file__).parent
    paths = list(folder.rglob("*.py"))
    assert paths
    assert not [
        (str(p.relative_to(folder)), len(p.read_text().splitlines()))
        for p in paths
        if len(p.read_text().splitlines()) > 400
    ]


def test_facade_contains_only_docstring_and_imports():
    tree = ast.parse(Path(tools.__file__).read_text())
    assert tree.body
    assert all(
        isinstance(n, (ast.Import, ast.ImportFrom))
        or (
            i == 0
            and isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)
        )
        for i, n in enumerate(tree.body)
    )


def test_transfer_order_and_limit(monkeypatch):
    from finances.mcp_server import queues

    session = Mock()
    pairs = [
        SimpleNamespace(
            id=i, status="confirmed", out_transaction_id=i * 2, in_transaction_id=i * 2 + 1
        )
        for i in [1, 3, 2]
    ]
    monkeypatch.setattr(queues, "reading", lambda: nullcontext(session))
    monkeypatch.setattr(queues, "account_names", Mock(return_value={}))
    monkeypatch.setattr(queues, "list_transfer_pairs", Mock(return_value=pairs))
    named = Mock(side_effect=lambda s, i, names: {"id": i})
    monkeypatch.setattr(queues.serialization, "named", named)
    assert tools.list_transfers(2) == {
        "total": 3,
        "pairs": [
            {"pair": 3, "status": "confirmed", "out": {"id": 6}, "in": {"id": 7}},
            {"pair": 2, "status": "confirmed", "out": {"id": 4}, "in": {"id": 5}},
        ],
    }
    assert [c.args[1] for c in named.call_args_list] == [6, 7, 4, 5]
    assert session.mock_calls == []
