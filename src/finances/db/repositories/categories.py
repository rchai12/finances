from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import (
    delete,
    exists,
    func,
    select,
    update,
)
from sqlalchemy.orm import Session

from finances.db.orm import (
    BudgetRow,
    CategoryRow,
    CategoryRuleRow,
    TransactionCategoryRow,
    TransactionRow,
    TransferPairRow,
    to_category,
    to_category_assignment,
    to_category_rule,
    to_transaction,
)
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
from finances.domain.rules import (
    MATCHES,
    normalize_pattern,
)
from finances.domain.text import (
    CATEGORY_NAME_LIMIT,
    RULE_PATTERN_LIMIT,
)


class CategoryExistsError(Exception):
    """Raised when a group or category with the same name already exists."""


def list_categories(session: Session) -> list[Category]:
    """Return every group and category, sorted by name without regard to case, then by id."""
    stmt = select(CategoryRow).order_by(func.lower(CategoryRow.name), CategoryRow.id)
    return [to_category(row) for row in session.scalars(stmt).all()]


def _category_row(session: Session, name: str) -> CategoryRow | None:
    stmt = select(CategoryRow).where(func.lower(CategoryRow.name) == name.strip().lower())
    return session.scalars(stmt).first()


def get_category_by_name(session: Session, name: str) -> Category | None:
    """Return the group or category with this name, ignoring case and outer spaces, or None."""
    row = _category_row(session, name)
    return to_category(row) if row is not None else None


def create_category(session: Session, name: str, group: str) -> Category:
    """Add a category under a group, with the group's flags, and return it. The caller commits."""
    clean = name.strip()
    if not 1 <= len(clean) <= CATEGORY_NAME_LIMIT:
        raise ValueError(f"a category name must be 1 to {CATEGORY_NAME_LIMIT} characters")
    parent = _category_row(session, group)
    if parent is None or parent.parent_id is not None:
        raise ValueError("group not found")
    if _category_row(session, clean) is not None:
        raise CategoryExistsError("a category with this name already exists")
    row = CategoryRow(
        name=clean,
        parent_id=parent.id,
        is_transfer=parent.is_transfer,
        is_income=parent.is_income,
        is_sensitive=parent.is_sensitive,
    )
    session.add(row)
    session.flush()
    return to_category(row)


def _leaf_category(session: Session, name: str) -> CategoryRow:
    """Return the category with this name, refusing a group or an unknown name."""
    row = _category_row(session, name)
    if row is None:
        raise ValueError("category not found")
    if row.parent_id is None:
        raise ValueError("rules and transactions take a category, not a group")
    return row


def list_rules(session: Session) -> list[CategoryRule]:
    """Return every rule in the order they are tried: highest priority first, then by id."""
    stmt = select(CategoryRuleRow).order_by(CategoryRuleRow.priority.desc(), CategoryRuleRow.id)
    return [to_category_rule(row) for row in session.scalars(stmt).all()]


def create_rule(
    session: Session, pattern: str, category: str, match: str = "contains", priority: int = 0
) -> CategoryRule:
    """Add a rule with its pattern normalized and return it. The caller commits."""
    clean = normalize_pattern(pattern)
    if not 1 <= len(clean) <= RULE_PATTERN_LIMIT:
        raise ValueError(f"a rule pattern must be 1 to {RULE_PATTERN_LIMIT} characters")
    if match not in MATCHES:
        raise ValueError(f"match must be one of: {', '.join(MATCHES)}")
    target = _leaf_category(session, category)
    taken = select(CategoryRuleRow).where(
        CategoryRuleRow.match == match, CategoryRuleRow.pattern == clean
    )
    if session.scalars(taken).first() is not None:
        raise ValueError("a rule with this pattern and match already exists")
    row = CategoryRuleRow(pattern=clean, match=match, priority=priority, category_id=target.id)
    session.add(row)
    session.flush()
    return to_category_rule(row)


def delete_rule(session: Session, rule_id: int) -> None:
    """Delete a rule and the assignments it set. The caller commits."""
    row = session.get(CategoryRuleRow, rule_id)
    if row is None:
        raise ValueError("rule not found")
    session.execute(delete(TransactionCategoryRow).where(TransactionCategoryRow.rule_id == rule_id))
    session.delete(row)
    session.flush()


@dataclass(frozen=True)
class CategoryDeletion:
    name: str
    was_group: bool
    moved_to: str | None
    transactions: int
    rules: int


def rename_category(session: Session, name: str, new_name: str) -> tuple[str, Category]:
    """Rename a group or category; return its old name and the renamed row. The caller commits."""
    row = _category_row(session, name)
    if row is None:
        raise ValueError("category not found")
    clean = new_name.strip()
    if not 1 <= len(clean) <= CATEGORY_NAME_LIMIT:
        raise ValueError(f"a category name must be 1 to {CATEGORY_NAME_LIMIT} characters")
    other = _category_row(session, clean)
    if other is not None and other.id != row.id:
        raise CategoryExistsError("a category with this name already exists")
    old = row.name
    row.name = clean
    session.flush()
    return old, to_category(row)


