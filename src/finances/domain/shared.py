"""Who owes whom for a shared expense. Imports only from finances.domain."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

ZERO = "a transaction of zero cannot be shared"
SIZE = "a share must be more than zero and at most the transaction's amount"


@dataclass(frozen=True)
class Share:
    transaction_id: int
    payer: str
    debtor: str
    owed_cents: int


@dataclass(frozen=True)
class Settlement:
    id: int
    payer: str
    payee: str
    amount_cents: int
    day: date


@dataclass(frozen=True)
class Owed:
    debtor: str
    creditor: str
    cents: int


def half_share(amount_cents: int) -> int:
    if amount_cents == 0:
        raise ValueError(ZERO)
    size = abs(amount_cents) // 2
    return size if amount_cents < 0 else -size


def signed_share(amount_cents: int, size_cents: int) -> int:
    if amount_cents == 0:
        raise ValueError(ZERO)
    if size_cents <= 0 or size_cents > abs(amount_cents):
        raise ValueError(SIZE)
    return size_cents if amount_cents < 0 else -size_cents


def balances(shares: Iterable[Share], settlements: Iterable[Settlement]) -> list[Owed]:
    net: dict[tuple[str, str], int] = defaultdict(int)
    for share in shares:
        net[(share.debtor, share.payer)] += share.owed_cents
    for settlement in settlements:
        net[(settlement.payer, settlement.payee)] -= settlement.amount_cents
    collapsed: dict[tuple[str, str], int] = {}
    for (debtor, creditor), cents in net.items():
        low, high = (debtor, creditor) if debtor < creditor else (creditor, debtor)
        signed = cents if debtor < creditor else -cents
        collapsed[(low, high)] = collapsed.get((low, high), 0) + signed
    owed = []
    for (low, high), cents in collapsed.items():
        if cents > 0:
            owed.append(Owed(low, high, cents))
        elif cents < 0:
            owed.append(Owed(high, low, -cents))
    return sorted(owed, key=lambda item: (item.debtor, item.creditor))
