from contextlib import nullcontext
from datetime import date
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from finances.mcp_server import tools


@pytest.mark.parametrize(
    "name",
    [
        "get_spending",
        "month_over_month",
        "get_insights",
        "get_recurring",
        "get_upcoming",
        "get_forecast",
        "get_budgets",
    ],
)
def test_facade_identity(name):
    from finances.mcp_server import reports

    assert getattr(tools, name) is getattr(reports, name)
    assert getattr(tools, name).__module__ == reports.__name__


def test_spending_json(monkeypatch):
    from finances.mcp_server import reports

    session = Mock()
    report = NS(
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
        by="merchant",
        lines=[NS(label="ACME", purchases_cents=700, refunds_cents=900, spent_cents=-200, count=2)],
        summary=NS(
            spent_cents=-200,
            refunds_cents=900,
            income_cents=1100,
            transfers=3,
            unsorted_in_cents=400,
            unsorted_in_count=1,
        ),
    )
    load = Mock(return_value=report)
    monkeypatch.setattr(reports, "reading", lambda: nullcontext(session))
    monkeypatch.setattr(reports, "spending_report", load)
    assert tools.get_spending(date(2026, 1, 1), date(2026, 1, 31), "merchant") == {
        "start": "2026-01-01",
        "end": "2026-01-31",
        "by": "merchant",
        "lines": [
            {
                "label": "ACME",
                "spent_cents": 700,
                "refunds_cents": 900,
                "net_cents": -200,
                "count": 2,
            }
        ],
        "summary": {
            "spent_cents": 700,
            "refunds_cents": 900,
            "net_cents": -200,
            "income_cents": 1100,
            "transfers": 3,
            "unsorted_in_cents": 400,
            "unsorted_in_count": 1,
        },
    }
    load.assert_called_once_with(session, date(2026, 1, 1), date(2026, 1, 31), "merchant")
    assert session.mock_calls == []


@pytest.mark.parametrize("income", [False, True], ids=["charges", "income"])
@pytest.mark.parametrize("include_inactive", [False, True], ids=["active", "all"])
def test_recurring_json(monkeypatch, income, include_inactive):
    from finances.mcp_server import reports

    session = Mock()
    row = NS(
        merchant="ACME",
        cadence="month",
        amount_cents=300,
        monthly_cents=300,
        count=2,
        first_day=date(2026, 1, 1),
        last_day=date(2026, 2, 1),
        next_day=date(2026, 3, 1),
        active=False,
        previous_cents=200,
    )
    charges = Mock(return_value=[row])
    incoming = Mock(return_value=[row])
    clock = Mock(return_value=date(2026, 2, 2))
    monkeypatch.setattr(reports, "reading", lambda: nullcontext(session))
    monkeypatch.setattr(reports, "recurring_charges", charges)
    monkeypatch.setattr(reports, "recurring_income", incoming)
    monkeypatch.setattr(reports.clock, "today", clock)
    expected = {
        False: {
            "merchant": "ACME",
            "cadence": "month",
            "amount_cents": -300,
            "monthly_cents": -300,
            "count": 2,
            "first_day": "2026-01-01",
            "last_day": "2026-02-01",
            "next_day": "2026-03-01",
            "active": False,
            "previous_cents": -200,
        },
        True: {
            "merchant": "ACME",
            "cadence": "month",
            "amount_cents": 300,
            "monthly_cents": 300,
            "count": 2,
            "first_day": "2026-01-01",
            "last_day": "2026-02-01",
            "next_day": "2026-03-01",
            "active": False,
            "previous_cents": 200,
        },
    }
    assert tools.get_recurring(income, include_inactive) == {
        "as_of": "2026-02-02",
        "income": income,
        "series": [expected[income]] if include_inactive else [],
    }
    selected, unused = (incoming, charges) if income else (charges, incoming)
    selected.assert_called_once_with(session, date(2026, 2, 2))
    unused.assert_not_called()
    clock.assert_called_once_with()
    assert session.mock_calls == []
