"""The agent's read-only tools. Each returns one JSON object."""

from datetime import date
from typing import Annotated, Any, Literal

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

import finances.clock as clock
from finances.analysis.balances import balance_report
from finances.analysis.months import month_report
from finances.analysis.networth import net_worth_over_time
from finances.analysis.search import FoundTransaction, TransactionQuery, search_transactions
from finances.analysis.spending import spending_report
from finances.db.repositories import account_names, list_account_owners, list_people
from finances.db.repositories import list_accounts as load_accounts
from finances.domain.spending import UNASSIGNED, UNCATEGORIZED, is_refund, month_bounds, month_range
from finances.mcp_server.access import reading

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
