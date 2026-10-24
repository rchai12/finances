"""One transaction, as `fin transactions list` and the Transactions page show it."""

from dataclasses import dataclass, replace

from finances.analysis.search import FoundTransaction
from finances.domain.models import Transaction
from finances.domain.money import format_cents
from finances.domain.spending import UNASSIGNED, UNCATEGORIZED, is_refund
from finances.domain.splits import SplitPart
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


def found_rows(
    found: list[FoundTransaction], names: dict[int, str]
) -> list[tuple[int, TransactionRow, str, bool, int | None]]:
    """Each found transaction as its id, row, category, refund flag, and part."""
    return [
        (
            item.transaction.id,
            replace(
                transaction_row(
                    item.transaction,
                    None if item.flow.person == UNASSIGNED else item.flow.person,
                    names,
                ),
                amount=format_cents(item.flow.amount_cents),
            ),
            "" if item.flow.category == UNCATEGORIZED else item.flow.category,
            is_refund(item.flow),
            item.part,
        )
        for item in found
    ]


@dataclass(frozen=True)
class PartLine:
    part: str
    amount: str
    category: str


def part_lines(parts: list[SplitPart], names: dict[int, str]) -> list[PartLine]:
    return [
        PartLine(str(part.position), format_cents(part.amount_cents), names[part.category_id])
        for part in parts
    ]
