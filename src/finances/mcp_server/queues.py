"""Read-only MCP queues adapters."""

from datetime import date
from typing import Annotated, Any

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

import finances.clock as clock
from finances.analysis.coverage import coverage_report
from finances.analysis.names import find_names
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
