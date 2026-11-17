import ast
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS
from typing import get_args
from unittest.mock import Mock

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from finances.mcp_server import helpers, reports, tools

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

    monkeypatch.setattr(reports, "reading", reading)
    clock = Mock(return_value=DAY)
    monkeypatch.setattr(reports.clock, "today", clock)
    return session, events, clock


def spending():
    return NS(
        start=date(2026, 2, 1),
        end=date(2026, 2, 28),
        by="category",
        lines=[],
        summary=NS(
            spent_cents=0,
            refunds_cents=0,
            income_cents=0,
            transfers=0,
            unsorted_in_cents=0,
            unsorted_in_count=0,
        ),
    )


@pytest.mark.parametrize("by", get_args(reports.By))
def test_spending_forwarding_without_calendar(monkeypatch, context, by):
    session, events, clock = context
    load = Mock(return_value=spending())
    monkeypatch.setattr(reports, "spending_report", load)
    result = tools.get_spending(date(2026, 2, 28), date(2026, 2, 1), by)
    load.assert_called_once_with(session, date(2026, 2, 28), date(2026, 2, 1), by)
    assert result == {
        "start": "2026-02-01",
        "end": "2026-02-28",
        "by": "category",
        "lines": [],
        "summary": {
            "spent_cents": 0,
            "refunds_cents": 0,
            "net_cents": 0,
            "income_cents": 0,
            "transfers": 0,
            "unsorted_in_cents": 0,
            "unsorted_in_count": 0,
        },
    }
    clock.assert_not_called()
    assert events == ["enter", "success"] and session.mock_calls == []


def test_spending_default(monkeypatch, context):
    session, events, clock = context
    load = Mock(return_value=spending())
    monkeypatch.setattr(reports, "spending_report", load)
    assert tools.get_spending()["start"] == "2026-02-01"
    load.assert_called_once_with(session, date(2026, 2, 1), date(2026, 2, 28), "category")
    clock.assert_called_once_with()


@pytest.mark.parametrize("bounds", [(DAY, None), (None, DAY)])
def test_partial_before_reading(context, bounds):
    session, events, clock = context
    with pytest.raises(ToolError, match="^give both start and end, or neither$"):
        tools.get_spending(*bounds)
    assert events == [] and session.mock_calls == []
    clock.assert_not_called()


@pytest.mark.parametrize(
    "tool,seam,args",
    [
        ("get_spending", "spending_report", (DAY, DAY)),
        ("get_forecast", "forecast_report", (7, "Test Card")),
    ],
)
@pytest.mark.parametrize(
    "error", [ValueError("synthetic refusal"), LookupError("synthetic refusal")]
)
def test_analysis_errors_and_context(monkeypatch, context, tool, seam, args, error):
    session, events, clock = context
    monkeypatch.setattr(reports, seam, Mock(side_effect=error))
    expected = ToolError if isinstance(error, ValueError) else LookupError
    with pytest.raises(expected, match="^synthetic refusal$") as caught:
        getattr(tools, tool)(*args)
    if expected is ToolError:
        assert caught.value.__cause__ is error
    else:
        assert caught.value is error
    assert events == ["enter", expected] and session.mock_calls == []


@pytest.mark.parametrize("month", ["", "2026-02"])
def test_month_json_and_clocks(monkeypatch, context, month):
    session, events, clock = context
    rows = [
        NS(start=date(2026, 1, 1), spent_cents=100, income_cents=500, uncovered=["Test Card"]),
        NS(start=date(2026, 2, 1), spent_cents=-20, income_cents=700, uncovered=[]),
    ]
    load = Mock(return_value=rows)
    monkeypatch.setattr(reports, "month_report", load)
    assert tools.month_over_month(month, 3) == {
        "months": [
            {"month": "2026-01", "net_cents": 100, "income_cents": 500, "uncovered": ["Test Card"]},
            {"month": "2026-02", "net_cents": -20, "income_cents": 700, "uncovered": []},
        ]
    }
    load.assert_called_once_with(session, DAY if not month else date(2026, 2, 28), 3)
    assert clock.call_count == (0 if month else 1)
    assert events == ["enter", "success"] and session.mock_calls == []


def test_bad_month_before_reading(context):
    session, events, clock = context
    with pytest.raises(ToolError, match="^month must be a year and month, like 2026-05$"):
        tools.month_over_month("2026-13")
    assert events == [] and session.mock_calls == []
    clock.assert_not_called()


