"""Transactions gathered for a CSV export, one line per flow."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from finances.analysis.search import FoundTransaction, TransactionQuery, search_transactions
from finances.db.repositories import account_names, note_of, tags_for

_CHUNK = 500
_ALL = 1_000_000_000


@dataclass(frozen=True)
class ExportLine:
    found: FoundTransaction
    account: str
    tags: list[str]
    note: str | None


def transactions_for_export(session: Session, start: date, end: date) -> list[ExportLine]:
    if start > end:
        raise ValueError("the start date is after the end date")
    found = search_transactions(session, TransactionQuery(start=start, end=end, limit=_ALL))
    found.sort(
        key=lambda item: (
            item.transaction.posted_date,
            item.transaction.id,
            item.part or 0,
        )
    )
    ids = list(dict.fromkeys(item.transaction.id for item in found))
    names = account_names(session)
    tags: dict[int, list[str]] = {}
    notes: dict[int, str | None] = {}
    for index in range(0, len(ids), _CHUNK):
        chunk = ids[index : index + _CHUNK]
        tags.update(tags_for(session, chunk))
        for transaction_id in chunk:
            notes[transaction_id] = note_of(session, transaction_id)
    return [
        ExportLine(
            item,
            names[item.transaction.account_id],
            tags.get(item.transaction.id, []),
            notes.get(item.transaction.id),
        )
        for item in found
    ]
