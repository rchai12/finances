from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from finances.db.orm import SettlementRow, SharedExpenseRow, TransactionRow
from finances.db.repositories.audit import record_change
from finances.db.repositories.people import (
    get_person_by_name,
    list_account_owners,
    list_cardholder_aliases,
    list_people,
)
from finances.db.repositories.transactions import _require_transaction
from finances.domain.people import JOINT, person_for
from finances.domain.shared import Settlement, Share, half_share, signed_share

JOINT_PAYER = "say who paid: this transaction is joint or has no owner"


def _people_names(session: Session) -> dict[int, str]:
    return {person.id: person.name for person in list_people(session)}


def _share_row(session: Session, transaction_id: int) -> SharedExpenseRow | None:
    stmt = select(SharedExpenseRow).where(SharedExpenseRow.transaction_id == transaction_id)
    return session.scalars(stmt).first()


def _is_shared(session: Session, transaction_id: int) -> bool:
    return _share_row(session, transaction_id) is not None


def _owes_text(debtor: str, payer: str) -> str:
    return f"{debtor} owes {payer}"


def _paid_text(payer: str, payee: str) -> str:
    return f"{payer} paid {payee}"


def _share_text(session: Session, transaction_id: int) -> str | None:
    row = _share_row(session, transaction_id)
    if row is None:
        return None
    names = _people_names(session)
    return _owes_text(names[row.debtor_id], names[row.payer_id])


def _delete_share(session: Session, transaction_id: int) -> None:
    session.execute(
        delete(SharedExpenseRow).where(SharedExpenseRow.transaction_id == transaction_id)
    )
    session.flush()


def _to_share(row: SharedExpenseRow, names: dict[int, str]) -> Share:
    return Share(row.transaction_id, names[row.payer_id], names[row.debtor_id], row.owed_cents)


def _to_settlement(row: SettlementRow, names: dict[int, str]) -> Settlement:
    return Settlement(row.id, names[row.payer_id], names[row.payee_id], row.amount_cents, row.day)


def _payer_of(session: Session, row: TransactionRow, payer: str) -> tuple[int, str]:
    named = payer.strip()
    if named:
        found_payer = get_person_by_name(session, named)
        if found_payer is None:
            raise ValueError("person not found")
        return found_payer.id, found_payer.name
    names = _people_names(session)
    owners = {
        account_id: JOINT if person_id is None else names[person_id]
        for account_id, person_id in list_account_owners(session).items()
    }
    aliases = {
        cardholder: names[person_id]
        for cardholder, person_id in list_cardholder_aliases(session).items()
    }
    found = person_for(row.cardholder, owners.get(row.account_id), aliases)
    if found is None or found == JOINT:
        raise ValueError(JOINT_PAYER)
    found_payer = get_person_by_name(session, found)
    assert found_payer is not None
    return found_payer.id, found_payer.name


def share_transaction(
    session: Session,
    transaction_id: int,
    debtor: str,
    *,
    payer: str = "",
    size_cents: int | None = None,
) -> Share:
    """Replace the transaction's share. The caller commits."""
    from finances.db.repositories.transfers import find_transfer_pair

    _require_transaction(session, transaction_id)
    row = session.get(TransactionRow, transaction_id)
    assert row is not None
    if row.is_pending:
        raise ValueError("a pending transaction cannot be shared")
    if find_transfer_pair(session, transaction_id) is not None:
        raise ValueError("a transfer cannot be shared")
    payer_id, payer_name = _payer_of(session, row, payer)
    found_debtor = get_person_by_name(session, debtor)
    if found_debtor is None:
        raise ValueError("person not found")
    if found_debtor.name == payer_name:
        raise ValueError("a person cannot owe themselves")
    owed = (
        half_share(row.amount_cents)
        if size_cents is None
        else signed_share(row.amount_cents, size_cents)
    )
    before = _share_text(session, transaction_id)
    _delete_share(session, transaction_id)
    session.add(
        SharedExpenseRow(
            transaction_id=transaction_id,
            payer_id=payer_id,
            debtor_id=found_debtor.id,
            owed_cents=owed,
        )
    )
    session.flush()
    after = _owes_text(found_debtor.name, payer_name)
    record_change(
        session,
        action="share_set",
        kind="transaction",
        record_id=transaction_id,
        before=before,
        after=after,
    )
    return Share(transaction_id, payer_name, found_debtor.name, owed)


def unshare_transaction(session: Session, transaction_id: int) -> None:
    """Remove the transaction's share. The caller commits."""
    _require_transaction(session, transaction_id)
    if not _is_shared(session, transaction_id):
        raise ValueError("the transaction is not shared")
    before = _share_text(session, transaction_id)
    _delete_share(session, transaction_id)
    record_change(
        session,
        action="share_cleared",
        kind="transaction",
        record_id=transaction_id,
        before=before,
    )


def list_shares(session: Session) -> list[Share]:
    """Return every share, by transaction id."""
    names = _people_names(session)
    stmt = select(SharedExpenseRow).order_by(SharedExpenseRow.transaction_id)
    return [_to_share(row, names) for row in session.scalars(stmt).all()]


def share_of(session: Session, transaction_id: int) -> Share | None:
    """Return the transaction's share, or None."""
    row = _share_row(session, transaction_id)
    if row is None:
        return None
    return _to_share(row, _people_names(session))


def record_settlement(
    session: Session, payer: str, payee: str, amount_cents: int, day: date
) -> Settlement:
    """Store a settlement. The caller commits."""
    found_payer = get_person_by_name(session, payer)
    if found_payer is None:
        raise ValueError("person not found")
    found_payee = get_person_by_name(session, payee)
    if found_payee is None:
        raise ValueError("person not found")
    if found_payer.id == found_payee.id:
        raise ValueError("a person cannot pay themselves")
    if amount_cents <= 0:
        raise ValueError("a settlement must be more than zero")
    row = SettlementRow(
        payer_id=found_payer.id,
        payee_id=found_payee.id,
        amount_cents=amount_cents,
        day=day,
    )
    session.add(row)
    session.flush()
    after = _paid_text(found_payer.name, found_payee.name)
    record_change(
        session,
        action="settlement_added",
        kind="settlement",
        record_id=row.id,
        after=after,
    )
    return _to_settlement(row, {found_payer.id: found_payer.name, found_payee.id: found_payee.name})


def delete_settlement(session: Session, settlement_id: int) -> Settlement:
    """Delete a settlement and return it. The caller commits."""
    row = session.get(SettlementRow, settlement_id)
    if row is None:
        raise ValueError("settlement not found")
    names = _people_names(session)
    found = _to_settlement(row, names)
    before = _paid_text(found.payer, found.payee)
    session.delete(row)
    session.flush()
    record_change(
        session,
        action="settlement_deleted",
        kind="settlement",
        record_id=settlement_id,
        before=before,
    )
    return found


def list_settlements(session: Session) -> list[Settlement]:
    """Return every settlement, by day, then id."""
    names = _people_names(session)
    stmt = select(SettlementRow).order_by(SettlementRow.day, SettlementRow.id)
    return [_to_settlement(row, names) for row in session.scalars(stmt).all()]
