"""The category tree, the rules, and uncategorized transactions, as plain text."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from finances.categorize.service import CategorizeResult
from finances.db.repositories import account_names, list_categories, list_rules, list_uncategorized
from finances.domain.merchants import clean_merchant
from finances.domain.models import Category
from finances.domain.money import format_cents


@dataclass(frozen=True)
class CategoryLine:
    group: str
    category: str
    kind: str


@dataclass(frozen=True)
class RuleLine:
    id: str
    priority: str
    match: str
    pattern: str
    category: str


@dataclass(frozen=True)
class UncategorizedLine:
    id: str
    date: str
    account: str
    merchant: str
    amount: str


def _kind(category: Category) -> str:
    flags = (
        ("transfer", category.is_transfer),
        ("income", category.is_income),
        ("sensitive", category.is_sensitive),
    )
    return ", ".join(word for word, flag in flags if flag)


def category_lines(session: Session) -> list[CategoryLine]:
    """One line per category, groups and the categories in each in name order, ignoring case."""
    found = list_categories(session)
    return [
        CategoryLine(group.name, category.name, _kind(category))
        for group in found
        if group.group_id is None
        for category in found
        if category.group_id == group.id
    ]


def rule_lines(session: Session) -> list[RuleLine]:
    names = {category.id: category.name for category in list_categories(session)}
    return [
        RuleLine(
            str(rule.id), str(rule.priority), rule.match, rule.pattern, names[rule.category_id]
        )
        for rule in list_rules(session)
    ]


def uncategorized_lines(session: Session, limit: int) -> list[UncategorizedLine]:
    names = account_names(session)
    return [
        UncategorizedLine(
            str(item.id),
            item.posted_date.isoformat(),
            names[item.account_id],
            clean_merchant(item.description),
            format_cents(item.amount_cents),
        )
        for item in list_uncategorized(session, limit)
    ]


def categorized_text(result: CategorizeResult) -> str:
    noun = "transaction" if result.total == 1 else "transactions"
    return (
        f"Categorized {result.total} {noun}: {result.changed} changed, "
        f"{result.uncategorized} without a category."
    )
