from collections.abc import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from finances.db.orm import CategoryRow, TransactionRow, TransactionSplitRow, to_split_part
from finances.db.repositories.audit import record_change
from finances.db.repositories.categories import _leaf_category
from finances.db.repositories.transactions import _require_transaction
from finances.domain.splits import SplitPart, check_split, signed_parts


def _is_split(session: Session, transaction_id: int) -> bool:
    stmt = select(TransactionSplitRow.id).where(
        TransactionSplitRow.transaction_id == transaction_id
    )
    return session.scalars(stmt).first() is not None


def _split_names(session: Session, transaction_id: int) -> str | None:
    parts = splits_for(session, [transaction_id]).get(transaction_id)
    if not parts:
        return None
    names = []
    for part in parts:
        row = session.get(CategoryRow, part.category_id)
        assert row is not None
        names.append(row.name)
    return ", ".join(names)


def _delete_parts(session: Session, transaction_id: int) -> None:
    session.execute(
        delete(TransactionSplitRow).where(TransactionSplitRow.transaction_id == transaction_id)
    )
    session.flush()


def set_split(
    session: Session, transaction_id: int, parts: Sequence[tuple[int, str]]
) -> list[SplitPart]:
    """Replace the transaction's parts with these, each a signed amount and a category."""
    from finances.db.repositories.assignments import remove_category
    from finances.db.repositories.transfers import find_transfer_pair

    _require_transaction(session, transaction_id)
    row = session.get(TransactionRow, transaction_id)
    assert row is not None
    if row.is_pending:
        raise ValueError("a pending transaction cannot be split")
    if find_transfer_pair(session, transaction_id) is not None:
        raise ValueError("a transfer cannot be split")
    check_split(row.amount_cents, [cents for cents, _name in parts])
    leaves = [_leaf_category(session, name) for _cents, name in parts]
    before = _split_names(session, transaction_id)
    _delete_parts(session, transaction_id)
    for position, ((cents, _name), leaf) in enumerate(zip(parts, leaves, strict=True), start=1):
        session.add(
            TransactionSplitRow(
                transaction_id=transaction_id,
                position=position,
                amount_cents=cents,
                category_id=leaf.id,
            )
        )
    session.flush()
    remove_category(session, transaction_id)
    record_change(
        session,
        action="split_set",
        kind="transaction",
        record_id=transaction_id,
        before=before,
        after=", ".join(leaf.name for leaf in leaves),
    )
    return splits_for(session, [transaction_id])[transaction_id]


def clear_split(session: Session, transaction_id: int) -> None:
    """Remove the transaction's parts. The caller commits and runs the rules."""
    _require_transaction(session, transaction_id)
    if not _is_split(session, transaction_id):
        raise ValueError("the transaction is not split")
    before = _split_names(session, transaction_id)
    _delete_parts(session, transaction_id)
    record_change(
        session,
        action="split_cleared",
        kind="transaction",
        record_id=transaction_id,
        before=before,
    )


def split_by_sizes(
    session: Session, transaction_id: int, parts: Sequence[tuple[int, str]]
) -> list[SplitPart]:
    """Sign each size as the transaction is, then store the parts. The caller commits."""
    _require_transaction(session, transaction_id)
    row = session.get(TransactionRow, transaction_id)
    assert row is not None
    signed = signed_parts(row.amount_cents, [size for size, _name in parts])
    return set_split(
        session, transaction_id, list(zip(signed, [name for _size, name in parts], strict=True))
    )


def splits_for(session: Session, transaction_ids: Iterable[int]) -> dict[int, list[SplitPart]]:
    """Map each named transaction that is split to its parts, by position."""
    ids = list(transaction_ids)
    if not ids:
        return {}
    stmt = (
        select(TransactionSplitRow)
        .where(TransactionSplitRow.transaction_id.in_(ids))
        .order_by(TransactionSplitRow.transaction_id, TransactionSplitRow.position)
    )
    found: dict[int, list[SplitPart]] = {}
    for row in session.scalars(stmt):
        found.setdefault(row.transaction_id, []).append(to_split_part(row))
    return found
