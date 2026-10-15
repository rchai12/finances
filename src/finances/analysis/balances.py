"""What the household has: each active account's newest balance, and the net worth."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from finances.db.repositories import latest_balance, list_accounts
from finances.domain.models import AccountType


@dataclass(frozen=True)
class BalanceLine:
    account: str
    type: str
    balance_cents: int | None
    as_of: date | None
    source: str | None


@dataclass(frozen=True)
class BalanceReport:
    lines: list[BalanceLine]
    cash_cents: int
    cards_cents: int
    other_cents: int
    net_worth_cents: int
    without_balance: list[str]


def _total(lines: Iterable[BalanceLine], types: Iterable[AccountType]) -> int:
    kinds = {kind.value for kind in types}
    return sum(
        line.balance_cents
        for line in lines
        if line.type in kinds and line.balance_cents is not None
    )


def balance_report(session: Session) -> BalanceReport:
    lines = []
    for account in list_accounts(session):
        snapshot = latest_balance(session, account.id)
        lines.append(
            BalanceLine(
                account=account.name,
                type=account.type.value,
                balance_cents=None if snapshot is None else snapshot.balance_cents,
                as_of=None if snapshot is None else snapshot.as_of_date,
                source=None if snapshot is None else snapshot.source.value,
            )
        )
    cash = _total(lines, (AccountType.CHECKING, AccountType.SAVINGS))
    cards = _total(lines, (AccountType.CREDIT_CARD,))
    other = _total(lines, (AccountType.OTHER,))
    return BalanceReport(
        lines=lines,
        cash_cents=cash,
        cards_cents=cards,
        other_cents=other,
        net_worth_cents=cash + cards + other,
        without_balance=[line.account for line in lines if line.balance_cents is None],
    )
