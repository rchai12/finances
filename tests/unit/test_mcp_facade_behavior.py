import ast
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, call

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from finances.mcp_server import accounts, queues, reports, tools

DAY = date(2026, 2, 15)


@pytest.fixture
def context(monkeypatch):
    session = Mock()
    events = []

    @contextmanager
    def reading():
        events.append("enter")
        try:
            yield session
        except Exception as error:
            events.append(type(error))
            raise
        else:
            events.append("success")

    monkeypatch.setattr(accounts, "reading", reading)
    monkeypatch.setattr(queues, "reading", reading)
    clock = Mock(return_value=DAY)
    monkeypatch.setattr(accounts.clock, "today", clock)
    return session, events, clock


def test_balances_and_net_worth(monkeypatch, context):
    session, events, clock = context
    load = Mock(
        return_value=NS(
            lines=[
                NS(
                    account="Test Card",
                    type="credit_card",
                    balance_cents=-300,
                    as_of=DAY,
                    source="statement",
                ),
                NS(
                    account="Test Savings", type="savings", balance_cents=0, as_of=None, source=None
                ),
            ],
            cash_cents=0,
            cards_cents=-300,
            other_cents=0,
            net_worth_cents=-300,
            without_balance=["Test Savings"],
        )
    )
    monkeypatch.setattr(accounts, "balance_report", load)
    assert tools.get_balances() == {
        "accounts": [
            {
                "name": "Test Card",
                "type": "credit_card",
                "balance_cents": -300,
                "as_of": "2026-02-15",
                "source": "statement",
            },
            {
                "name": "Test Savings",
                "type": "savings",
                "balance_cents": 0,
                "as_of": None,
                "source": None,
            },
        ],
        "cash_cents": 0,
        "cards_cents": -300,
        "other_cents": 0,
        "net_worth_cents": -300,
        "without_balance": ["Test Savings"],
    }
    load.assert_called_once_with(session)
    worth = Mock(
        return_value=[
            NS(day=date(2026, 1, 31), net_worth_cents=-100, accounts=1),
            NS(day=DAY, net_worth_cents=-300, accounts=2),
        ]
    )
    monkeypatch.setattr(accounts, "net_worth_over_time", worth)
    assert tools.get_net_worth(3) == {
        "as_of": "2026-02-15",
        "points": [
            {"day": "2026-01-31", "net_worth_cents": -100, "accounts": 1},
            {"day": "2026-02-15", "net_worth_cents": -300, "accounts": 2},
        ],
    }
    worth.assert_called_once_with(session, DAY, 3)
    clock.assert_called_once_with()
    assert events == ["enter", "success"] * 2 and session.mock_calls == []


@pytest.mark.parametrize("count,next_offset", [(5, 4), (4, None)])
def test_transactions_filters_and_paging(monkeypatch, context, count, next_offset):
    session, events, clock = context
    found = list(range(count))
    load = Mock(return_value=found)
    monkeypatch.setattr(queues, "search_transactions", load)
    monkeypatch.setattr(queues, "account_names", Mock(return_value={2: "Test Card"}))
    serialize = Mock(side_effect=lambda item, names: {"id": item, "account": names[2]})
    monkeypatch.setattr(queues.serialization, "transaction_item", serialize)
    result = tools.list_transactions(
        text="ACME",
        account="Test Card",
        person="Pat",
        category="Coffee",
        group="Food",
        merchant="ACME",
        bank="Test Bank",
        card="1111",
        kind="spending",
        start=date(2026, 2, 1),
        end=DAY,
        limit=2,
        offset=2,
    )
    assert result == {
        "transactions": [{"id": 2, "account": "Test Card"}, {"id": 3, "account": "Test Card"}],
        "next_offset": next_offset,
    }
    query = load.call_args.args[1]
    assert load.call_args.args[0] is session
    assert (
        query.text,
        query.account,
        query.person,
        query.category,
        query.group,
        query.merchant,
        query.bank,
        query.card,
        query.kind,
        query.start,
        query.end,
        query.limit,
    ) == (
        "ACME",
        "Test Card",
        "Pat",
        "Coffee",
        "Food",
        "ACME",
        "Test Bank",
        "1111",
        "spending",
        date(2026, 2, 1),
        DAY,
        5,
    )
    assert serialize.call_args_list == [call(2, {2: "Test Card"}), call(3, {2: "Test Card"})]
    assert events == ["enter", "success"] and session.mock_calls == []


