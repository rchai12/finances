from sqlalchemy import (
    ColumnElement,
    delete,
    exists,
    or_,
    select,
)
from sqlalchemy.orm import Session

from finances.db.orm import (
    TransactionRow,
    TransferPairRow,
    TransferRejectionRow,
    to_transfer_pair,
)
from finances.db.repositories.audit import record_change
from finances.domain.audit import pair_text
from finances.domain.models import (
    AUTO,
    CONFIRMED,
    TransferPair,
)
from finances.domain.transfers import Movement


def _names(
    table: type[TransferPairRow] | type[TransferRejectionRow], transaction_id: object
) -> ColumnElement[bool]:
    """True for a pair or rejection with the transaction on either side."""
    return or_(
        table.out_transaction_id == transaction_id, table.in_transaction_id == transaction_id
    )


def list_transfer_movements(session: Session) -> list[Movement]:
    """Return each posted, non-zero transaction that is in no pair, in id order."""
    paired = exists().where(_names(TransferPairRow, TransactionRow.id))
    stmt = (
        select(
            TransactionRow.id,
            TransactionRow.account_id,
            TransactionRow.amount_cents,
            TransactionRow.posted_date,
        )
        .where(TransactionRow.is_pending.is_(False), TransactionRow.amount_cents != 0, ~paired)
        .order_by(TransactionRow.id)
    )
    return [Movement(*row) for row in session.execute(stmt).all()]


def list_transfer_rejections(session: Session) -> set[tuple[int, int]]:
    """Return the (out id, in id) of every pair said not to be a transfer."""
    stmt = select(TransferRejectionRow.out_transaction_id, TransferRejectionRow.in_transaction_id)
    return {(out_id, in_id) for out_id, in_id in session.execute(stmt).all()}


def list_transfer_pairs(session: Session) -> list[TransferPair]:
    """Return every transfer pair, in id order."""
    stmt = select(TransferPairRow).order_by(TransferPairRow.id)
    return [to_transfer_pair(row) for row in session.scalars(stmt).all()]


def find_transfer_pair(session: Session, transaction_id: int) -> TransferPair | None:
    """The pair holding this transaction on either side, or None."""
    stmt = select(TransferPairRow).where(_names(TransferPairRow, transaction_id))
    row = session.scalars(stmt).first()
    return to_transfer_pair(row) if row is not None else None


def _check_transfer(session: Session, out_id: int, in_id: int) -> None:
    """Refuse two transactions that cannot be one transfer."""
    out = session.get(TransactionRow, out_id)
    into = session.get(TransactionRow, in_id)
    if out is None or into is None:
        raise ValueError("transaction not found")
    if out.account_id == into.account_id:
        raise ValueError("a transfer goes from one account to another")
    if out.amount_cents >= 0 or into.amount_cents != -out.amount_cents:
        raise ValueError("a transfer pairs money out with the same amount in")


def _drop_rejection(session: Session, out_id: int, in_id: int) -> None:
    session.execute(
        delete(TransferRejectionRow).where(
            TransferRejectionRow.out_transaction_id == out_id,
            TransferRejectionRow.in_transaction_id == in_id,
        )
    )


def _store_rejection(session: Session, out_id: int, in_id: int) -> None:
    if (out_id, in_id) not in list_transfer_rejections(session):
        session.add(TransferRejectionRow(out_transaction_id=out_id, in_transaction_id=in_id))
    session.flush()


def create_transfer_pair(session: Session, out_id: int, in_id: int, status: str) -> TransferPair:
    """Pair an outflow with an inflow and return the pair. The caller commits."""
    _check_transfer(session, out_id, in_id)
    for transaction_id in (out_id, in_id):
        if find_transfer_pair(session, transaction_id) is not None:
            raise ValueError(f"transaction {transaction_id} is already in a transfer")
    if status not in (AUTO, CONFIRMED):
        raise ValueError("status must be auto or confirmed")
    _drop_rejection(session, out_id, in_id)
    row = TransferPairRow(out_transaction_id=out_id, in_transaction_id=in_id, status=status)
    session.add(row)
    session.flush()
    if status == CONFIRMED:
        record_change(
            session,
            action="transfer_confirmed",
            kind="transfer",
            record_id=row.id,
            after=pair_text(out_id, in_id),
        )
    return to_transfer_pair(row)


def reject_transfer(session: Session, out_id: int, in_id: int) -> None:
    """Record that two transactions are not a transfer, unpairing them. The caller commits."""
    _check_transfer(session, out_id, in_id)
    session.execute(
        delete(TransferPairRow).where(
            TransferPairRow.out_transaction_id == out_id,
            TransferPairRow.in_transaction_id == in_id,
        )
    )
    _store_rejection(session, out_id, in_id)
    record_change(
        session,
        action="transfer_rejected",
        kind="transaction",
        record_id=out_id,
        after=pair_text(out_id, in_id),
    )


def unpair_transfer(session: Session, pair_id: int) -> TransferPair:
    """Delete a pair and record it as rejected; return the pair. The caller commits."""
    row = session.get(TransferPairRow, pair_id)
    if row is None:
        raise ValueError("transfer not found")
    pair = to_transfer_pair(row)
    session.delete(row)
    session.flush()
    _store_rejection(session, pair.out_transaction_id, pair.in_transaction_id)
    record_change(
        session,
        action="transfer_unpaired",
        kind="transfer",
        record_id=pair.id,
        before=pair_text(pair.out_transaction_id, pair.in_transaction_id),
    )
    return pair