@pytest.mark.parametrize("month", ["", "2026-01"])
def test_insights_and_budgets_whole_json(monkeypatch, context, month):
    session, events, clock = context
    first = date(2026, 1 if month else 2, 1)
    finding = NS(type="fee", severity="high", subject="", savings_cents=200, detail="Synthetic fee")
    merchant = NS(
        merchant="ACME",
        visits=2,
        spent_cents=400,
        average_cents=200,
        baseline_cents=100,
        change_cents=300,
        weekend_visits=1,
    )
    load = Mock(
        return_value=NS(
            month=first,
            findings=[finding],
            merchants=[merchant],
            closed=[NS(finding=finding, status="handled")],
        )
    )
    monkeypatch.setattr(reports, "insights_report", load)
    assert tools.get_insights(month) == {
        "month": "2026-01" if month else "2026-02",
        "findings": [
            {
                "type": "fee",
                "severity": "high",
                "subject": None,
                "savings_cents": 200,
                "detail": "Synthetic fee",
            }
        ],
        "merchants": [
            {
                "merchant": "ACME",
                "visits": 2,
                "spent_cents": 400,
                "average_cents": 200,
                "baseline_cents": 100,
                "change_cents": 300,
                "weekend_visits": 1,
            }
        ],
        "set_aside": [
            {
                "type": "fee",
                "severity": "high",
                "subject": None,
                "savings_cents": 200,
                "detail": "Synthetic fee",
                "status": "handled",
            }
        ],
    }
    load.assert_called_once_with(session, first)
    assert clock.call_count == (0 if month else 1)
    clock.reset_mock()
    budgets = Mock(
        return_value=[
            NS(
                name="Food",
                is_group=True,
                target_cents=500,
                spent_cents=200,
                left_cents=300,
                used_percent=40,
                month_gone_percent=50,
            ),
            NS(
                name="Coffee",
                is_group=False,
                target_cents=100,
                spent_cents=200,
                left_cents=-100,
                used_percent=200,
                month_gone_percent=50,
            ),
        ]
    )
    monkeypatch.setattr(reports, "budget_report", budgets)
    assert tools.get_budgets(month) == {
        "month": "2026-01" if month else "2026-02",
        "budgets": [
            {
                "name": "Food",
                "kind": "group",
                "target_cents": 500,
                "net_cents": 200,
                "left_cents": 300,
                "used_percent": 40,
                "month_gone_percent": 50,
            },
            {
                "name": "Coffee",
                "kind": "category",
                "target_cents": 100,
                "net_cents": 200,
                "left_cents": -100,
                "used_percent": 200,
                "month_gone_percent": 50,
            },
        ],
    }
    budgets.assert_called_once_with(session, first, DAY)
    assert clock.call_count == (1 if month else 2)
    assert events == ["enter", "success"] * 2 and session.mock_calls == []


@pytest.mark.parametrize("account", ["", "Test Card"])
def test_upcoming_forecast_json(monkeypatch, context, account):
    session, events, clock = context
    bill = NS(day=DAY, kind="bill", merchant="ACME", cadence="month", amount_cents=-300)
    pay = NS(day=DAY, kind="income", merchant="EXAMPLE PAY", cadence="month", amount_cents=500)
    load = Mock(
        return_value=NS(
            start=DAY, end=date(2026, 2, 21), items=[bill, pay], bills_cents=-300, income_cents=500
        )
    )
    monkeypatch.setattr(reports, "upcoming_report", load)
    assert tools.get_upcoming(7) == {
        "start": "2026-02-15",
        "end": "2026-02-21",
        "items": [
            {
                "day": "2026-02-15",
                "kind": "bill",
                "merchant": "ACME",
                "cadence": "month",
                "amount_cents": -300,
            },
            {
                "day": "2026-02-15",
                "kind": "income",
                "merchant": "EXAMPLE PAY",
                "cadence": "month",
                "amount_cents": 500,
            },
        ],
        "bills_cents": -300,
        "income_cents": 500,
    }
    load.assert_called_once_with(session, DAY, 7)
    forecast = Mock(
        return_value=NS(
            start=DAY,
            end=date(2026, 2, 21),
            accounts=[
                NS(
                    account="Test Card",
                    balance_cents=500,
                    balance_day=DAY,
                    walk=NS(
                        in_cents=0,
                        out_cents=-300,
                        end_cents=200,
                        lowest_cents=200,
                        lowest_day=DAY,
                        steps=[NS(item=bill, balance_cents=200)],
                    ),
                )
            ],
            no_balance=["Test Savings"],
        )
    )
    monkeypatch.setattr(reports, "forecast_report", forecast)
    assert tools.get_forecast(7, account) == {
        "start": "2026-02-15",
        "end": "2026-02-21",
        "accounts": [
            {
                "account": "Test Card",
                "balance_cents": 500,
                "balance_day": "2026-02-15",
                "in_cents": 0,
                "out_cents": -300,
                "end_cents": 200,
                "lowest_cents": 200,
                "lowest_day": "2026-02-15",
                "steps": [
                    {
                        "day": "2026-02-15",
                        "merchant": "ACME",
                        "amount_cents": -300,
                        "balance_cents": 200,
                    }
                ],
            }
        ],
        "no_balance": ["Test Savings"],
    }
    forecast.assert_called_once_with(session, DAY, 7, account or None)
    assert clock.call_count == 2 and events == ["enter", "success"] * 2 and session.mock_calls == []


@pytest.mark.parametrize("empty", [False, True])
def test_recurring_active_null_previous(monkeypatch, context, empty):
    session, events, clock = context
    row = NS(
        merchant="ACME",
        cadence="month",
        amount_cents=300,
        monthly_cents=300,
        count=2,
        first_day=DAY,
        last_day=DAY,
        next_day=DAY,
        active=True,
        previous_cents=None,
    )
    load = Mock(return_value=[] if empty else [row])
    monkeypatch.setattr(reports, "recurring_charges", load)
    assert tools.get_recurring() == {
        "as_of": "2026-02-15",
        "income": False,
        "series": []
        if empty
        else [
            {
                "merchant": "ACME",
                "cadence": "month",
                "amount_cents": -300,
                "monthly_cents": -300,
                "count": 2,
                "first_day": "2026-02-15",
                "last_day": "2026-02-15",
                "next_day": "2026-02-15",
                "active": True,
                "previous_cents": None,
            }
        ],
    }
    load.assert_called_once_with(session, DAY)
    clock.assert_called_once_with()
    assert events == ["enter", "success"] and session.mock_calls == []


def test_structure_identity_and_caps():
    assert tools.By is reports.By
    assert reports._month_start is helpers.month_start
    source = Path(reports.__file__).read_text()
    assert len(source.splitlines()) <= 400
    assert len(Path(tools.__file__).read_text().splitlines()) <= 512
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module not in {"finances.mcp_server.tools", "finances.mcp_server.server"}
            assert all(
                alias.name not in {"tools", "server", "writing", "get_settings"}
                for alias in node.names
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"__import__", "eval", "exec"}
