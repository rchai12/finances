"""One account's spending, months, balances, and latest transactions."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from finances.analysis.people import load_attribution
from finances.analysis.search import FoundTransaction, TransactionQuery, search_transactions
from finances.analysis.spending import load_flows
from finances.db.repositories import list_balance_snapshots, list_transactions
from finances.domain.models import Account, BalanceSnapshot
from finances.domain.periods import months_ending
from finances.domain.spending import Flow, SpendingLine, month_bounds, spending_lines, summarize


@dataclass(frozen=True)
class AccountMonth:
    start: date
    spent_cents: int
    income_cents: int


@dataclass(frozen=True)
class AccountPage:
    account: Account
    owner: str | None
    card: str
    cards: list[str]
    spending: list[SpendingLine]
    months: list[AccountMonth]
    balances: list[BalanceSnapshot]
    latest: list[FoundTransaction]


def _cards(session: Session, account_id: int) -> list[str]:
    rows = list_transactions(session, account_id, limit=10_000)
    return sorted({item.card_last4 for item in rows if item.card_last4})


def _for_account(flows: list[Flow], account_name: str, card: str) -> list[Flow]:
    kept = [flow for flow in flows if flow.account == account_name]
    if card:
        kept = [flow for flow in kept if flow.card == card]
    return kept


def account_page(
    session: Session, account: Account, card: str, start: date, end: date, today: date
) -> AccountPage:
    """Spending for the month, twelve months, balances, and the latest fifty transactions."""
    cards = _cards(session, account.id)
    if card and card not in cards:
        raise ValueError("card not found")
    window = months_ending(today, 12)
    flow_end = max(end, month_bounds(today)[1])
    flows = _for_account(load_flows(session, window[0][0], flow_end), account.name, card)
    in_month = [flow for flow in flows if start <= flow.day <= end]
    months = []
    for month_start, month_end in window:
        summary = summarize(flow for flow in flows if month_start <= flow.day <= month_end)
        months.append(AccountMonth(month_start, summary.spent_cents, summary.income_cents))
    return AccountPage(
        account=account,
        owner=load_attribution(session).owner(account.id),
        card=card,
        cards=cards,
        spending=spending_lines(in_month, "group"),
        months=months,
        balances=list_balance_snapshots(session, account.id),
        latest=search_transactions(
            session, TransactionQuery(account=account.name, card=card, limit=50)
        ),
    )
