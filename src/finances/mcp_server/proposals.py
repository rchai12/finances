"""Proposal and advice adapters; ledger changes require person acceptance."""

from collections.abc import Callable
from typing import Annotated, Any, Literal

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from finances.analysis.insights import find_finding
from finances.db.repositories import list_advice as load_advice
from finances.db.repositories import list_proposals as load_proposals
from finances.db.repositories import log_advice as keep_advice
from finances.db.repositories import propose_category as store_category_proposal
from finances.db.repositories import propose_category_change as store_category_change
from finances.db.repositories import propose_finding_status as store_finding_status
from finances.db.repositories import propose_group as store_group
from finances.db.repositories import propose_merchant_alias as store_alias
from finances.db.repositories import propose_new_category as store_new_category
from finances.db.repositories import propose_not_transfer as store_not_transfer
from finances.db.repositories import propose_rule as store_rule
from finances.db.repositories import propose_rule_change as store_rule_change
from finances.db.repositories import propose_transfer as store_transfer
from finances.db.repositories.categories import CategoryExistsError
from finances.mcp_server import serialization
from finances.mcp_server.access import reading, writing
from finances.mcp_server.helpers import month_start as _month_start


def _as_tool(work: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return work()
    except (ValueError, CategoryExistsError) as error:
        raise ToolError(str(error)) from None


def propose_category(transaction_id: int, category: str, reason: str) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            found = store_category_proposal(session, transaction_id, category, reason)
            return {"proposal": serialization.proposal_item(session, found)}

    return _as_tool(work)


def propose_transfer(out_id: int, in_id: int, reason: str) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            found = store_transfer(session, out_id, in_id, reason)
            return {"proposal": serialization.proposal_item(session, found)}

    return _as_tool(work)


def propose_not_transfer(out_id: int, in_id: int, reason: str) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            found = store_not_transfer(session, out_id, in_id, reason)
            return {"proposal": serialization.proposal_item(session, found)}

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
            return {"proposal": serialization.proposal_item(session, found)}

    return _as_tool(work)


def propose_merchant_alias(example_id: int, target: str, reason: str) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            found = store_alias(session, example_id, target, reason)
            return {"proposal": serialization.proposal_item(session, found)}

    return _as_tool(work)


def propose_group(
    name: str,
    example_id: int,
    reason: str,
    kind: Literal["spending", "transfer", "income"] = "spending",
    sensitive: bool = False,
) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            found = store_group(session, example_id, name, reason, kind=kind, sensitive=sensitive)
            return {"proposal": serialization.proposal_item(session, found)}

    return _as_tool(work)


def propose_new_category(
    name: str,
    group: str,
    example_id: int,
    reason: str,
    tax: bool = False,
) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            found = store_new_category(session, example_id, name, group, reason, tax=tax)
            return {"proposal": serialization.proposal_item(session, found)}

    return _as_tool(work)


def propose_rule_change(
    rule_id: int,
    reason: str,
    delete: bool = False,
    pattern: str | None = None,
    match: Literal["contains", "starts_with", "equals"] | None = None,
    priority: Annotated[int | None, Field(ge=-1000, le=1000)] = None,
    category: str | None = None,
) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            found = store_rule_change(
                session,
                rule_id,
                reason,
                delete=delete,
                pattern=pattern,
                match=match,
                priority=priority,
                category=category,
            )
            return {"proposal": serialization.proposal_item(session, found)}

    return _as_tool(work)


def propose_category_change(
    name: str,
    reason: str,
    rename_to: str | None = None,
    delete: bool = False,
    move_to: str | None = None,
) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            found = store_category_change(
                session, name, reason, rename_to=rename_to, delete=delete, move_to=move_to
            )
            return {"proposal": serialization.proposal_item(session, found)}

    return _as_tool(work)


def propose_finding_status(
    type: str, status: str, reason: str, about: str = "", month: str = ""
) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with writing() as session:
            start = _month_start(month)
            found = find_finding(session, start, type, about)
            stored = store_finding_status(session, found, status, reason)
            return {"proposal": serialization.proposal_item(session, stored)}

    return _as_tool(work)


def list_proposals(
    status: Literal["open", "accepted", "declined"] = "open",
    limit: Annotated[int, Field(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        with reading() as session:
            found = load_proposals(session, status=status, limit=limit)
            return {"proposals": [serialization.proposal_item(session, item) for item in found]}

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
                    "dismissed_at": serialization.iso(found.dismissed_at),
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
                        "dismissed_at": serialization.iso(item.dismissed_at),
                    }
                    for item in found
                ]
            }

    return _as_tool(work)
