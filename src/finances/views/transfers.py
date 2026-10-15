"""Transfer pairs and the candidates waiting for review, as plain text."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from finances.categorize.transfers import transfer_suggestions
from finances.db.repositories import (
    account_names,
    find_transfer_pair,
    get_transaction,
    list_transfer_pairs,
)
from finances.domain.models import TransferPair
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


def _line(session: Session, pair: TransferPair, names: dict[int, str]) -> TransferLine:
    out = get_transaction(session, pair.out_transaction_id)
    into = get_transaction(session, pair.in_transaction_id)
    return TransferLine(
        str(pair.id),
        out.posted_date.isoformat(),
        names[out.account_id],
        names[into.account_id],
        format_cents(into.amount_cents),
        str(out.id),
        str(into.id),
        pair.status,
    )


def transfer_lines(session: Session) -> list[TransferLine]:
    """One line per pair, latest outflow date first, then highest pair id first."""
    names = account_names(session)
    lines = [_line(session, pair, names) for pair in list_transfer_pairs(session)]
    return sorted(lines, key=lambda line: (line.date, int(line.pair)), reverse=True)


def transfer_of(session: Session, transaction_id: int) -> TransferLine | None:
    """The line of the pair holding this transaction, as transfer_lines would show it, or None."""
    pair = find_transfer_pair(session, transaction_id)
    if pair is None:
        return None
    return _line(session, pair, account_names(session))


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
