"""Transfer pairs and the candidates waiting for review, as plain text."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from finances.categorize.transfers import transfer_suggestions
from finances.db.repositories import account_names, get_transaction, list_transfer_pairs
from finances.domain.money import format_cents


@dataclass(frozen=True)
class TransferLine:
    pair: str
    date: str
    from_account: str
    to_account: str
    amount: str
    out_id: str
    in_id: str
    how: str


@dataclass(frozen=True)
class SuggestionLine:
    out_id: str
    out_date: str
    from_account: str
    in_id: str
    in_date: str
    to_account: str
    amount: str


def transfer_lines(session: Session) -> list[TransferLine]:
    """One line per pair, latest outflow date first, then highest pair id first."""
    names = account_names(session)
    found = [
        (
            pair,
            get_transaction(session, pair.out_transaction_id),
            get_transaction(session, pair.in_transaction_id),
        )
        for pair in list_transfer_pairs(session)
    ]
    found.sort(key=lambda item: (item[1].posted_date, item[0].id), reverse=True)
    return [
        TransferLine(
            str(pair.id),
            out.posted_date.isoformat(),
            names[out.account_id],
            names[into.account_id],
            format_cents(into.amount_cents),
            str(out.id),
            str(into.id),
            pair.status,
        )
        for pair, out, into in found
    ]


def suggestion_lines(session: Session) -> list[SuggestionLine]:
    names = account_names(session)
    lines = []
    for out_id, in_id in transfer_suggestions(session):
        out = get_transaction(session, out_id)
        into = get_transaction(session, in_id)
        lines.append(
            SuggestionLine(
                str(out.id),
                out.posted_date.isoformat(),
                names[out.account_id],
                str(into.id),
                into.posted_date.isoformat(),
                names[into.account_id],
                format_cents(into.amount_cents),
            )
        )
    return lines
