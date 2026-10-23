"""The agent's read-only tools. Each returns one JSON object."""

from collections.abc import Callable
from datetime import date
from typing import Annotated, Any, Literal

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field
from sqlalchemy.orm import Session

import finances.clock as clock
from finances.analysis.balances import balance_report
from finances.analysis.budgets import budget_report
from finances.analysis.coverage import coverage_report
from finances.analysis.forecast import forecast_report
from finances.analysis.insights import insights_report
from finances.analysis.months import month_report
from finances.analysis.names import find_names
from finances.analysis.networth import net_worth_over_time
from finances.analysis.recurring import recurring_charges, recurring_income
from finances.analysis.search import FoundTransaction, TransactionQuery, search_transactions
from finances.analysis.spending import spending_report
from finances.analysis.upcoming import upcoming_report
from finances.categorize.transfers import transfer_suggestions
from finances.config import get_settings
from finances.db.repositories import (
    account_names,
    count_uncategorized,
    get_transaction,
    list_account_owners,
    list_people,
    list_transfer_pairs,
    proposal_out_of_date,
)
from finances.db.repositories import list_accounts as load_accounts
from finances.db.repositories import list_advice as load_advice
from finances.db.repositories import list_categories as load_categories
from finances.db.repositories import list_proposals as load_proposals
from finances.db.repositories import list_rules as load_rules
from finances.db.repositories import list_uncategorized as load_uncategorized
from finances.db.repositories import log_advice as keep_advice
from finances.db.repositories import propose_category as store_category_proposal
from finances.db.repositories import propose_merchant_alias as store_alias
from finances.db.repositories import propose_not_transfer as store_not_transfer
from finances.db.repositories import propose_rule as store_rule
from finances.db.repositories import propose_transfer as store_transfer
from finances.domain.merchants import clean_merchant
from finances.domain.models import Transaction
from finances.domain.proposals import ALIAS, CATEGORY, RULE, Proposal
from finances.domain.spending import UNASSIGNED, UNCATEGORIZED, is_refund, month_bounds, month_range
from finances.mcp_server.access import reading, writing

By = Literal["category", "group", "merchant", "person", "account", "bank", "card"]


def list_accounts(include_inactive: bool = False) -> dict[str, Any]:
    with reading() as session:
        people = {person.id: person.name for person in list_people(session)}
        owners = list_account_owners(session)
        accounts = []
        for account in load_accounts(session, include_inactive):
            has_row = account.id in owners
            person_id = owners.get(account.id)
            accounts.append(
                {
                    "name": account.name,
                    "institution": account.institution,
                    "type": account.type.value,
                    "currency": account.currency,
                    "last4": account.last4,
                    "active": account.is_active,
                    "owner": None if person_id is None else people[person_id],
                    "joint": has_row and person_id is None,
                }
            )
        return {"accounts": accounts}


def get_balances() -> dict[str, Any]:
    with reading() as session:
        report = balance_report(session)
        return {
            "accounts": [
                {
                    "name": line.account,
                    "type": line.type,
                    "balance_cents": line.balance_cents,
                    "as_of": None if line.as_of is None else line.as_of.isoformat(),
                    "source": line.source,
                }
                for line in report.lines
            ],
            "cash_cents": report.cash_cents,
            "cards_cents": report.cards_cents,
            "other_cents": report.other_cents,
            "net_worth_cents": report.net_worth_cents,
            "without_balance": report.without_balance,
        }


def get_net_worth(months: Annotated[int, Field(ge=1, le=60)] = 12) -> dict[str, Any]:
    with reading() as session:
        today = clock.today()
        return {
            "as_of": today.isoformat(),
            "points": [
                {
                    "day": point.day.isoformat(),
                    "net_worth_cents": point.net_worth_cents,
                    "accounts": point.accounts,
                }
                for point in net_worth_over_time(session, today, months)
            ],
        }


def _transaction_item(item: FoundTransaction, names: dict[int, str]) -> dict[str, Any]:
    flow = item.flow
    found = item.transaction
    uncategorized = flow.category == UNCATEGORIZED
    return {
        "id": found.id,
        "day": flow.day.isoformat(),
        "posted": found.posted_date.isoformat(),
        "account": names[found.account_id],
        "description": found.description,
        "merchant": flow.merchant,
        "amount_cents": found.amount_cents,
        "kind": flow.kind,
        "refund": is_refund(flow),
        "category": None if uncategorized else flow.category,
        "group": None if uncategorized else flow.group,
        "person": None if flow.person == UNASSIGNED else flow.person,
        "card": found.card_last4,
        "pending": found.is_pending,
    }


