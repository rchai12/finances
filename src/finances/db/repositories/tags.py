from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finances.db.orm import TransactionNoteRow, TransactionTagRow
from finances.db.repositories.audit import record_change
from finances.db.repositories.transactions import (
    _distinct_transaction_ids,
    _require_transaction,
)
from finances.domain.tags import TagCount, clean_note, normalize_tag


def add_tags(session: Session, transaction_ids: Iterable[int], tag: str) -> tuple[int, str]:
    ids = _distinct_transaction_ids(transaction_ids)
    for transaction_id in ids:
        _require_transaction(session, transaction_id)
    stored = normalize_tag(tag)
    for transaction_id in ids:
        if _tag_row(session, transaction_id, stored) is None:
            session.add(TransactionTagRow(transaction_id=transaction_id, tag=stored))
            session.flush()
            record_change(
                session,
                action="tag_added",
                kind="transaction",
                record_id=transaction_id,
                after=stored,
            )
    return len(ids), stored


def remove_tags(session: Session, transaction_ids: Iterable[int], tag: str) -> tuple[int, str]:
    ids = _distinct_transaction_ids(transaction_ids)
    for transaction_id in ids:
        _require_transaction(session, transaction_id)
    stored = normalize_tag(tag)
    for transaction_id in ids:
        row = _tag_row(session, transaction_id, stored)
        if row is not None:
            session.delete(row)
            session.flush()
            record_change(
                session,
                action="tag_removed",
                kind="transaction",
                record_id=transaction_id,
                before=stored,
            )
    return len(ids), stored


def tags_for(session: Session, transaction_ids: Iterable[int]) -> dict[int, list[str]]:
    ids = list(transaction_ids)
    if not ids:
        return {}
    stmt = (
        select(TransactionTagRow)
        .where(TransactionTagRow.transaction_id.in_(ids))
        .order_by(TransactionTagRow.tag)
    )
    found: dict[int, list[str]] = {}
    for row in session.scalars(stmt):
        found.setdefault(row.transaction_id, []).append(row.tag)
    return found


def list_tags(session: Session) -> list[TagCount]:
    stmt = (
        select(TransactionTagRow.tag, func.count())
        .group_by(TransactionTagRow.tag)
        .order_by(TransactionTagRow.tag)
    )
    return [TagCount(tag, count) for tag, count in session.execute(stmt)]


def set_note(session: Session, transaction_id: int, text: str) -> str | None:
    _require_transaction(session, transaction_id)
    cleaned = clean_note(text)
    row = _note_row(session, transaction_id)
    if cleaned == "":
        if row is None:
            return None
        before = row.text
        session.delete(row)
        session.flush()
        record_change(
            session,
            action="note_cleared",
            kind="transaction",
            record_id=transaction_id,
            before=before,
        )
        return None
    if row is None:
        session.add(TransactionNoteRow(transaction_id=transaction_id, text=cleaned))
        session.flush()
        record_change(
            session,
            action="note_set",
            kind="transaction",
            record_id=transaction_id,
            after=cleaned,
        )
        return cleaned
    if row.text == cleaned:
        return cleaned
    before = row.text
    row.text = cleaned
    session.flush()
    record_change(
        session,
        action="note_set",
        kind="transaction",
        record_id=transaction_id,
        before=before,
        after=cleaned,
    )
    return cleaned


def note_of(session: Session, transaction_id: int) -> str | None:
    row = _note_row(session, transaction_id)
    return None if row is None else row.text


def _tag_row(session: Session, transaction_id: int, tag: str) -> TransactionTagRow | None:
    stmt = select(TransactionTagRow).where(
        TransactionTagRow.transaction_id == transaction_id, TransactionTagRow.tag == tag
    )
    return session.scalars(stmt).first()


def _note_row(session: Session, transaction_id: int) -> TransactionNoteRow | None:
    stmt = select(TransactionNoteRow).where(TransactionNoteRow.transaction_id == transaction_id)
    return session.scalars(stmt).first()
