"""The agent's read-only account tools. Each returns one JSON object."""

from typing import Annotated, Any

from pydantic import Field

import finances.clock as clock
from finances.analysis.balances import balance_report
from finances.analysis.networth import net_worth_over_time
from finances.db.repositories import list_account_owners, list_people
from finances.db.repositories import list_accounts as load_accounts
from finances.mcp_server.access import reading


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