def list_transactions(
    text: str = "",
    account: str = "",
    person: str = "",
    category: str = "",
    group: str = "",
    merchant: str = "",
    bank: str = "",
    card: str = "",
    kind: str = "",
    start: date | None = None,
    end: date | None = None,
    limit: Annotated[int, Field(ge=1, le=200)] = 50,
    offset: Annotated[int, Field(ge=0, le=5000)] = 0,
) -> dict[str, Any]:
    if start is not None and end is not None and start > end:
        raise ToolError("the start date is after the end date")
    query = TransactionQuery(
        text=text,
        account=account,
        person=person,
        category=category,
        group=group,
        merchant=merchant,
        bank=bank,
        card=card,
        kind=kind,
        start=start,
        end=end,
        limit=offset + limit + 1,
    )
    with reading() as session:
        try:
            found = search_transactions(session, query)
        except ValueError as error:
            raise ToolError(str(error)) from error
        names = account_names(session)
    page = found[offset : offset + limit]
    next_offset = offset + limit if len(found) > offset + limit else None
    return {
        "transactions": [_transaction_item(item, names) for item in page],
        "next_offset": next_offset,
    }


def get_spending(
    start: date | None = None,
    end: date | None = None,
    by: By = "category",
) -> dict[str, Any]:
    if (start is None) != (end is None):
        raise ToolError("give both start and end, or neither")
    if start is None or end is None:
        start, end = month_bounds(clock.today())
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


def _month_start(month: str) -> date:
    if not month:
        start, _ = month_bounds(clock.today())
        return start
    try:
        start, _ = month_range(month)
    except ValueError as error:
        raise ToolError(str(error)) from error
    return start


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


def _brief(item: Transaction, names: dict[int, str]) -> dict[str, Any]:
    return {
        "id": item.id,
        "posted": item.posted_date.isoformat(),
        "account": names[item.account_id],
        "description": item.description,
        "amount_cents": item.amount_cents,
    }


def _named(session: Any, transaction_id: int, names: dict[int, str]) -> dict[str, Any]:
    found = get_transaction(session, transaction_id)
    assert found is not None
    return _brief(found, names)


def list_uncategorized(limit: Annotated[int, Field(ge=1, le=500)] = 50) -> dict[str, Any]:
    with reading() as session:
        names = account_names(session)
        return {
            "total": count_uncategorized(session),
            "transactions": [
                {**_brief(item, names), "merchant": clean_merchant(item.description)}
                for item in load_uncategorized(session, limit)
            ],
        }


def list_categories() -> dict[str, Any]:
    with reading() as session:
        found = load_categories(session)
    groups = {item.id: item.name for item in found if item.group_id is None}
    return {
        "categories": [
            {
                "name": item.name,
                "group": groups[item.group_id],
                "transfer": item.is_transfer,
                "income": item.is_income,
                "sensitive": item.is_sensitive,
            }
            for item in found
            if item.group_id is not None
        ]
    }


def list_rules() -> dict[str, Any]:
    with reading() as session:
        names = {item.id: item.name for item in load_categories(session)}
        return {
            "rules": [
                {
                    "id": item.id,
                    "priority": item.priority,
                    "match": item.match,
                    "pattern": item.pattern,
                    "category": names[item.category_id],
                }
                for item in load_rules(session)
            ]
        }


def list_transfers(limit: Annotated[int, Field(ge=1, le=500)] = 100) -> dict[str, Any]:
    with reading() as session:
        names = account_names(session)
        pairs = list_transfer_pairs(session)
        newest = sorted(pairs, key=lambda item: item.id, reverse=True)
        return {
            "total": len(pairs),
            "pairs": [
                {
                    "pair": item.id,
                    "status": item.status,
                    "out": _named(session, item.out_transaction_id, names),
                    "in": _named(session, item.in_transaction_id, names),
                }
                for item in newest[:limit]
            ],
        }


def list_transfer_suggestions() -> dict[str, Any]:
    with reading() as session:
        names = account_names(session)
        return {
            "suggestions": [
                {
                    "out": _named(session, out_id, names),
                    "in": _named(session, in_id, names),
                }
                for out_id, in_id in transfer_suggestions(session)
            ]
        }


def _iso(day: date | None) -> str | None:
    return None if day is None else day.isoformat()


