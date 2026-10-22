"""Net worth over time from the stored accounts and snapshots."""

from datetime import date

from sqlalchemy.orm import Session

from finances.db.repositories import list_accounts, list_balance_snapshots
from finances.domain.networth import NetWorthPoint, net_worth_points, point_days


def net_worth_over_time(session: Session, today: date, months: int = 12) -> list[NetWorthPoint]:
    balances = []
    for account in list_accounts(session):
        snapshots = list_balance_snapshots(session, account.id)
        balances.append([(item.as_of_date, item.balance_cents) for item in snapshots])
    return net_worth_points(balances, point_days(today, months))
