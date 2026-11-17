"""Read tools and permitted proposal/advice writers, returning JSON objects."""

from datetime import date
from typing import Annotated, Any

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

import finances.clock as clock
from finances.analysis.balances import balance_report
from finances.analysis.coverage import coverage_report
from finances.analysis.listings import account_listing
from finances.analysis.names import find_names
from finances.analysis.networth import net_worth_over_time
from finances.analysis.search import TransactionQuery, search_transactions
from finances.categorize.transfers import transfer_suggestions
from finances.config import get_settings
from finances.db.repositories import (
    account_names,
    count_uncategorized,
    list_transfer_pairs,
)
from finances.db.repositories import list_categories as load_categories
from finances.db.repositories import list_rules as load_rules
from finances.db.repositories import list_uncategorized as load_uncategorized
from finances.domain.merchants import clean_merchant
from finances.mcp_server import serialization
from finances.mcp_server.access import reading
from finances.mcp_server.proposals import list_advice as list_advice
from finances.mcp_server.proposals import list_proposals as list_proposals
from finances.mcp_server.proposals import log_advice as log_advice
from finances.mcp_server.proposals import propose_category as propose_category
from finances.mcp_server.proposals import propose_category_change as propose_category_change
from finances.mcp_server.proposals import propose_finding_status as propose_finding_status
from finances.mcp_server.proposals import propose_group as propose_group
from finances.mcp_server.proposals import propose_merchant_alias as propose_merchant_alias
from finances.mcp_server.proposals import propose_new_category as propose_new_category
from finances.mcp_server.proposals import propose_not_transfer as propose_not_transfer
from finances.mcp_server.proposals import propose_rule as propose_rule
from finances.mcp_server.proposals import propose_rule_change as propose_rule_change
from finances.mcp_server.proposals import propose_transfer as propose_transfer
from finances.mcp_server.reports import By as By
from finances.mcp_server.reports import get_budgets as get_budgets
from finances.mcp_server.reports import get_forecast as get_forecast
from finances.mcp_server.reports import get_insights as get_insights
from finances.mcp_server.reports import get_recurring as get_recurring
from finances.mcp_server.reports import get_spending as get_spending
from finances.mcp_server.reports import get_upcoming as get_upcoming
from finances.mcp_server.reports import month_over_month as month_over_month


def list_accounts(include_inactive: bool = False) -> dict[str, Any]:
    with reading() as session:
        accounts = []
        for item in account_listing(session, include_inactive=include_inactive):
            account = item.account
            accounts.append(
                {
                    "name": account.name,
                    "institution": account.institution,
                    "type": account.type.value,
                    "currency": account.currency,
                    "last4": account.last4,
                    "active": account.is_active,
                    "owner": None if item.joint else item.owner,
                    "joint": item.joint,
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
        "transactions": [serialization.transaction_item(item, names) for item in page],
        "next_offset": next_offset,
    }


def list_uncategorized(limit: Annotated[int, Field(ge=1, le=500)] = 50) -> dict[str, Any]:
    with reading() as session:
        names = account_names(session)
        return {
            "total": count_uncategorized(session),
            "transactions": [
                {**serialization.brief(item, names), "merchant": clean_merchant(item.description)}
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
                    "out": serialization.named(session, item.out_transaction_id, names),
                    "in": serialization.named(session, item.in_transaction_id, names),
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
                    "out": serialization.named(session, out_id, names),
                    "in": serialization.named(session, in_id, names),
                }
                for out_id, in_id in transfer_suggestions(session)
            ]
        }


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
                "newest_statement_end": serialization.iso(item.facts.newest_statement_end),
                "mapped": item.facts.mapped,
                "last_pull": serialization.iso(item.facts.last_pull),
                "drift_cents": item.facts.drift_cents,
                "drift_date": serialization.iso(item.facts.drift_date),
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
