"""A 30-day forecast for each account from that account's own series."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from finances.analysis.spending import load_flows
from finances.db.repositories import get_account_by_name, list_accounts, list_balance_snapshots
from finances.domain.forecast import Walk, walk
from finances.domain.models import Account
from finances.domain.recurring import Charge, find_recurring, find_recurring_income
from finances.domain.spending import INCOME, SPENDING, TRANSFER, UNSORTED_IN, Flow
from finances.domain.upcoming import Upcoming, expected


@dataclass(frozen=True)
class AccountForecast:
    account: str
    balance_cents: int
    balance_day: date
    walk: Walk


@dataclass(frozen=True)
class ForecastReport:
    start: date
    end: date
    accounts: list[AccountForecast]
    no_balance: list[str]


def _start_balance(session: Session, account_id: int, start: date) -> tuple[int, date] | None:
    for snapshot in list_balance_snapshots(session, account_id):
        if snapshot.as_of_date <= start:
            return snapshot.balance_cents, snapshot.as_of_date
    return None


def _items(flows: Iterable[Flow], account: str, start: date, days: int) -> list[Upcoming]:
    own = [flow for flow in flows if flow.account == account]
    bills = find_recurring(
        (
            Charge(flow.merchant, flow.day, flow.amount_cents)
            for flow in own
            if flow.kind in (SPENDING, TRANSFER) and flow.amount_cents < 0
        ),
        start,
    )
    income = find_recurring_income(
        (
            Charge(flow.merchant, flow.day, flow.amount_cents)
            for flow in own
            if flow.kind in (INCOME, UNSORTED_IN, TRANSFER) and flow.amount_cents > 0
        ),
        start,
    )
    return expected(bills, income, start, days)


def _forecast(
    session: Session, account: Account, start: date, days: int, flows: list[Flow]
) -> AccountForecast | None:
    found = _start_balance(session, account.id, start)
    if found is None:
        return None
    cents, day = found
    return AccountForecast(
        account=account.name,
        balance_cents=cents,
        balance_day=day,
        walk=walk(cents, start, _items(flows, account.name, start, days)),
    )


def forecast_report(
    session: Session, start: date, days: int = 30, account: str | None = None
) -> ForecastReport:
    end = start + timedelta(days=days - 1)
    flows = load_flows(session, date.min, start)
    if account is not None:
        found = get_account_by_name(session, account)
        if found is None:
            raise ValueError("account not found")
        forecast = _forecast(session, found, start, days, flows)
        if forecast is None:
            raise ValueError(f"{found.name} has no balance yet")
        return ForecastReport(start, end, [forecast], [])
    accounts: list[AccountForecast] = []
    no_balance: list[str] = []
    for item in list_accounts(session):
        forecast = _forecast(session, item, start, days, flows)
        if forecast is None:
            no_balance.append(item.name)
        else:
            accounts.append(forecast)
    return ForecastReport(start, end, accounts, no_balance)
