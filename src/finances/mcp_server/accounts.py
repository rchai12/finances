"""Read-only MCP accounts adapters."""

from typing import Annotated, Any

from pydantic import Field

import finances.clock as clock
from finances.analysis.balances import balance_report
from finances.analysis.listings import account_listing
from finances.analysis.networth import net_worth_over_time
from finances.mcp_server.access import reading


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