def _delete_budget_for(session: Session, category_id: int) -> None:
    row = session.scalars(select(BudgetRow).where(BudgetRow.category_id == category_id)).first()
    if row is not None:
        session.delete(row)
        session.flush()


def delete_category(session: Session, name: str, move_to: str = "") -> CategoryDeletion:
    """Delete a category or empty group, moving a category's uses first. The caller commits."""
    row = _category_row(session, name)
    if row is None:
        raise ValueError("category not found")
    if row.parent_id is None:
        children = session.scalars(
            select(CategoryRow).where(CategoryRow.parent_id == row.id).limit(1)
        ).first()
        if children is not None:
            raise ValueError("a group can be deleted only when it has no categories")
        deleted = CategoryDeletion(row.name, True, None, 0, 0)
        _delete_budget_for(session, row.id)
        session.delete(row)
        session.flush()
        return deleted

    target = None
    if move_to.strip():
        target = _leaf_category(session, move_to)
        if target.id == row.id:
            raise ValueError("a category cannot be moved to itself")

    transactions = (
        session.scalar(
            select(func.count())
            .select_from(TransactionCategoryRow)
            .where(TransactionCategoryRow.category_id == row.id)
        )
        or 0
    )
    rules = (
        session.scalar(
            select(func.count())
            .select_from(CategoryRuleRow)
            .where(CategoryRuleRow.category_id == row.id)
        )
        or 0
    )
    if (transactions > 0 or rules > 0) and target is None:
        raise ValueError(
            f"{row.name} is in use (transactions: {transactions}, rules: {rules}); "
            "choose a category to move them to"
        )

    moved_to = None
    if target is not None:
        session.execute(
            update(TransactionCategoryRow)
            .where(TransactionCategoryRow.category_id == row.id)
            .values(category_id=target.id)
        )
        session.execute(
            update(CategoryRuleRow)
            .where(CategoryRuleRow.category_id == row.id)
            .values(category_id=target.id)
        )
        moved_to = target.name if transactions > 0 or rules > 0 else None

    deleted = CategoryDeletion(row.name, False, moved_to, transactions, rules)
    _delete_budget_for(session, row.id)
    session.delete(row)
    session.flush()
    return deleted


def edit_rule(
    session: Session,
    rule_id: int,
    *,
    pattern: str | None = None,
    match: str | None = None,
    priority: int | None = None,
    category: str | None = None,
) -> CategoryRule:
    """Change a rule's fields and return it. The caller commits and runs categorize."""
    row = session.get(CategoryRuleRow, rule_id)
    if row is None:
        raise ValueError("rule not found")
    clean = normalize_pattern(row.pattern if pattern is None else pattern)
    if not 1 <= len(clean) <= RULE_PATTERN_LIMIT:
        raise ValueError(f"a rule pattern must be 1 to {RULE_PATTERN_LIMIT} characters")
    chosen_match = row.match if match is None else match
    if chosen_match not in MATCHES:
        raise ValueError(f"match must be one of: {', '.join(MATCHES)}")
    if category is None:
        category_id = row.category_id
    else:
        category_id = _leaf_category(session, category).id
    taken = select(CategoryRuleRow).where(
        CategoryRuleRow.match == chosen_match,
        CategoryRuleRow.pattern == clean,
        CategoryRuleRow.id != rule_id,
    )
    if session.scalars(taken).first() is not None:
        raise ValueError("a rule with this pattern and match already exists")
    row.pattern = clean
    row.match = chosen_match
    row.priority = row.priority if priority is None else priority
    row.category_id = category_id
    session.flush()
    return to_category_rule(row)


def list_category_assignments(session: Session) -> dict[int, CategoryAssignment]:
    """Map each categorized transaction's id to its assignment."""
    rows = session.scalars(select(TransactionCategoryRow)).all()
    return {row.transaction_id: to_category_assignment(row) for row in rows}


def _assignment_row(session: Session, transaction_id: int) -> TransactionCategoryRow | None:
    stmt = select(TransactionCategoryRow).where(
        TransactionCategoryRow.transaction_id == transaction_id
    )
    return session.scalars(stmt).first()


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
        _assign(session, transaction_id, target.id, MANUAL, None)
    return len(ids), to_category(target)


def clear_categories_by_hand(session: Session, transaction_ids: Iterable[int]) -> int:
    """Remove each transaction's category. The caller commits and runs categorize."""
    ids = _distinct_transaction_ids(transaction_ids)
    for transaction_id in ids:
        _require_transaction(session, transaction_id)
    for transaction_id in ids:
        remove_category(session, transaction_id)
    return len(ids)


def set_category_by_hand(session: Session, transaction_id: int, category: str) -> Category:
    """Set the transaction's category by hand, so rules leave it alone. The caller commits."""
    _require_transaction(session, transaction_id)
    target = _leaf_category(session, category)
    _assign(session, transaction_id, target.id, MANUAL, None)
    return to_category(target)


def clear_category_by_hand(session: Session, transaction_id: int) -> None:
    """Remove the transaction's category, leaving it to the rules. The caller commits."""
    _require_transaction(session, transaction_id)
    remove_category(session, transaction_id)


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