def data_coverage() -> dict[str, Any]:
    today = clock.today()
    with reading() as session:
        report = coverage_report(session, get_settings().effective_backup_dir, today)
    return {
        "as_of": report.as_of.isoformat(),
        "accounts": [
            {
                "name": item.facts.name,
                "type": item.type,
                "first_day": None if item.span is None else item.span[0].isoformat(),
                "last_day": None if item.span is None else item.span[1].isoformat(),
                "audited": [
                    {"start": start.isoformat(), "end": end.isoformat()}
                    for start, end in item.audited
                ],
                "gaps": [
                    {"start": start.isoformat(), "end": end.isoformat()}
                    for start, end in item.facts.gaps
                ],
                "newest_statement_end": _iso(item.facts.newest_statement_end),
                "mapped": item.facts.mapped,
                "last_pull": _iso(item.facts.last_pull),
                "drift_cents": item.facts.drift_cents,
                "drift_date": _iso(item.facts.drift_date),
            }
            for item in report.accounts
        ],
        "problems": [
            {
                "kind": problem.kind,
                "account": problem.account or None,
                "detail": problem.detail,
                "action": problem.action,
            }
            for problem in report.problems
        ],
    }


def find_merchants(phrase: str, limit: Annotated[int, Field(ge=1, le=20)] = 5) -> dict[str, Any]:
    stripped = phrase.strip()
    if not stripped:
        raise ToolError("give a phrase to look for")
    if len(phrase) > 100:
        raise ToolError("a phrase is at most 100 characters")
    with reading() as session:
        found = find_names(session, stripped, limit)
    return {
        "matches": [{"name": item.name, "kind": item.kind, "score": item.score} for item in found]
    }


def _proposal_item(session: Session, proposal: Proposal) -> dict[str, Any]:
    return {
        "id": proposal.id,
        "kind": proposal.kind,
        "transaction_id": proposal.target_id,
        "in_id": proposal.other_id,
        "category": proposal.value if proposal.kind in (CATEGORY, RULE) else None,
        "rule": (
            None
            if proposal.kind != RULE
            else {
                "match": proposal.match,
                "pattern": proposal.pattern,
                "priority": proposal.priority,
            }
        ),
        "alias": (
            None
            if proposal.kind != ALIAS
            else {"source": proposal.source, "target": proposal.value}
        ),
        "reason": proposal.reason,
        "status": proposal.status,
        "created_at": proposal.created_at.isoformat(),
        "decided_at": _iso(proposal.decided_at),
        "out_of_date": proposal_out_of_date(session, proposal),
    }


def _as_tool(work: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return work()
    except ValueError as error:
        raise ToolError(str(error)) from None


def propose_category(transaction_id: int, category: str, reason: str) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            found = store_category_proposal(session, transaction_id, category, reason)
            return {"proposal": _proposal_item(session, found)}

    return _as_tool(work)


def propose_transfer(out_id: int, in_id: int, reason: str) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            found = store_transfer(session, out_id, in_id, reason)
            return {"proposal": _proposal_item(session, found)}

    return _as_tool(work)


def propose_not_transfer(out_id: int, in_id: int, reason: str) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            found = store_not_transfer(session, out_id, in_id, reason)
            return {"proposal": _proposal_item(session, found)}

    return _as_tool(work)


def propose_rule(
    example_id: int,
    pattern: str,
    category: str,
    reason: str,
    match: Literal["contains", "starts_with", "equals"] = "contains",
    priority: Annotated[int, Field(ge=-1000, le=1000)] = 0,
) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            found = store_rule(
                session, example_id, pattern, category, reason, match=match, priority=priority
            )
            return {"proposal": _proposal_item(session, found)}

    return _as_tool(work)


def propose_merchant_alias(example_id: int, target: str, reason: str) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            found = store_alias(session, example_id, target, reason)
            return {"proposal": _proposal_item(session, found)}

    return _as_tool(work)


def list_proposals(
    status: Literal["open", "accepted", "declined"] = "open",
    limit: Annotated[int, Field(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with reading() as session:
            found = load_proposals(session, status=status, limit=limit)
            return {"proposals": [_proposal_item(session, item) for item in found]}

    return _as_tool(work)


def log_advice(text: str, subject: str = "") -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            found = keep_advice(session, text, subject)
            return {
                "advice": {
                    "id": found.id,
                    "created_at": found.created_at.isoformat(),
                    "subject": found.subject,
                    "text": found.text,
                }
            }

    return _as_tool(work)


def list_advice(limit: Annotated[int, Field(ge=1, le=200)] = 20) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with reading() as session:
            found = load_advice(session, limit=limit)
            return {
                "advice": [
                    {
                        "id": item.id,
                        "created_at": item.created_at.isoformat(),
                        "subject": item.subject,
                        "text": item.text,
                    }
                    for item in found
                ]
            }

    return _as_tool(work)
