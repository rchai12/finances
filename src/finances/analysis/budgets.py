"""Budget progress for a month from stored targets and Phase 12a spending."""

from datetime import date

from sqlalchemy.orm import Session

from finances.analysis.spending import load_flows
from finances.db.repositories import list_budgets, list_categories
from finances.domain.budgets import BudgetLine, BudgetTarget, budget_lines
from finances.domain.spending import month_bounds, spending_lines


def budget_report(session: Session, start: date, today: date) -> list[BudgetLine]:
    """Each budget's spent and left for the month of start, judged as of today."""
    end = month_bounds(start)[1]
    categories = {item.id: item for item in list_categories(session)}
    targets = [
        BudgetTarget(
            name=categories[budget.category_id].name,
            is_group=categories[budget.category_id].group_id is None,
            target_cents=budget.amount_cents,
        )
        for budget in list_budgets(session)
    ]
    flows = load_flows(session, start, end, parts=True)
    by_category = {line.label: line.spent_cents for line in spending_lines(flows, "category")}
    by_group = {line.label: line.spent_cents for line in spending_lines(flows, "group")}
    return budget_lines(targets, by_category, by_group, start, end, today)
