"""Read-only MCP reporting adapters."""

from datetime import date
from typing import Annotated, Any, Literal

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

import finances.clock as clock
from finances.analysis.budgets import budget_report
from finances.analysis.forecast import forecast_report
from finances.analysis.insights import insights_report
from finances.analysis.months import month_report
from finances.analysis.recurring import recurring_charges, recurring_income
from finances.analysis.spending import spending_report
from finances.analysis.upcoming import upcoming_report
from finances.domain import periods
from finances.domain.spending import month_range
from finances.mcp_server.access import reading
from finances.mcp_server.helpers import month_start as _month_start

By = Literal["category", "group", "merchant", "person", "account", "bank", "card"]


def get_spending(
    start: date | None = None,
    end: date | None = None,
    by: By = "category",
) -> dict[str, Any]:
    try:
        period = periods.select_period(
            start=start, end=end, today=clock.today() if start is None and end is None else date.min
        )
    except periods.PeriodError as error:
        raise ToolError("give both start and end, or neither") from error
    start, end = period.start, period.end
    with reading() as session:
        try:
            report = spending_report(session, start, end, by)
        except ValueError as error:
            raise ToolError(str(error)) from error
    return {
        "start": report.start.isoformat(),
        "end": report.end.isoformat(),
        "by": report.by,
        "lines": [
            {
                "label": line.label,
                "spent_cents": line.purchases_cents,
                "refunds_cents": line.refunds_cents,
                "net_cents": line.spent_cents,
                "count": line.count,
            }
            for line in report.lines
        ],
        "summary": {
            "spent_cents": report.summary.spent_cents + report.summary.refunds_cents,
            "refunds_cents": report.summary.refunds_cents,
            "net_cents": report.summary.spent_cents,
            "income_cents": report.summary.income_cents,
            "transfers": report.summary.transfers,
            "unsorted_in_cents": report.summary.unsorted_in_cents,
            "unsorted_in_count": report.summary.unsorted_in_count,
        },
    }


def month_over_month(
    month: str = "", count: Annotated[int, Field(ge=1, le=24)] = 6
) -> dict[str, Any]:
    if month:
        try:
            _, day = month_range(month)
        except ValueError as error:
            raise ToolError(str(error)) from error
    else:
        day = clock.today()
    with reading() as session:
        lines = month_report(session, day, count)
    return {
        "months": [
            {
                "month": line.start.isoformat()[:7],
                "net_cents": line.spent_cents,
                "income_cents": line.income_cents,
                "uncovered": line.uncovered,
            }
            for line in lines
        ]
    }


def get_insights(month: str = "") -> dict[str, Any]:
    start = _month_start(month)
    with reading() as session:
        report = insights_report(session, start)
    return {
        "month": report.month.isoformat()[:7],
        "findings": [
            {
                "type": item.type,
                "severity": item.severity,
                "subject": item.subject or None,
                "savings_cents": item.savings_cents,
                "detail": item.detail,
            }
            for item in report.findings
        ],
        "merchants": [
            {
                "merchant": item.merchant,
                "visits": item.visits,
                "spent_cents": item.spent_cents,
                "average_cents": item.average_cents,
                "baseline_cents": item.baseline_cents,
                "change_cents": item.change_cents,
                "weekend_visits": item.weekend_visits,
            }
            for item in report.merchants
        ],
        "set_aside": [
            {
                "type": item.finding.type,
                "severity": item.finding.severity,
                "subject": item.finding.subject or None,
                "savings_cents": item.finding.savings_cents,
                "detail": item.finding.detail,
                "status": item.status,
            }
            for item in report.closed
        ],
    }


def get_recurring(income: bool = False, include_inactive: bool = False) -> dict[str, Any]:
    today = clock.today()
    with reading() as session:
        series = recurring_income(session, today) if income else recurring_charges(session, today)
    sign = 1 if income else -1
    kept = [item for item in series if include_inactive or item.active]
    return {
        "as_of": today.isoformat(),
        "income": income,
        "series": [
            {
                "merchant": item.merchant,
                "cadence": item.cadence,
                "amount_cents": sign * item.amount_cents,
                "monthly_cents": sign * item.monthly_cents,
                "count": item.count,
                "first_day": item.first_day.isoformat(),
                "last_day": item.last_day.isoformat(),
                "next_day": item.next_day.isoformat(),
                "active": item.active,
                "previous_cents": (
                    None if item.previous_cents is None else sign * item.previous_cents
                ),
            }
            for item in kept
        ],
    }


def get_upcoming(days: Annotated[int, Field(ge=1, le=90)] = 30) -> dict[str, Any]:
    today = clock.today()
    with reading() as session:
        report = upcoming_report(session, today, days)
    return {
        "start": report.start.isoformat(),
        "end": report.end.isoformat(),
        "items": [
            {
                "day": item.day.isoformat(),
                "kind": item.kind,
                "merchant": item.merchant,
                "cadence": item.cadence,
                "amount_cents": item.amount_cents,
            }
            for item in report.items
        ],
        "bills_cents": report.bills_cents,
        "income_cents": report.income_cents,
    }


def get_forecast(
    days: Annotated[int, Field(ge=1, le=90)] = 30, account: str = ""
) -> dict[str, Any]:
    today = clock.today()
    wanted = account or None
    with reading() as session:
        try:
            report = forecast_report(session, today, days, wanted)
        except ValueError as error:
            raise ToolError(str(error)) from error
    return {
        "start": report.start.isoformat(),
        "end": report.end.isoformat(),
        "accounts": [
            {
                "account": item.account,
                "balance_cents": item.balance_cents,
                "balance_day": item.balance_day.isoformat(),
                "in_cents": item.walk.in_cents,
                "out_cents": item.walk.out_cents,
                "end_cents": item.walk.end_cents,
                "lowest_cents": item.walk.lowest_cents,
                "lowest_day": item.walk.lowest_day.isoformat(),
                "steps": [
                    {
                        "day": step.item.day.isoformat(),
                        "merchant": step.item.merchant,
                        "amount_cents": step.item.amount_cents,
                        "balance_cents": step.balance_cents,
                    }
                    for step in item.walk.steps
                ],
            }
            for item in report.accounts
        ],
        "no_balance": report.no_balance,
    }


def get_budgets(month: str = "") -> dict[str, Any]:
    start = _month_start(month)
    today = clock.today()
    with reading() as session:
        lines = budget_report(session, start, today)
    return {
        "month": start.isoformat()[:7],
        "budgets": [
            {
                "name": line.name,
                "kind": "group" if line.is_group else "category",
                "target_cents": line.target_cents,
                "net_cents": line.spent_cents,
                "left_cents": line.left_cents,
                "used_percent": line.used_percent,
                "month_gone_percent": line.month_gone_percent,
            }
            for line in lines
        ],
    }
