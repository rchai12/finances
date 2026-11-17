"""Serialize MCP results, using only the existing adapter read seams."""

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from finances.analysis.search import FoundTransaction
from finances.db.repositories import get_transaction, proposal_out_of_date
from finances.db.repositories.chains import waits_for
from finances.domain.models import Transaction
from finances.domain.proposals import (
    ALIAS,
    CATEGORY,
    CATEGORY_DELETE,
    CATEGORY_RENAME,
    FINDING_STATUS,
    GROUP,
    NEW_CATEGORY,
    RULE,
    RULE_DELETE,
    RULE_EDIT,
    Proposal,
    group_kind_word,
)
from finances.domain.spending import UNASSIGNED, UNCATEGORIZED, is_refund


def transaction_item(item: FoundTransaction, names: dict[int, str]) -> dict[str, Any]:
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
        "amount_cents": flow.amount_cents,
        "kind": flow.kind,
        "refund": is_refund(flow),
        "category": None if uncategorized else flow.category,
        "group": None if uncategorized else flow.group,
        "person": None if flow.person == UNASSIGNED else flow.person,
        "card": found.card_last4,
        "pending": found.is_pending,
    }


def brief(item: Transaction, names: dict[int, str]) -> dict[str, Any]:
    return {
        "id": item.id,
        "posted": item.posted_date.isoformat(),
        "account": names[item.account_id],
        "description": item.description,
        "amount_cents": item.amount_cents,
    }


def named(session: Any, transaction_id: int, names: dict[int, str]) -> dict[str, Any]:
    found = get_transaction(session, transaction_id)
    assert found is not None
    return brief(found, names)


def iso(day: date | None) -> str | None:
    return None if day is None else day.isoformat()


def proposal_item(session: Session, proposal: Proposal) -> dict[str, Any]:
    return {
        "id": proposal.id,
        "kind": proposal.kind,
        "transaction_id": None
        if proposal.kind
        in (RULE_EDIT, RULE_DELETE, CATEGORY_RENAME, CATEGORY_DELETE, FINDING_STATUS)
        else proposal.target_id,
        "in_id": proposal.other_id,
        "category": proposal.value
        if proposal.kind in (CATEGORY, RULE, RULE_EDIT, RULE_DELETE)
        else None,
        "rule": (
            None
            if proposal.kind not in (RULE, RULE_EDIT, RULE_DELETE)
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
        "new": (
            None
            if proposal.kind not in (GROUP, NEW_CATEGORY)
            else {
                "name": proposal.value,
                "group": proposal.group if proposal.kind == NEW_CATEGORY else None,
                "kind": (
                    group_kind_word(transfer=proposal.transfer, income=proposal.income)
                    if proposal.kind == GROUP
                    else None
                ),
                "sensitive": proposal.sensitive if proposal.kind == GROUP else None,
                "tax": proposal.tax if proposal.kind == NEW_CATEGORY else None,
            }
        ),
        "waits_for": waits_for(session, proposal),
        "rule_change": (
            None
            if proposal.kind not in (RULE_EDIT, RULE_DELETE)
            else {
                "rule_id": proposal.target_id,
                "before": proposal.before,
                "delete": proposal.kind == RULE_DELETE,
            }
        ),
        "finding": (
            None
            if proposal.kind != FINDING_STATUS
            else {
                "type": proposal.finding_type,
                "about": proposal.finding_subject or "",
                "month": (
                    "" if proposal.finding_month is None else proposal.finding_month.isoformat()[:7]
                ),
                "status": proposal.value,
            }
        ),
        "category_change": (
            None
            if proposal.kind not in (CATEGORY_RENAME, CATEGORY_DELETE)
            else {
                "name": proposal.before,
                "rename_to": proposal.value if proposal.kind == CATEGORY_RENAME else None,
                "delete": proposal.kind == CATEGORY_DELETE,
                "move_to": (
                    None
                    if proposal.kind != CATEGORY_DELETE or not proposal.value
                    else proposal.value
                ),
            }
        ),
        "reason": proposal.reason,
        "status": proposal.status,
        "created_at": proposal.created_at.isoformat(),
        "decided_at": iso(proposal.decided_at),
        "out_of_date": proposal_out_of_date(session, proposal),
    }
