from sqlalchemy import select
from sqlalchemy.orm import Session

from finances.db.orm import (
    BudgetRow,
    to_budget,
)
from finances.db.repositories.audit import record_change
from finances.db.repositories.categories import _category_row
from finances.domain.budgets import AMOUNT_MESSAGE
from finances.domain.models import Budget
from finances.domain.money import format_cents

_BUDGET_MIN = 1


_BUDGET_MAX = 100_000_000


def set_budget(session: Session, name: str, amount_cents: int) -> tuple[str, Budget]:
    """Set or replace the monthly target for a group or category. The caller commits."""
    row = _category_row(session, name)
    if row is None:
        raise ValueError("category not found")
    if not _BUDGET_MIN <= amount_cents <= _BUDGET_MAX:
        raise ValueError(AMOUNT_MESSAGE)
    found = session.scalars(select(BudgetRow).where(BudgetRow.category_id == row.id)).first()
    previous = None if found is None else found.amount_cents
    if previous == amount_cents:
        session.flush()
        return row.name, to_budget(found)
    if found is None:
        found = BudgetRow(category_id=row.id, amount_cents=amount_cents)
        session.add(found)
    else:
        found.amount_cents = amount_cents
    session.flush()
    record_change(
        session,
        action="budget_set",
        kind="category",
        record_id=row.id,
        before=None if previous is None else format_cents(previous),
        after=format_cents(amount_cents),
    )
    return row.name, to_budget(found)


def remove_budget(session: Session, name: str) -> str:
    """Remove the budget for a group or category and return its stored name. The caller commits."""
    row = _category_row(session, name)
    if row is None:
        raise ValueError("category not found")
    found = session.scalars(select(BudgetRow).where(BudgetRow.category_id == row.id)).first()
    if found is None:
        raise ValueError(f"there is no budget for {row.name}")
    before = format_cents(found.amount_cents)
    session.delete(found)
    session.flush()
    record_change(
        session,
        action="budget_removed",
        kind="category",
        record_id=row.id,
        before=before,
    )
    return row.name


def list_budgets(session: Session) -> list[Budget]:
    """Return every budget, in id order."""
    stmt = select(BudgetRow).order_by(BudgetRow.id)
    return [to_budget(row) for row in session.scalars(stmt).all()]