def test_reversed_dates_before_reading(context):
    session, events, clock = context
    with pytest.raises(ToolError, match="^the start date is after the end date$"):
        tools.list_transactions(start=DAY, end=date(2026, 2, 1))
    assert events == [] and session.mock_calls == []


@pytest.mark.parametrize("error", [ValueError("synthetic"), LookupError("synthetic")])
def test_transaction_error_context(monkeypatch, context, error):
    session, events, clock = context
    monkeypatch.setattr(queues, "search_transactions", Mock(side_effect=error))
    expected = ToolError if isinstance(error, ValueError) else LookupError
    with pytest.raises(expected, match="^synthetic$") as caught:
        tools.list_transactions()
    assert caught.value.__cause__ is error if expected is ToolError else caught.value is error
    assert events == ["enter", expected] and session.mock_calls == []


def test_categories_rules_uncategorized(monkeypatch, context):
    session, events, clock = context
    categories = [
        NS(id=1, name="Food", group_id=None),
        NS(id=2, name="Coffee", group_id=1, is_transfer=False, is_income=False, is_sensitive=True),
        NS(
            id=3, name="Transfer", group_id=1, is_transfer=True, is_income=False, is_sensitive=False
        ),
    ]
    monkeypatch.setattr(queues, "load_categories", Mock(return_value=categories))
    rules = Mock(
        return_value=[
            NS(id=2, priority=10, match="contains", pattern="ACME", category_id=2),
            NS(id=1, priority=1, match="equals", pattern="FOO", category_id=3),
        ]
    )
    monkeypatch.setattr(queues, "load_rules", rules)
    assert tools.list_categories() == {
        "categories": [
            {
                "name": "Coffee",
                "group": "Food",
                "transfer": False,
                "income": False,
                "sensitive": True,
            },
            {
                "name": "Transfer",
                "group": "Food",
                "transfer": True,
                "income": False,
                "sensitive": False,
            },
        ]
    }
    assert tools.list_rules() == {
        "rules": [
            {"id": 2, "priority": 10, "match": "contains", "pattern": "ACME", "category": "Coffee"},
            {"id": 1, "priority": 1, "match": "equals", "pattern": "FOO", "category": "Transfer"},
        ]
    }
    row = NS(description="ACME COFFEE")
    monkeypatch.setattr(queues, "account_names", Mock(return_value={}))
    load = Mock(return_value=[row])
    monkeypatch.setattr(queues, "load_uncategorized", load)
    monkeypatch.setattr(queues, "count_uncategorized", Mock(return_value=4))
    monkeypatch.setattr(queues.serialization, "brief", Mock(return_value={"id": 1}))
    assert tools.list_uncategorized(3) == {
        "total": 4,
        "transactions": [{"id": 1, "merchant": "ACME COFFEE"}],
    }
    load.assert_called_once_with(session, 3)
    assert events == ["enter", "success"] * 3 and session.mock_calls == []


