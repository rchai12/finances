"""Shared expenses as plain text for the terminal."""

from dataclasses import dataclass

from finances.domain.money import format_cents
from finances.domain.shared import Owed, Settlement, Share


@dataclass(frozen=True)
class ShareRow:
    id: str
    paid_by: str
    owes: str
    owed: str


@dataclass(frozen=True)
class SettlementRow:
    id: str
    date: str
    payer: str
    payee: str
    amount: str


def share_text(share: Share) -> str:
    if share.owed_cents >= 0:
        debtor, creditor, cents = share.debtor, share.payer, share.owed_cents
    else:
        debtor, creditor, cents = share.payer, share.debtor, -share.owed_cents
    return f"Transaction {share.transaction_id}: {debtor} owes {creditor} {format_cents(cents)}."


def share_rows(shares: list[Share]) -> list[ShareRow]:
    return [
        ShareRow(
            id=str(share.transaction_id),
            paid_by=share.payer,
            owes=share.debtor,
            owed=format_cents(share.owed_cents),
        )
        for share in shares
    ]


def owed_text(owed: Owed) -> str:
    return f"{owed.debtor} owes {owed.creditor} {format_cents(owed.cents)}."


def settlement_text(settlement: Settlement) -> str:
    paid = format_cents(settlement.amount_cents)
    return f"{settlement.payer} paid {settlement.payee} {paid} on {settlement.day.isoformat()}."


def settlement_rows(settlements: list[Settlement]) -> list[SettlementRow]:
    return [
        SettlementRow(
            id=str(settlement.id),
            date=settlement.day.isoformat(),
            payer=settlement.payer,
            payee=settlement.payee,
            amount=format_cents(settlement.amount_cents),
        )
        for settlement in settlements
    ]
