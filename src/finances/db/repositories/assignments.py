from collections.abc import Iterable

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from finances.db.orm import (
    CategoryRow,
    TransactionCategoryRow,
    TransactionRow,
    TransferPairRow,
    to_category,
    to_category_assignment,
    to_transaction,
)
from finances.db.repositories.audit import record_change
from finances.db.repositories.categories import _leaf_category
from finances.db.repositories.transactions import (
    _distinct_transaction_ids,
    _require_transaction,
)
from finances.db.repositories.transfers import _names
from finances.domain.models import (
    BY_RULE,
    MANUAL,
    Category,
    CategoryAssignment,
    CategoryRule,
    Transaction,
)


def list_category_assignments(session: Session) -> dict[int, CategoryAssignment]:
    """Map each categorized transaction's id to its assignment."""
    rows = session.scalars(select(TransactionCategoryRow)).all()
    return {row.transaction_id: to_category_assignment(row) for row in rows}


def _assignment_row(session: Session, transaction_id: int) -> TransactionCategoryRow | None:
    stmt = select(TransactionCategoryRow).where(
        TransactionCategoryRow.transaction_id == transaction_id
    )
    return session.scalars(stmt).first()


def _category_name(session: Session, category_id: int) -> str:
    row = session.get(CategoryRow, category_id)
    return row.name


def _assigned_name(session: Session, transaction_id: int) -> str | None:
    row = _assignment_row(session, transaction_id)
    if row is None:
        return None
    return _category_name(session, row.category_id)


def _assign(
    session: Session, transaction_id: int, category_id: int, source: str, rule_id: int | None
) -> None:
    row = _assignment_row(session, transaction_id)
    if row is None:
        row = TransactionCategoryRow(transaction_id=transaction_id)
        session.add(row)
    row.category_id = category_id
    row.source = source
    row.rule_id = rule_id
    session.flush()


def assign_by_rule(session: Session, transaction_id: int, rule: CategoryRule) -> None:
    """Store, or replace, the transaction's category as set by the rule. The caller commits."""
    _assign(session, transaction_id, rule.category_id, BY_RULE, rule.id)


def remove_category(session: Session, transaction_id: int) -> None:
    """Remove the transaction's category, if it has one. The caller commits."""
    row = _assignment_row(session, transaction_id)
    if row is not None:
        session.delete(row)
        session.flush()


def set_categories_by_hand(
    session: Session, transaction_ids: Iterable[int], category: str
) -> tuple[int, Category]:
    """Set each transaction's category by hand. The caller commits."""
    ids = _distinct_transaction_ids(transaction_ids)
    for transaction_id in ids:
        _require_transaction(session, transaction_id)
    target = _leaf_category(session, category)
    for transaction_id in ids:
        before = _assigned_name(session, transaction_id)
        _assign(session, transaction_id, target.id, MANUAL, None)
        if before != target.name:
            record_change(
                session,
                action="category_set",
                kind="transaction",
                record_id=transaction_id,
                before=before,
                after=target.name,
            )
    return len(ids), to_category(target)


def clear_categories_by_hand(session: Session, transaction_ids: Iterable[int]) -> int:
    """Remove each transaction's category. The caller commits and runs categorize."""
    ids = _distinct_transaction_ids(transaction_ids)
    for transaction_id in ids:
        _require_transaction(session, transaction_id)
    for transaction_id in ids:
        before = _assigned_name(session, transaction_id)
        remove_category(session, transaction_id)
        if before is not None:
            record_change(
                session,
                action="category_cleared",
                kind="transaction",
                record_id=transaction_id,
                before=before,
            )
    return len(ids)


def set_category_by_hand(session: Session, transaction_id: int, category: str) -> Category:
    """Set the transaction's category by hand, so rules leave it alone. The caller commits."""
    _require_transaction(session, transaction_id)
    target = _leaf_category(session, category)
    before = _assigned_name(session, transaction_id)
    _assign(session, transaction_id, target.id, MANUAL, None)
    if before != target.name:
        record_change(
            session,
            action="category_set",
            kind="transaction",
            record_id=transaction_id,
            before=before,
            after=target.name,
        )
    return to_category(target)


def clear_category_by_hand(session: Session, transaction_id: int) -> None:
    """Remove the transaction's category, leaving it to the rules. The caller commits."""
    _require_transaction(session, transaction_id)
    before = _assigned_name(session, transaction_id)
    remove_category(session, transaction_id)
    if before is not None:
        record_change(
            session,
            action="category_cleared",
            kind="transaction",
            record_id=transaction_id,
            before=before,
        )


def list_uncategorized(session: Session, limit: int) -> list[Transaction]:
    """Return transactions without a category, latest posted date first, at most limit."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    categorized = exists().where(TransactionCategoryRow.transaction_id == TransactionRow.id)
    paired = exists().where(_names(TransferPairRow, TransactionRow.id))
    stmt = (
        select(TransactionRow)
        .where(~categorized, ~paired)
        .order_by(TransactionRow.posted_date.desc(), TransactionRow.id.desc())
        .limit(limit)
    )
    return [to_transaction(row) for row in session.scalars(stmt).all()]


def count_uncategorized(session: Session) -> int:
    """How many transactions have no category and are in no transfer pair."""
    categorized = exists().where(TransactionCategoryRow.transaction_id == TransactionRow.id)
    paired = exists().where(_names(TransferPairRow, TransactionRow.id))
    return (
        session.scalar(
            select(func.count()).select_from(TransactionRow).where(~categorized, ~paired)
        )
        or 0
    )