def test_coverage_full_json(monkeypatch, context, tmp_path):
    session, events, clock = context
    dt = datetime(2026, 2, 15, 12, 0, tzinfo=UTC)
    a = NS(
        name="Test Card",
        gaps=[(date(2026, 1, 2), date(2026, 1, 3))],
        newest_statement_end=DAY,
        mapped=True,
        last_pull=dt,
        drift_cents=-20,
        drift_date=DAY,
    )
    b = NS(
        name="Test Savings",
        gaps=[],
        newest_statement_end=None,
        mapped=False,
        last_pull=None,
        drift_cents=None,
        drift_date=None,
    )
    result = NS(
        as_of=DAY,
        accounts=[
            NS(
                facts=a,
                type="credit_card",
                span=(date(2026, 1, 1), DAY),
                audited=[(date(2026, 1, 1), DAY)],
            ),
            NS(facts=b, type="savings", span=None, audited=[]),
        ],
        problems=[
            NS(kind="gap", account="", detail="Synthetic", action="Review"),
            NS(kind="stale", account="Test Card", detail="Old", action="Import"),
        ],
    )
    load = Mock(return_value=result)
    monkeypatch.setattr(queues, "coverage_report", load)
    monkeypatch.setattr(queues, "get_settings", lambda: NS(effective_backup_dir=tmp_path))
    assert tools.data_coverage() == {
        "as_of": "2026-02-15",
        "accounts": [
            {
                "name": "Test Card",
                "type": "credit_card",
                "first_day": "2026-01-01",
                "last_day": "2026-02-15",
                "audited": [{"start": "2026-01-01", "end": "2026-02-15"}],
                "gaps": [{"start": "2026-01-02", "end": "2026-01-03"}],
                "newest_statement_end": "2026-02-15",
                "mapped": True,
                "last_pull": "2026-02-15T12:00:00+00:00",
                "drift_cents": -20,
                "drift_date": "2026-02-15",
            },
            {
                "name": "Test Savings",
                "type": "savings",
                "first_day": None,
                "last_day": None,
                "audited": [],
                "gaps": [],
                "newest_statement_end": None,
                "mapped": False,
                "last_pull": None,
                "drift_cents": None,
                "drift_date": None,
            },
        ],
        "problems": [
            {"kind": "gap", "account": None, "detail": "Synthetic", "action": "Review"},
            {"kind": "stale", "account": "Test Card", "detail": "Old", "action": "Import"},
        ],
    }
    load.assert_called_once_with(session, tmp_path, DAY)
    clock.assert_called_once_with()
    assert events == ["enter", "success"] and session.mock_calls == []


@pytest.mark.parametrize(
    "phrase,error",
    [(" " * 101, "give a phrase to look for"), ("x" * 101, "a phrase is at most 100 characters")],
)
def test_merchant_invalid_before_session(context, phrase, error):
    session, events, clock = context
    with pytest.raises(ToolError, match=error):
        tools.find_merchants(phrase)
    assert events == [] and session.mock_calls == []


@pytest.mark.parametrize("phrase,expected", [("  ACME  ", "ACME"), ("x" * 100, "x" * 100)])
def test_merchant_lookup(monkeypatch, context, phrase, expected):
    session, events, clock = context
    load = Mock(return_value=[NS(name="ACME", kind="merchant", score=99)])
    monkeypatch.setattr(queues, "find_names", load)
    assert tools.find_merchants(phrase, 7) == {
        "matches": [{"name": "ACME", "kind": "merchant", "score": 99}]
    }
    load.assert_called_once_with(session, expected, 7)
    assert events == ["enter", "success"] and session.mock_calls == []


def test_suggestions_order(monkeypatch, context):
    session, events, clock = context
    names = {2: "Test"}
    monkeypatch.setattr(queues, "account_names", Mock(return_value=names))
    monkeypatch.setattr(queues, "transfer_suggestions", Mock(return_value=[(9, 8), (1, 2)]))
    named = Mock(side_effect=lambda s, i, n: {"id": i})
    monkeypatch.setattr(queues.serialization, "named", named)
    assert tools.list_transfer_suggestions() == {
        "suggestions": [{"out": {"id": 9}, "in": {"id": 8}}, {"out": {"id": 1}, "in": {"id": 2}}]
    }
    assert named.call_args_list == [call(session, i, names) for i in [9, 8, 1, 2]]
    assert events == ["enter", "success"] and session.mock_calls == []


def test_facade_and_no_reverse_imports():
    assert tools.By is reports.By
    for module in [accounts, queues]:
        tree = ast.parse(Path(module.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in {
                    "finances.mcp_server.tools",
                    "finances.mcp_server.server",
                }
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"__import__", "eval", "exec"}


def test_recursive_size_gate_rejects_401(monkeypatch, tmp_path):
    from tests.unit.test_mcp_facade_contract import test_all_mcp_sources_fit

    folder = tmp_path / "mcp_server"
    folder.mkdir()
    source = folder / "tools.py"
    source.write_text("pass\n" * 400)
    monkeypatch.setattr(tools, "__file__", str(source))
    test_all_mcp_sources_fit()
    nested = folder / "new"
    nested.mkdir()
    (nested / "future.py").write_text("pass\n" * 401)
    with pytest.raises(AssertionError):
        test_all_mcp_sources_fit()
