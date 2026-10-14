"""One transaction, as `fin transactions list` and the Transactions page show it."""

from dataclasses import dataclass

from finances.domain.models import Transaction
from finances.domain.money import format_cents
from finances.views.format import mask_last4


@dataclass(frozen=True)
class TransactionRow:
    date: str
    account: str
    description: str
    amount: str
    card: str
    section: str
    person: str


def transaction_row(item: Transaction, person: str | None, names: dict[int, str]) -> TransactionRow:
    return TransactionRow(
        item.posted_date.isoformat(),
        names[item.account_id],
        item.description,
        format_cents(item.amount_cents),
        mask_last4(item.card_last4),
        item.section or "",
        person or "",
    )
